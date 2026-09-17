"""Secure executor that enforces VeriAgent decisions.

CRITICAL SECURITY PRINCIPLE:
The executor owns the verification process. It never accepts caller-provided
verification results, which could be fabricated by a malicious agent.

Flow:
1. Agent submits ProposedAction
2. Executor calls verifier internally
3. Executor enforces decision:
   - ALLOW → execute tool and log
   - REVIEW → save as pending, do not execute
   - BLOCK → log rejection, never execute
4. For approved REVIEW actions:
   - Revalidate (rules might have changed)
   - Execute exactly once
   - Prevent duplicate execution
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .models import Decision, ProposedAction, VerificationResult
from .repository import Repository
from .tool_registry import ToolNotFoundError, ToolRegistry
from .verifier import RuleVerifier


class ExecutionStatus(str, Enum):
    """Status of an execution attempt."""

    EXECUTED = "EXECUTED"  # Tool was called successfully
    BLOCKED = "BLOCKED"  # Verification blocked the action
    PENDING_REVIEW = "PENDING_REVIEW"  # Awaiting human approval
    REVIEW_APPROVED = "REVIEW_APPROVED"  # Human approved, then executed
    REVIEW_REJECTED = "REVIEW_REJECTED"  # Human rejected, never executed
    FAILED = "FAILED"  # Tool execution raised an exception


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result of a secure execution attempt."""

    execution_id: int
    proposal: ProposedAction
    decision: Decision
    verification_result: VerificationResult
    status: ExecutionStatus
    tool_result: Any | None
    error_message: str | None
    executed_at: str | None


class SecureExecutor:
    """Enforces verification before tool execution and maintains audit log."""

    def __init__(
        self,
        verifier: RuleVerifier,
        tool_registry: ToolRegistry,
        database_path: str | Path = "data/veriagent.db",
    ) -> None:
        self.verifier = verifier
        self.tool_registry = tool_registry
        self.database_path = Path(database_path)
        self.repository = Repository(database_path)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create pending_reviews table if it doesn't exist."""
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_log_id INTEGER NOT NULL,
                    proposed_action_json TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    verification_reasons TEXT NOT NULL,
                    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    execution_id INTEGER,
                    FOREIGN KEY (action_log_id) REFERENCES action_logs(log_id)
                )
                """
            )

    def submit(self, proposal: ProposedAction) -> ExecutionResult:
        """Submit a proposed action for verification and conditional execution.

        SECURITY: This method calls the verifier internally. Never accept
        a verification result from the caller.

        Args:
            proposal: The action an agent wants to perform

        Returns:
            ExecutionResult with decision, status, and any tool output
        """
        # Step 1: Verify the proposal internally
        verification = self.verifier.verify(proposal)

        # Step 2: Log the attempt
        action_log_id = self.repository.log_action(
            user_id=None,  # Could be extracted from proposal if needed
            action=proposal.action,
            parameters_json=json.dumps(proposal.parameters),
            decision=verification.decision.value,
            reason="; ".join(verification.reasons),
            risk_score=None,  # Will be added in Phase 6
        )

        # Step 3: Enforce the decision
        if verification.decision == Decision.ALLOW:
            return self._execute_allowed(proposal, verification, action_log_id)
        elif verification.decision == Decision.REVIEW:
            return self._queue_for_review(proposal, verification, action_log_id)
        else:  # BLOCK
            return self._block_execution(proposal, verification, action_log_id)

    def _execute_allowed(
        self, proposal: ProposedAction, verification: VerificationResult, action_log_id: int
    ) -> ExecutionResult:
        """Execute an ALLOW decision."""
        try:
            # Check if tool is registered
            if not proposal.tool:
                raise ToolNotFoundError("ProposedAction must specify a tool name")

            tool_def = self.tool_registry.get(proposal.tool)

            # Execute the tool
            tool_result = tool_def.callable(**proposal.parameters)

            return ExecutionResult(
                execution_id=action_log_id,
                proposal=proposal,
                decision=verification.decision,
                verification_result=verification,
                status=ExecutionStatus.EXECUTED,
                tool_result=tool_result,
                error_message=None,
                executed_at=datetime.now().isoformat(),
            )
        except Exception as e:
            return ExecutionResult(
                execution_id=action_log_id,
                proposal=proposal,
                decision=verification.decision,
                verification_result=verification,
                status=ExecutionStatus.FAILED,
                tool_result=None,
                error_message=str(e),
                executed_at=datetime.now().isoformat(),
            )

    def _queue_for_review(
        self, proposal: ProposedAction, verification: VerificationResult, action_log_id: int
    ) -> ExecutionResult:
        """Queue a REVIEW decision for human approval."""
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO pending_reviews (
                    action_log_id,
                    proposed_action_json,
                    decision,
                    verification_reasons
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    action_log_id,
                    json.dumps(
                        {
                            "action": proposal.action,
                            "user_role": proposal.user_role,
                            "parameters": proposal.parameters,
                            "tool": proposal.tool,
                        }
                    ),
                    verification.decision.value,
                    "; ".join(verification.reasons),
                ),
            )
            review_id = cursor.lastrowid

        return ExecutionResult(
            execution_id=review_id,
            proposal=proposal,
            decision=verification.decision,
            verification_result=verification,
            status=ExecutionStatus.PENDING_REVIEW,
            tool_result=None,
            error_message=None,
            executed_at=None,
        )

    def _block_execution(
        self, proposal: ProposedAction, verification: VerificationResult, action_log_id: int
    ) -> ExecutionResult:
        """Block execution and log the rejection."""
        return ExecutionResult(
            execution_id=action_log_id,
            proposal=proposal,
            decision=verification.decision,
            verification_result=verification,
            status=ExecutionStatus.BLOCKED,
            tool_result=None,
            error_message="; ".join(verification.reasons),
            executed_at=None,
        )

    def approve_review(
        self, review_id: int, reviewed_by: str, approval_reason: str | None = None
    ) -> ExecutionResult:
        """Approve a pending review and execute the action.

        SECURITY:
        - Revalidates the action before execution
        - If revalidation returns ALLOW or REVIEW → execute (approval satisfies REVIEW)
        - If revalidation returns BLOCK → reject (approval cannot override BLOCK)
        """
        # Step 1: Fetch the pending review
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM pending_reviews WHERE review_id = ? AND status = 'PENDING'",
                (review_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"No pending review found with ID {review_id}")

            # Prevent duplicate execution
            if row["status"] != "PENDING":
                raise ValueError(f"Review {review_id} already processed: {row['status']}")

            # Reconstruct the proposal
            action_data = json.loads(row["proposed_action_json"])
            proposal = ProposedAction(
                action=action_data["action"],
                user_role=action_data["user_role"],
                parameters=action_data["parameters"],
                tool=action_data.get("tool"),
            )

        # Step 2: Revalidate (rules/data might have changed)
        verification = self.verifier.verify(proposal)

        # Step 3: Approval logic
        # BLOCK → Cannot execute (hard rejection - entity doesn't exist, no permission, etc.)
        # ALLOW → Can execute (rules improved, or was low risk all along)
        # REVIEW → Can execute (approval satisfies the review requirement)
        if verification.decision == Decision.BLOCK:
            # Human approval cannot override a hard BLOCK
            # BLOCK means: missing entity, no permission, invalid parameters, etc.
            with sqlite3.connect(self.database_path) as conn:
                conn.execute(
                    """
                    UPDATE pending_reviews
                    SET status = 'REJECTED',
                        reviewed_at = ?,
                        reviewed_by = ?
                    WHERE review_id = ?
                    """,
                    (datetime.now().isoformat(), reviewed_by, review_id),
                )

            return ExecutionResult(
                execution_id=review_id,
                proposal=proposal,
                decision=verification.decision,
                verification_result=verification,
                status=ExecutionStatus.REVIEW_REJECTED,
                tool_result=None,
                error_message=f"Revalidation blocked: {'; '.join(verification.reasons)}",
                executed_at=None,
            )

        # Step 4: Execute the tool (approval satisfies ALLOW or REVIEW)
        try:
            if not proposal.tool:
                raise ToolNotFoundError("ProposedAction must specify a tool name")

            tool_def = self.tool_registry.get(proposal.tool)
            tool_result = tool_def.callable(**proposal.parameters)

            # Log successful execution with approval context
            reason = f"Human-approved review {review_id} by {reviewed_by}"
            if approval_reason:
                reason += f": {approval_reason}"

            action_log_id = self.repository.log_action(
                user_id=None,
                action=proposal.action,
                parameters_json=json.dumps(proposal.parameters),
                decision="ALLOW",
                reason=reason,
                risk_score=None,
            )

            # Update review status with approval details
            with sqlite3.connect(self.database_path) as conn:
                conn.execute(
                    """
                    UPDATE pending_reviews
                    SET status = 'APPROVED',
                        reviewed_at = ?,
                        reviewed_by = ?,
                        execution_id = ?
                    WHERE review_id = ?
                    """,
                    (datetime.now().isoformat(), reviewed_by, action_log_id, review_id),
                )

            return ExecutionResult(
                execution_id=action_log_id,
                proposal=proposal,
                decision=Decision.ALLOW,
                verification_result=verification,
                status=ExecutionStatus.REVIEW_APPROVED,
                tool_result=tool_result,
                error_message=None,
                executed_at=datetime.now().isoformat(),
            )

        except Exception as e:
            # Tool execution failed
            with sqlite3.connect(self.database_path) as conn:
                conn.execute(
                    """
                    UPDATE pending_reviews
                    SET status = 'REJECTED',
                        reviewed_at = ?,
                        reviewed_by = ?
                    WHERE review_id = ?
                    """,
                    (datetime.now().isoformat(), reviewed_by, review_id),
                )

            return ExecutionResult(
                execution_id=review_id,
                proposal=proposal,
                decision=Decision.ALLOW,
                verification_result=verification,
                status=ExecutionStatus.FAILED,
                tool_result=None,
                error_message=str(e),
                executed_at=datetime.now().isoformat(),
            )

    def reject_review(self, review_id: int, reviewed_by: str) -> ExecutionResult:
        """Reject a pending review without executing."""
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM pending_reviews WHERE review_id = ? AND status = 'PENDING'",
                (review_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"No pending review found with ID {review_id}")

            action_data = json.loads(row["proposed_action_json"])
            proposal = ProposedAction(
                action=action_data["action"],
                user_role=action_data["user_role"],
                parameters=action_data["parameters"],
                tool=action_data.get("tool"),
            )

            # Mark as rejected
            conn.execute(
                """
                UPDATE pending_reviews
                SET status = 'REJECTED',
                    reviewed_at = ?,
                    reviewed_by = ?
                WHERE review_id = ?
                """,
                (datetime.now().isoformat(), reviewed_by, review_id),
            )

        return ExecutionResult(
            execution_id=review_id,
            proposal=proposal,
            decision=Decision.REVIEW,
            verification_result=None,  # type: ignore
            status=ExecutionStatus.REVIEW_REJECTED,
            tool_result=None,
            error_message="Human reviewer rejected the action",
            executed_at=None,
        )

    def get_pending_reviews(self) -> list[dict[str, Any]]:
        """Retrieve all pending reviews awaiting human decision."""
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT review_id, proposed_action_json, verification_reasons, submitted_at
                FROM pending_reviews
                WHERE status = 'PENDING'
                ORDER BY review_id ASC
                """
            )
            return [
                {
                    "review_id": row["review_id"],
                    "proposal": json.loads(row["proposed_action_json"]),
                    "reasons": row["verification_reasons"],
                    "submitted_at": row["submitted_at"],
                }
                for row in cursor.fetchall()
            ]
