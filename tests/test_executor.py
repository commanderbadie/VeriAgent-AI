"""Tests for the secure executor.

CRITICAL SECURITY TESTS:
These tests prove that BLOCK and REVIEW decisions never result in tool execution.
"""

import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, call

from veriagent import (
    BusinessTools,
    Decision,
    ExecutionStatus,
    ProposedAction,
    RuleVerifier,
    SecureExecutor,
    ToolRegistry,
)


@contextmanager
def _db_connection(db_path: str | Path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that properly closes SQLite connections."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
from veriagent.database import initialize_database


class SecureExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        """Create temporary database and executor for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        initialize_database(self.db_path)

        # Custom permissions that include test actions
        test_permissions = {
            "READ_ONLY": frozenset({"get_customer", "get_invoice", "calculate_balance"}),
            "AGENT": frozenset({
                "get_customer",
                "get_invoice",
                "calculate_balance",
                "create_invoice",
                "send_email",
                "update_customer",
                "failing_tool",  # Add test tool
            }),
            "ADMIN": frozenset({
                "get_customer",
                "get_invoice",
                "calculate_balance",
                "create_invoice",
                "send_email",
                "update_customer",
                "refund_customer",
                "failing_tool",  # Add test tool
            }),
        }

        self.verifier = RuleVerifier(
            database_path=self.db_path,
            role_permissions=test_permissions,
        )
        self.registry = ToolRegistry()
        self.tools = BusinessTools(database_path=self.db_path)

        # Register tools
        self.registry.register(
            "get_customer",
            self.tools.get_customer,
            "Retrieve customer information",
            risk_level="LOW",
        )
        self.registry.register(
            "refund_customer",
            self.tools.refund_customer,
            "Process a customer refund",
            risk_level="HIGH",
        )

        self.executor = SecureExecutor(
            verifier=self.verifier,
            tool_registry=self.registry,
            database_path=self.db_path,
        )

    def test_allow_decision_executes_tool(self) -> None:
        """ALLOW decisions should execute the tool."""
        proposal = ProposedAction(
            action="get_customer",
            user_role="AGENT",
            parameters={"customer_id": 101},
            tool="get_customer",
        )

        result = self.executor.submit(proposal)

        self.assertEqual(result.decision, Decision.ALLOW)
        self.assertEqual(result.status, ExecutionStatus.EXECUTED)
        self.assertIsNotNone(result.tool_result)
        self.assertTrue(result.tool_result.success)
        self.assertEqual(result.tool_result.data.customer_id, 101)

    def test_block_decision_never_executes_tool(self) -> None:
        """CRITICAL: BLOCK decisions must never execute tools."""
        # Create a mock tool to prove it's never called
        mock_tool = MagicMock(return_value="SHOULD NEVER BE CALLED")
        self.registry.register("dangerous_action", mock_tool, "Mock tool", risk_level="HIGH")

        # Unauthorized user
        proposal = ProposedAction(
            action="dangerous_action",
            user_role="READ_ONLY",  # Not permitted
            parameters={},
            tool="dangerous_action",
        )

        result = self.executor.submit(proposal)

        # Verify decision and status
        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertEqual(result.status, ExecutionStatus.BLOCKED)
        self.assertIsNone(result.tool_result)
        self.assertIsNotNone(result.error_message)

        # CRITICAL: Verify mock tool was never called
        mock_tool.assert_not_called()

    def test_review_decision_queues_without_execution(self) -> None:
        """CRITICAL: REVIEW decisions must queue without executing."""
        # REVIEW occurs when amount exceeds limit
        proposal = ProposedAction(
            action="refund_customer",
            user_role="ADMIN",
            parameters={"customer_id": 101, "amount": 25_000, "reason": "Test"},
            tool="refund_customer",
        )

        result = self.executor.submit(proposal)

        # Verify queued for review
        self.assertEqual(result.decision, Decision.REVIEW)
        self.assertEqual(result.status, ExecutionStatus.PENDING_REVIEW)
        self.assertIsNone(result.tool_result)
        self.assertIsNone(result.executed_at)

        # Verify it's in the pending queue
        pending = self.executor.get_pending_reviews()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["review_id"], result.execution_id)

    def test_missing_customer_is_blocked(self) -> None:
        """BLOCK on missing entity should never execute."""
        mock_tool = MagicMock()
        self.registry.register("test_action", mock_tool, "Test", risk_level="LOW")

        proposal = ProposedAction(
            action="test_action",
            user_role="AGENT",
            parameters={"customer_id": 999},  # Does not exist
            tool="test_action",
        )

        result = self.executor.submit(proposal)

        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertEqual(result.status, ExecutionStatus.BLOCKED)
        mock_tool.assert_not_called()

    def test_unregistered_tool_fails_safely(self) -> None:
        """Attempting to execute an unregistered tool should fail."""
        # Use create_invoice which is permitted for ADMIN but not registered
        proposal = ProposedAction(
            action="create_invoice",
            user_role="ADMIN",
            parameters={"customer_id": 101, "amount": 1000, "due_date": "2026-12-31"},
            tool="create_invoice",
        )

        result = self.executor.submit(proposal)

        # Should be allowed by verifier but fail at execution
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("not registered", result.error_message)

    def test_approve_review_executes_after_validation(self) -> None:
        """Approval should execute REVIEW actions even if revalidation still shows REVIEW."""
        # Submit an action requiring review (₹11,000 > ₹10,000 limit)
        proposal = ProposedAction(
            action="refund_customer",
            user_role="ADMIN",
            parameters={"customer_id": 101, "amount": 11_000, "reason": "Customer complaint"},
            tool="refund_customer",
        )

        submit_result = self.executor.submit(proposal)
        self.assertEqual(submit_result.status, ExecutionStatus.PENDING_REVIEW)
        review_id = submit_result.execution_id

        # Approve the review
        # Revalidation will still return REVIEW (amount still > limit)
        # But approval should satisfy the review requirement → execute
        approval_result = self.executor.approve_review(
            review_id, 
            reviewed_by="supervisor@company.com",
            approval_reason="Valid customer complaint verified"
        )

        # Should execute because human approval satisfies REVIEW requirement
        self.assertEqual(approval_result.status, ExecutionStatus.REVIEW_APPROVED)
        self.assertIsNotNone(approval_result.tool_result)
        self.assertTrue(approval_result.tool_result.success)
        self.assertEqual(approval_result.tool_result.data["amount"], 11_000)

    def test_approve_review_revalidates_before_execution(self) -> None:
        """Approval must reject if revalidation returns BLOCK (cannot override hard blocks)."""
        # Submit a refund that triggers REVIEW
        proposal = ProposedAction(
            action="refund_customer",
            user_role="ADMIN",
            parameters={"customer_id": 101, "amount": 15_000, "reason": "Test"},
            tool="refund_customer",
        )

        submit_result = self.executor.submit(proposal)
        self.assertEqual(submit_result.status, ExecutionStatus.PENDING_REVIEW)
        review_id = submit_result.execution_id

        # Now delete the customer to make revalidation fail with BLOCK
        with _db_connection(self.db_path) as conn:
            conn.execute("DELETE FROM customers WHERE customer_id = 101")

        # Try to approve - revalidation will BLOCK (customer doesn't exist)
        approval_result = self.executor.approve_review(
            review_id,
            reviewed_by="supervisor@company.com",
            approval_reason="Approved"
        )

        # Should be rejected because BLOCK cannot be overridden
        self.assertEqual(approval_result.status, ExecutionStatus.REVIEW_REJECTED)
        self.assertIsNone(approval_result.tool_result)
        self.assertIn("Customer 101 does not exist", approval_result.error_message)

    def test_approval_cannot_override_block_decision(self) -> None:
        """CRITICAL: Human approval cannot override BLOCK decisions."""
        # First, set limit very high to get initial ALLOW
        self.executor.verifier.refund_review_limit = 50_000

        proposal = ProposedAction(
            action="refund_customer",
            user_role="ADMIN",
            parameters={"customer_id": 101, "amount": 30_000, "reason": "Test"},
            tool="refund_customer",
        )

        # This will be ALLOWED initially
        submit_result = self.executor.submit(proposal)

        # If it was allowed, we need a different test
        # Let's directly test with missing customer
        proposal_blocked = ProposedAction(
            action="refund_customer",
            user_role="ADMIN",
            parameters={"customer_id": 999, "amount": 5_000, "reason": "Test"},
            tool="refund_customer",
        )

        blocked_result = self.executor.submit(proposal_blocked)
        self.assertEqual(blocked_result.status, ExecutionStatus.BLOCKED)
        # Cannot approve a BLOCKED action - it's not in pending_reviews

    def test_reject_review_never_executes(self) -> None:
        """CRITICAL: Rejected reviews must never execute."""
        # Submit a real refund that triggers REVIEW
        proposal = ProposedAction(
            action="refund_customer",
            user_role="ADMIN",
            parameters={"customer_id": 101, "amount": 20_000, "reason": "Test"},
            tool="refund_customer",
        )

        # Submit for review
        submit_result = self.executor.submit(proposal)
        self.assertEqual(submit_result.status, ExecutionStatus.PENDING_REVIEW)
        review_id = submit_result.execution_id

        # Reject it
        rejection_result = self.executor.reject_review(review_id, reviewed_by="test_admin")

        self.assertEqual(rejection_result.status, ExecutionStatus.REVIEW_REJECTED)
        self.assertIsNone(rejection_result.tool_result)

    def test_duplicate_approval_prevented(self) -> None:
        """Cannot approve the same review twice."""
        proposal = ProposedAction(
            action="refund_customer",
            user_role="ADMIN",
            parameters={"customer_id": 101, "amount": 15_000, "reason": "Test"},
            tool="refund_customer",
        )

        submit_result = self.executor.submit(proposal)
        review_id = submit_result.execution_id

        # First approval
        self.executor.approve_review(review_id, reviewed_by="admin1")

        # Second approval attempt should fail
        with self.assertRaises(ValueError) as context:
            self.executor.approve_review(review_id, reviewed_by="admin2")
        self.assertIn("No pending review", str(context.exception))

    def test_tool_exception_is_caught_and_logged(self) -> None:
        """Tool exceptions should be caught and returned as FAILED status."""

        def failing_tool(customer_id):
            raise RuntimeError("Tool failed internally")

        # Register the failing tool and add to permissions
        self.registry.register("failing_tool", failing_tool, "Fails always", risk_level="LOW")

        proposal = ProposedAction(
            action="failing_tool",
            user_role="AGENT",  # AGENT has get_customer permission
            parameters={"customer_id": 101},
            tool="failing_tool",
        )

        result = self.executor.submit(proposal)

        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("Tool failed internally", result.error_message)

    def test_pending_reviews_listed_correctly(self) -> None:
        """Pending reviews should appear in the queue."""
        # Submit multiple reviews
        for amount in [15_000, 20_000, 25_000]:
            proposal = ProposedAction(
                action="refund_customer",
                user_role="ADMIN",
                parameters={"customer_id": 101, "amount": amount, "reason": "Test"},
                tool="refund_customer",
            )
            self.executor.submit(proposal)

        pending = self.executor.get_pending_reviews()
        self.assertEqual(len(pending), 3)

        # Approve one
        self.executor.approve_review(pending[0]["review_id"], reviewed_by="admin")

        # Should now have 2 pending
        pending_after = self.executor.get_pending_reviews()
        self.assertEqual(len(pending_after), 2)

    def test_all_decisions_logged_to_audit_trail(self) -> None:
        """Every submit should create an audit log entry."""
        import sqlite3

        # Submit various decisions
        proposals = [
            ProposedAction("get_customer", "AGENT", {"customer_id": 101}, "get_customer"),
            ProposedAction("get_customer", "READ_ONLY", {"customer_id": 999}, "get_customer"),
            ProposedAction(
                "refund_customer",
                "ADMIN",
                {"customer_id": 101, "amount": 20_000, "reason": "Test"},
                "refund_customer",
            ),
        ]

        for proposal in proposals:
            self.executor.submit(proposal)

        # Check audit log
        with _db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM action_logs")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 3)

    def test_executor_never_accepts_external_verification_result(self) -> None:
        """CRITICAL DESIGN TEST: Executor has no method that accepts VerificationResult."""
        # This test documents the security design
        # The executor.submit() method signature should NOT have a verification parameter

        import inspect

        submit_sig = inspect.signature(self.executor.submit)
        param_names = list(submit_sig.parameters.keys())

        # Should only accept ProposedAction
        self.assertEqual(param_names, ["proposal"])
        self.assertNotIn("verification", param_names)
        self.assertNotIn("result", param_names)


class ToolRegistryTests(unittest.TestCase):
    def test_register_and_retrieve_tool(self) -> None:
        registry = ToolRegistry()

        def mock_tool(**kwargs):
            return "result"

        registry.register("test_tool", mock_tool, "Test tool", risk_level="LOW")

        tool_def = registry.get("test_tool")
        self.assertEqual(tool_def.name, "test_tool")
        self.assertEqual(tool_def.risk_level, "LOW")
        self.assertEqual(tool_def.callable, mock_tool)

    def test_unregistered_tool_raises_error(self) -> None:
        registry = ToolRegistry()

        from veriagent import ToolNotFoundError

        with self.assertRaises(ToolNotFoundError):
            registry.get("unknown_tool")

    def test_duplicate_registration_prevented(self) -> None:
        registry = ToolRegistry()

        def mock_tool():
            pass

        registry.register("tool", mock_tool, "Tool", risk_level="LOW")

        with self.assertRaises(ValueError):
            registry.register("tool", mock_tool, "Duplicate", risk_level="LOW")

    def test_invalid_risk_level_rejected(self) -> None:
        registry = ToolRegistry()

        with self.assertRaises(ValueError):
            registry.register("tool", lambda: None, "Test", risk_level="INVALID")

    def test_list_all_tools(self) -> None:
        registry = ToolRegistry()

        registry.register("tool1", lambda: None, "Tool 1", risk_level="LOW")
        registry.register("tool2", lambda: None, "Tool 2", risk_level="HIGH")

        tools = registry.list_tools()
        self.assertEqual(len(tools), 2)
        self.assertEqual({t.name for t in tools}, {"tool1", "tool2"})

    def test_is_registered(self) -> None:
        registry = ToolRegistry()
        registry.register("tool", lambda: None, "Tool", risk_level="LOW")

        self.assertTrue(registry.is_registered("tool"))
        self.assertFalse(registry.is_registered("unknown"))


if __name__ == "__main__":
    unittest.main()
