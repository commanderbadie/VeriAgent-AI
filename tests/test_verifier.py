import tempfile
import unittest
from pathlib import Path

from veriagent import Decision, ProposedAction, RuleVerifier
from veriagent.database import initialize_database


class RuleVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary database for each test
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        initialize_database(self.db_path)
        self.verifier = RuleVerifier(database_path=self.db_path)

    def test_read_only_user_can_read_customer(self) -> None:
        result = self.verifier.verify(
            ProposedAction("get_customer", "READ_ONLY", {"customer_id": 101})
        )
        self.assertEqual(result.decision, Decision.ALLOW)

    def test_read_only_user_cannot_update_customer(self) -> None:
        result = self.verifier.verify(
            ProposedAction("update_customer", "READ_ONLY", {"customer_id": 101})
        )
        self.assertEqual(result.decision, Decision.BLOCK)

    def test_missing_customer_is_blocked(self) -> None:
        result = self.verifier.verify(
            ProposedAction("get_customer", "AGENT", {"customer_id": 999})
        )
        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertFalse(result.checks["entity_reference"])

    def test_missing_invoice_is_blocked(self) -> None:
        result = self.verifier.verify(
            ProposedAction("get_invoice", "AGENT", {"invoice_id": "INV-9999"})
        )
        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertFalse(result.checks["entity_reference"])

    def test_existing_customer_passes_entity_check(self) -> None:
        result = self.verifier.verify(
            ProposedAction("get_customer", "AGENT", {"customer_id": 101})
        )
        self.assertEqual(result.decision, Decision.ALLOW)
        self.assertTrue(result.checks["entity_reference"])

    def test_large_refund_requires_review(self) -> None:
        result = self.verifier.verify(
            ProposedAction("refund_customer", "ADMIN", {"customer_id": 101, "amount": 20_000})
        )
        self.assertEqual(result.decision, Decision.REVIEW)

    def test_invalid_refund_amount_is_blocked(self) -> None:
        result = self.verifier.verify(
            ProposedAction("refund_customer", "ADMIN", {"customer_id": 101, "amount": -1})
        )
        self.assertEqual(result.decision, Decision.BLOCK)

    def test_refund_for_missing_customer_is_blocked(self) -> None:
        result = self.verifier.verify(
            ProposedAction("refund_customer", "ADMIN", {"customer_id": 999, "amount": 1000})
        )
        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertFalse(result.checks["entity_reference"])

    def test_small_refund_is_allowed(self) -> None:
        result = self.verifier.verify(
            ProposedAction("refund_customer", "ADMIN", {"customer_id": 101, "amount": 500})
        )
        self.assertEqual(result.decision, Decision.ALLOW)


if __name__ == "__main__":
    unittest.main()
