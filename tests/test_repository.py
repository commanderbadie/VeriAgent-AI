"""Tests for the database repository layer."""

import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from veriagent import Customer, Invoice, NotFoundError, Repository, ValidationError
from veriagent.database import initialize_database


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


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        """Create a temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        initialize_database(self.db_path)
        self.repo = Repository(self.db_path)

    def test_get_existing_customer(self) -> None:
        customer = self.repo.get_customer(101)
        self.assertEqual(customer.customer_id, 101)
        self.assertEqual(customer.name, "Aarav Demo")
        self.assertEqual(customer.status, "ACTIVE")

    def test_get_missing_customer_raises_error(self) -> None:
        with self.assertRaises(NotFoundError) as context:
            self.repo.get_customer(999)
        self.assertIn("Customer 999 not found", str(context.exception))

    def test_customer_exists(self) -> None:
        self.assertTrue(self.repo.customer_exists(101))
        self.assertFalse(self.repo.customer_exists(999))

    def test_get_existing_invoice(self) -> None:
        invoice = self.repo.get_invoice("INV-1001")
        self.assertEqual(invoice.invoice_id, "INV-1001")
        self.assertEqual(invoice.customer_id, 101)
        self.assertEqual(invoice.amount, 4500.00)

    def test_get_missing_invoice_raises_error(self) -> None:
        with self.assertRaises(NotFoundError):
            self.repo.get_invoice("INV-9999")

    def test_invoice_exists(self) -> None:
        self.assertTrue(self.repo.invoice_exists("INV-1001"))
        self.assertFalse(self.repo.invoice_exists("INV-9999"))

    def test_calculate_balance_for_customer_with_open_invoices(self) -> None:
        # Customer 101 has INV-1001 (4500) with status OPEN
        # Customer 102 has INV-1002 (12000) with status OVERDUE
        balance_101 = self.repo.calculate_balance(101)
        self.assertEqual(balance_101, 4500.00)

        balance_102 = self.repo.calculate_balance(102)
        self.assertEqual(balance_102, 12000.00)

    def test_calculate_balance_for_missing_customer(self) -> None:
        with self.assertRaises(NotFoundError):
            self.repo.calculate_balance(999)

    def test_create_invoice_success(self) -> None:
        invoice = self.repo.create_invoice(
            invoice_id="INV-TEST-001",
            customer_id=101,
            amount=1500.00,
            due_date="2026-12-31",
            status="DRAFT",
        )
        self.assertEqual(invoice.invoice_id, "INV-TEST-001")
        self.assertEqual(invoice.amount, 1500.00)
        self.assertEqual(invoice.status, "DRAFT")

    def test_create_invoice_for_missing_customer(self) -> None:
        with self.assertRaises(NotFoundError):
            self.repo.create_invoice(
                invoice_id="INV-BAD",
                customer_id=999,
                amount=100,
                due_date="2026-12-31",
            )

    def test_create_invoice_with_negative_amount(self) -> None:
        with self.assertRaises(ValidationError):
            self.repo.create_invoice(
                invoice_id="INV-NEG",
                customer_id=101,
                amount=-100,
                due_date="2026-12-31",
            )

    def test_create_invoice_with_invalid_status(self) -> None:
        with self.assertRaises(ValidationError):
            self.repo.create_invoice(
                invoice_id="INV-STATUS",
                customer_id=101,
                amount=100,
                due_date="2026-12-31",
                status="INVALID",
            )

    def test_update_customer_success(self) -> None:
        updated = self.repo.update_customer(101, name="New Name", phone="+91-99999-99999")
        self.assertEqual(updated.name, "New Name")
        self.assertEqual(updated.phone, "+91-99999-99999")
        self.assertEqual(updated.email, "aarav@example.test")  # unchanged

    def test_update_customer_with_invalid_field(self) -> None:
        with self.assertRaises(ValidationError) as context:
            self.repo.update_customer(101, invalid_field="test")
        self.assertIn("Invalid update fields", str(context.exception))

    def test_update_customer_with_no_fields(self) -> None:
        with self.assertRaises(ValidationError):
            self.repo.update_customer(101)

    def test_update_missing_customer(self) -> None:
        with self.assertRaises(NotFoundError):
            self.repo.update_customer(999, name="Test")

    def test_update_customer_status(self) -> None:
        updated = self.repo.update_customer(101, status="SUSPENDED")
        self.assertEqual(updated.status, "SUSPENDED")

    def test_update_customer_with_invalid_status(self) -> None:
        with self.assertRaises(ValidationError):
            self.repo.update_customer(101, status="BANNED")

    def test_get_customer_invoices(self) -> None:
        invoices = self.repo.get_customer_invoices(101)
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices[0].invoice_id, "INV-1001")

    def test_get_customer_invoices_empty(self) -> None:
        # Add a customer with no invoices
        with _db_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO customers VALUES (999, 'Test', 'test@example.test', NULL, 'ACTIVE')"
            )
        invoices = self.repo.get_customer_invoices(999)
        self.assertEqual(len(invoices), 0)

    def test_create_payment_success(self) -> None:
        payment = self.repo.create_payment(
            payment_id="PAY-001",
            invoice_id="INV-1001",
            amount=4500.00,
            payment_date="2026-09-17",
        )
        self.assertEqual(payment.payment_id, "PAY-001")
        self.assertEqual(payment.amount, 4500.00)
        self.assertEqual(payment.status, "COMPLETED")

    def test_create_payment_for_missing_invoice(self) -> None:
        with self.assertRaises(NotFoundError):
            self.repo.create_payment(
                payment_id="PAY-BAD",
                invoice_id="INV-9999",
                amount=100,
                payment_date="2026-09-17",
            )

    def test_create_payment_with_invalid_amount(self) -> None:
        with self.assertRaises(ValidationError):
            self.repo.create_payment(
                payment_id="PAY-NEG",
                invoice_id="INV-1001",
                amount=-100,
                payment_date="2026-09-17",
            )

    def test_log_action(self) -> None:
        log_id = self.repo.log_action(
            user_id=2,
            action="refund_customer",
            parameters_json='{"customer_id": 101, "amount": 500}',
            decision="ALLOW",
            reason="All checks passed",
            risk_score=0.12,
        )
        self.assertIsInstance(log_id, int)
        self.assertGreater(log_id, 0)

    def test_transaction_rollback_on_error(self) -> None:
        """Test that failed operations don't leave partial data."""
        initial_count = 0
        with _db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM customers")
            initial_count = cursor.fetchone()[0]

        # Try to update with invalid field (should fail)
        with self.assertRaises(ValidationError):
            self.repo.update_customer(101, invalid="test")

        # Verify customer count unchanged
        with _db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM customers")
            final_count = cursor.fetchone()[0]
        self.assertEqual(initial_count, final_count)


if __name__ == "__main__":
    unittest.main()
