"""Minimal demonstration of action interception before tool execution."""

from __future__ import annotations

from .database import initialize_database
from .models import ProposedAction
from .tools import BusinessTools
from .verifier import RuleVerifier


def main() -> None:
    # Initialize database
    db_path = initialize_database()
    print(f"Database initialized: {db_path}\n")

    # Create verifier and tools
    verifier = RuleVerifier(database_path=db_path)
    tools = BusinessTools(database_path=db_path)

    # Demo 1: Safe read operation
    print("=" * 60)
    print("DEMO 1: Safe read operation (get_customer)")
    print("=" * 60)
    proposal = ProposedAction(
        action="get_customer",
        user_role="AGENT",
        parameters={"customer_id": 102},
        tool="get_customer",
    )
    result = verifier.verify(proposal)
    print(f"Proposed: {proposal.action} for customer {proposal.parameters['customer_id']}")
    print(f"Decision: {result.decision.value}")
    print(f"Reasons: {', '.join(result.reasons)}")

    if result.decision.value == "ALLOW":
        tool_result = tools.get_customer(102)
        print(f"Executed: {tool_result.message}")
        print(f"Customer: {tool_result.data}")
    print()

    # Demo 2: Large refund requires review
    print("=" * 60)
    print("DEMO 2: Large refund → REVIEW")
    print("=" * 60)
    proposal = ProposedAction(
        action="refund_customer",
        user_role="ADMIN",
        parameters={"customer_id": 102, "amount": 20_000, "reason": "Product return"},
        tool="refund_customer",
    )
    result = verifier.verify(proposal)
    print(f"Proposed: {proposal.action}")
    print(f"Amount: ₹{proposal.parameters['amount']:,.2f}")
    print(f"Decision: {result.decision.value}")
    print(f"Reasons: {', '.join(result.reasons)}")
    print()

    # Demo 3: Missing customer → BLOCK
    print("=" * 60)
    print("DEMO 3: Non-existent customer → BLOCK")
    print("=" * 60)
    proposal = ProposedAction(
        action="refund_customer",
        user_role="ADMIN",
        parameters={"customer_id": 999, "amount": 5_000, "reason": "Test"},
        tool="refund_customer",
    )
    result = verifier.verify(proposal)
    print(f"Proposed: {proposal.action} for customer {proposal.parameters['customer_id']}")
    print(f"Decision: {result.decision.value}")
    print(f"Reasons: {', '.join(result.reasons)}")
    print()

    # Demo 4: Unauthorized action → BLOCK
    print("=" * 60)
    print("DEMO 4: READ_ONLY user tries refund → BLOCK")
    print("=" * 60)
    proposal = ProposedAction(
        action="refund_customer",
        user_role="READ_ONLY",
        parameters={"customer_id": 101, "amount": 1_000, "reason": "Test"},
        tool="refund_customer",
    )
    result = verifier.verify(proposal)
    print(f"Proposed: {proposal.action} by {proposal.user_role}")
    print(f"Decision: {result.decision.value}")
    print(f"Reasons: {', '.join(result.reasons)}")
    print()

    # Demo 5: Small refund allowed
    print("=" * 60)
    print("DEMO 5: Small refund → ALLOW and execute")
    print("=" * 60)
    proposal = ProposedAction(
        action="refund_customer",
        user_role="ADMIN",
        parameters={"customer_id": 101, "amount": 500, "reason": "Customer satisfaction"},
        tool="refund_customer",
    )
    result = verifier.verify(proposal)
    print(f"Proposed: {proposal.action}")
    print(f"Amount: ₹{proposal.parameters['amount']:,.2f}")
    print(f"Decision: {result.decision.value}")
    print(f"Reasons: {', '.join(result.reasons)}")

    if result.decision.value == "ALLOW":
        tool_result = tools.refund_customer(
            customer_id=proposal.parameters["customer_id"],
            amount=proposal.parameters["amount"],
            reason=proposal.parameters["reason"],
        )
        print(f"Executed: {tool_result.message}")
        print(f"Result: {tool_result.data}")
    print()


if __name__ == "__main__":
    main()
