"""Tests for the business tools layer."""

import tempfile
import unittest
from pathlib import Path

from veriagent import BusinessTools
from veriagent.database import initialize_database


class BusinessToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        """Create a temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        initialize_database(self.db_path)
        self.tools = BusinessTools(self.db_path)

    def test_get_customer_success(self) -> None:
        result = self.tools.get_customer(101)
        self.assertTrue(result.success)
        self.assertEqual(result.data.customer_id, 101)
        self.assertEqual(result.data.name, "Aarav Demo")

    def test_get_customer_not_found(self) -> None:
        result = self.tools.get_customer(999)
        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertIn("not found", result.message)

    def test_get_invoice_success(self) -> None:
        result = self.tools.get_invoice("INV-1001")
        self.assertTrue(result.success)
        self.assertEqual(result.data.invoice_id, "INV-1001")
        self.assertEqual(result.data.amount, 4500.00)

    def test_get_invoice_not_found(self) -> None:
        result = self.tools.get_invoice("INV-9999")
        self.assertFalse(result.success)
        self.assertIsNone(result.data)

    def test_calculate_balance_success(self) -> None:
        result = self.tools.calculate_balance(101)
        self.assertTrue(result.success)
        self.assertEqual(result.data["customer_id"], 101)
        self.assertEqual(result.data["balance"], 4500.00)

    def test_calculate_balance_for_missing_customer(self) -> None:
        result = self.tools.calculate_balance(999)
        self.assertFalse(result.success)

    def test_create_invoice_success(self) -> None:
        result = self.tools.create_invoice(
            customer_id=101,
            amount=2500.00,
            due_date="2026-12-31",
        )
        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data.amount, 2500.00)
        self.assertIn("created", result.message)

    def test_create_invoice_for_missing_customer(self) -> None:
        result = self.tools.create_invoice(
            customer_id=999,
            amount=1000,
            due_date="2026-12-31",
        )
        self.assertFalse(result.success)

    def test_create_invoice_with_negative_amount(self) -> None:
        result = self.tools.create_invoice(
            customer_id=101,
            amount=-100,
            due_date="2026-12-31",
        )
        self.assertFalse(result.success)

    def test_update_customer_success(self) -> None:
        result = self.tools.update_customer(101, name="Updated Name", phone="+91-11111-11111")
        self.assertTrue(result.success)
        self.assertEqual(result.data.name, "Updated Name")
        self.assertEqual(result.data.phone, "+91-11111-11111")

    def test_update_customer_with_invalid_field(self) -> None:
        result = self.tools.update_customer(101, invalid_field="test")
        self.assertFalse(result.success)
        self.assertIn("Invalid", result.message)

    def test_update_customer_not_found(self) -> None:
        result = self.tools.update_customer(999, name="Test")
        self.assertFalse(result.success)

    def test_refund_customer_success(self) -> None:
        result = self.tools.refund_customer(
            customer_id=101,
            amount=500.00,
            reason="Customer satisfaction",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["customer_id"], 101)
        self.assertEqual(result.data["amount"], 500.00)
        self.assertIn("refund_id", result.data)

    def test_refund_customer_not_found(self) -> None:
        result = self.tools.refund_customer(
            customer_id=999,
            amount=100,
            reason="Test",
        )
        self.assertFalse(result.success)

    def test_refund_with_negative_amount(self) -> None:
        result = self.tools.refund_customer(
            customer_id=101,
            amount=-100,
            reason="Test",
        )
        self.assertFalse(result.success)
        self.assertIn("positive", result.message)

    def test_refund_with_zero_amount(self) -> None:
        result = self.tools.refund_customer(
            customer_id=101,
            amount=0,
            reason="Test",
        )
        self.assertFalse(result.success)

    def test_send_email_success(self) -> None:
        result = self.tools.send_email(
            recipient="test@example.com",
            subject="Test Email",
            body="This is a test email.",
        )
        self.assertTrue(result.success)
        self.assertIn("email_id", result.data)
        self.assertEqual(result.data["recipient"], "test@example.com")

    def test_send_email_invalid_address(self) -> None:
        result = self.tools.send_email(
            recipient="invalid-email",
            subject="Test",
            body="Body",
        )
        self.assertFalse(result.success)
        self.assertIn("Invalid", result.message)

    def test_send_email_empty_subject(self) -> None:
        result = self.tools.send_email(
            recipient="test@example.com",
            subject="",
            body="Body",
        )
        self.assertFalse(result.success)
        self.assertIn("empty", result.message)

    def test_get_simulated_emails(self) -> None:
        # Send a few test emails
        self.tools.send_email("user1@test.com", "Subject 1", "Body 1")
        self.tools.send_email("user2@test.com", "Subject 2", "Body 2")

        result = self.tools.get_simulated_emails(limit=10)
        self.assertTrue(result.success)
        self.assertGreaterEqual(len(result.data), 2)
        self.assertEqual(result.data[0].recipient, "user2@test.com")  # most recent first

    def test_multiple_operations_in_sequence(self) -> None:
        """Test a realistic workflow."""
        # 1. Get customer
        customer_result = self.tools.get_customer(101)
        self.assertTrue(customer_result.success)

        # 2. Calculate balance
        balance_result = self.tools.calculate_balance(101)
        self.assertTrue(balance_result.success)

        # 3. Create invoice
        invoice_result = self.tools.create_invoice(101, 1000.00, "2026-12-31")
        self.assertTrue(invoice_result.success)

        # 4. Send email notification
        email_result = self.tools.send_email(
            customer_result.data.email,
            "New Invoice",
            f"Invoice {invoice_result.data.invoice_id} has been created.",
        )
        self.assertTrue(email_result.success)


if __name__ == "__main__":
    unittest.main()
