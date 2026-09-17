"""Database repository for safe, parameterized access to synthetic data."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator


class NotFoundError(Exception):
    """Entity does not exist in the database."""


class ValidationError(Exception):
    """Invalid input or constraint violation."""


@dataclass(frozen=True, slots=True)
class Customer:
    """Customer entity from the database."""

    customer_id: int
    name: str
    email: str
    phone: str | None
    status: str


@dataclass(frozen=True, slots=True)
class Invoice:
    """Invoice entity from the database."""

    invoice_id: str
    customer_id: int
    amount: float
    due_date: str
    status: str


@dataclass(frozen=True, slots=True)
class Payment:
    """Payment entity from the database."""

    payment_id: str
    invoice_id: str
    amount: float
    payment_date: str
    status: str


class Repository:
    """Safe database access layer with parameterized queries and transactions."""

    def __init__(self, database_path: str | Path = "data/veriagent.db") -> None:
        self.database_path = Path(database_path)
        if not self.database_path.exists():
            raise FileNotFoundError(f"Database not found: {self.database_path}")

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections with proper cleanup."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_customer(self, customer_id: int) -> Customer:
        """Retrieve a customer by ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT customer_id, name, email, phone, status FROM customers WHERE customer_id = ?",
                (customer_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Customer {customer_id} not found")
            return Customer(
                customer_id=row["customer_id"],
                name=row["name"],
                email=row["email"],
                phone=row["phone"],
                status=row["status"],
            )

    def customer_exists(self, customer_id: int) -> bool:
        """Check if a customer exists."""
        try:
            self.get_customer(customer_id)
            return True
        except NotFoundError:
            return False

    def get_invoice(self, invoice_id: str) -> Invoice:
        """Retrieve an invoice by ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT invoice_id, customer_id, amount, due_date, status FROM invoices WHERE invoice_id = ?",
                (invoice_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Invoice {invoice_id} not found")
            return Invoice(
                invoice_id=row["invoice_id"],
                customer_id=row["customer_id"],
                amount=row["amount"],
                due_date=row["due_date"],
                status=row["status"],
            )

    def invoice_exists(self, invoice_id: str) -> bool:
        """Check if an invoice exists."""
        try:
            self.get_invoice(invoice_id)
            return True
        except NotFoundError:
            return False

    def get_customer_invoices(self, customer_id: int) -> list[Invoice]:
        """Retrieve all invoices for a customer."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT invoice_id, customer_id, amount, due_date, status FROM invoices WHERE customer_id = ?",
                (customer_id,),
            )
            return [
                Invoice(
                    invoice_id=row["invoice_id"],
                    customer_id=row["customer_id"],
                    amount=row["amount"],
                    due_date=row["due_date"],
                    status=row["status"],
                )
                for row in cursor.fetchall()
            ]

    def calculate_balance(self, customer_id: int) -> float:
        """Calculate outstanding balance (unpaid invoices) for a customer."""
        if not self.customer_exists(customer_id):
            raise NotFoundError(f"Customer {customer_id} not found")

        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) as total
                FROM invoices
                WHERE customer_id = ? AND status IN ('OPEN', 'OVERDUE')
                """,
                (customer_id,),
            )
            row = cursor.fetchone()
            return float(row["total"])

    def create_invoice(
        self, invoice_id: str, customer_id: int, amount: float, due_date: str, status: str = "OPEN"
    ) -> Invoice:
        """Create a new invoice."""
        if not self.customer_exists(customer_id):
            raise NotFoundError(f"Customer {customer_id} not found")

        if amount < 0:
            raise ValidationError("Invoice amount must be non-negative")

        valid_statuses = {"DRAFT", "OPEN", "PAID", "OVERDUE", "VOID"}
        if status not in valid_statuses:
            raise ValidationError(f"Invalid invoice status: {status}")

        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO invoices (invoice_id, customer_id, amount, due_date, status) VALUES (?, ?, ?, ?, ?)",
                    (invoice_id, customer_id, amount, due_date, status),
                )
            except sqlite3.IntegrityError as e:
                raise ValidationError(f"Invoice creation failed: {e}")

        return self.get_invoice(invoice_id)

    def update_customer(self, customer_id: int, **fields: Any) -> Customer:
        """Update customer fields. Only name, email, phone, and status are allowed."""
        allowed_fields = {"name", "email", "phone", "status"}
        invalid_fields = set(fields.keys()) - allowed_fields
        if invalid_fields:
            raise ValidationError(f"Invalid update fields: {invalid_fields}")

        if not fields:
            raise ValidationError("No fields to update")

        # Validate status if provided
        if "status" in fields:
            valid_statuses = {"ACTIVE", "SUSPENDED", "CLOSED"}
            if fields["status"] not in valid_statuses:
                raise ValidationError(f"Invalid customer status: {fields['status']}")

        # Build dynamic UPDATE query
        set_clause = ", ".join(f"{field} = ?" for field in fields.keys())
        values = list(fields.values()) + [customer_id]

        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE customers SET {set_clause} WHERE customer_id = ?",
                values,
            )
            if cursor.rowcount == 0:
                raise NotFoundError(f"Customer {customer_id} not found")

        return self.get_customer(customer_id)

    def create_payment(
        self, payment_id: str, invoice_id: str, amount: float, payment_date: str
    ) -> Payment:
        """Create a payment record."""
        if not self.invoice_exists(invoice_id):
            raise NotFoundError(f"Invoice {invoice_id} not found")

        if amount <= 0:
            raise ValidationError("Payment amount must be positive")

        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO payments (payment_id, invoice_id, amount, payment_date, status) VALUES (?, ?, ?, ?, ?)",
                    (payment_id, invoice_id, amount, payment_date, "COMPLETED"),
                )
            except sqlite3.IntegrityError as e:
                raise ValidationError(f"Payment creation failed: {e}")

            # Retrieve and return the payment within the same connection
            cursor = conn.execute(
                "SELECT payment_id, invoice_id, amount, payment_date, status FROM payments WHERE payment_id = ?",
                (payment_id,),
            )
            row = cursor.fetchone()
            return Payment(
                payment_id=row["payment_id"],
                invoice_id=row["invoice_id"],
                amount=row["amount"],
                payment_date=row["payment_date"],
                status=row["status"],
            )

    def log_action(
        self,
        user_id: int | None,
        action: str,
        parameters_json: str,
        decision: str,
        reason: str,
        risk_score: float | None = None,
    ) -> int:
        """Log an action to the audit trail."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO action_logs (user_id, action, parameters_json, decision, reason, risk_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, action, parameters_json, decision, reason, risk_score),
            )
            return cursor.lastrowid
