"""Deterministic verification baseline.

The learned risk model will be added separately so deterministic facts do not
leak directly into the ML target.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from pathlib import Path

from .models import Decision, ProposedAction, VerificationResult
from .repository import NotFoundError, Repository


DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "READ_ONLY": frozenset({"get_customer", "get_invoice", "calculate_balance"}),
    "AGENT": frozenset(
        {
            "get_customer",
            "get_invoice",
            "calculate_balance",
            "create_invoice",
            "send_email",
            "update_customer",
        }
    ),
    "ADMIN": frozenset(
        {
            "get_customer",
            "get_invoice",
            "calculate_balance",
            "create_invoice",
            "send_email",
            "update_customer",
            "refund_customer",
        }
    ),
}


class RuleVerifier:
    """Evaluate permissions, parameter validity, and explicit policies."""

    def __init__(
        self,
        role_permissions: Mapping[str, Set[str]] | None = None,
        refund_review_limit: float = 10_000,
        database_path: str | Path = "data/veriagent.db",
    ) -> None:
        source = role_permissions or DEFAULT_ROLE_PERMISSIONS
        self.role_permissions = {role: frozenset(actions) for role, actions in source.items()}
        self.refund_review_limit = refund_review_limit
        self.repository = Repository(database_path)

    def verify(self, proposal: ProposedAction) -> VerificationResult:
        reasons: list[str] = []
        checks = {
            "known_role": proposal.user_role in self.role_permissions,
            "permission": False,
            "parameters": True,
            "entity_reference": True,
            "policy": True,
        }

        allowed_actions = self.role_permissions.get(proposal.user_role, frozenset())
        checks["permission"] = proposal.action in allowed_actions
        if not checks["known_role"]:
            reasons.append(f"Unknown user role: {proposal.user_role}")
        if not checks["permission"]:
            reasons.append(
                f"Role {proposal.user_role} is not permitted to perform {proposal.action}"
            )

        # Verify entity references independently
        self._verify_entities(proposal, checks, reasons)

        decision = Decision.ALLOW
        if proposal.action == "refund_customer":
            decision = self._check_refund(proposal, checks, reasons)

        if not all(
            checks[name]
            for name in ("known_role", "permission", "parameters", "entity_reference")
        ):
            decision = Decision.BLOCK

        if not reasons:
            reasons.append("All deterministic checks passed")

        return VerificationResult(decision=decision, reasons=tuple(reasons), checks=checks)

    def _verify_entities(
        self, proposal: ProposedAction, checks: dict[str, bool], reasons: list[str]
    ) -> None:
        """Independently verify that referenced entities exist in the database."""
        # Check customer_id if present
        if "customer_id" in proposal.parameters:
            customer_id = proposal.parameters["customer_id"]
            if not self.repository.customer_exists(customer_id):
                checks["entity_reference"] = False
                reasons.append(f"Customer {customer_id} does not exist")

        # Check invoice_id if present
        if "invoice_id" in proposal.parameters:
            invoice_id = proposal.parameters["invoice_id"]
            if not self.repository.invoice_exists(invoice_id):
                checks["entity_reference"] = False
                reasons.append(f"Invoice {invoice_id} does not exist")

    def _check_refund(
        self,
        proposal: ProposedAction,
        checks: dict[str, bool],
        reasons: list[str],
    ) -> Decision:
        amount = proposal.parameters.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
            checks["parameters"] = False
            reasons.append("Refund amount must be a positive number")
            return Decision.BLOCK

        if amount > self.refund_review_limit:
            checks["policy"] = False
            reasons.append(
                f"Refund amount exceeds the review limit of {self.refund_review_limit:.2f}"
            )
            return Decision.REVIEW

        return Decision.ALLOW
