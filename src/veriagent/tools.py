"""Business tool functions that interact with the synthetic database.

These tools are the actual business operations that AI agents can perform.
They must NEVER be called directly by agents—all calls go through VeriAgent verification.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .repository import Customer, Invoice, NotFoundError, Repository, ValidationError


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Structured result from a tool execution."""

    success: bool
    data: Any
    message: str


@dataclass(frozen=True, slots=True)
class EmailRecord:
    """Record of a simulated email."""

    email_id: int
    recipient: str
    subject: str
    body: str
    sent_at: str


class BusinessTools:
    """Collection of business operations available to AI agents."""

    def __init__(self, database_path: str | Path = "data/veriagent.db") -> None:
        self.repository = Repository(database_path)
        self.database_path = Path(database_path)

    def get_customer(self, customer_id: int) -> ToolResult:
        """Retrieve customer information by ID."""
        try:
            customer = self.repository.get_customer(customer_id)
            return ToolResult(
                success=True,
                data=customer,
                message=f"Customer {customer_id} retrieved successfully",
            )
        except NotFoundError as e:
            return ToolResult(success=False, data=None, message=str(e))

    def get_invoice(self, invoice_id: str) -> ToolResult:
        """Retrieve invoice information by ID."""
        try:
            invoice = self.repository.get_invoice(invoice_id)
            return ToolResult(
                success=True,
                data=invoice,
                message=f"Invoice {invoice_id} retrieved successfully",
            )
        except NotFoundError as e:
            return ToolResult(success=False, data=None, message=str(e))

    def calculate_balance(self, customer_id: int) -> ToolResult:
        """Calculate outstanding balance for a customer."""
        try:
            balance = self.repository.calculate_balance(customer_id)
            return ToolResult(
                success=True,
                data={"customer_id": customer_id, "balance": balance},
                message=f"Balance calculated: ₹{balance:.2f}",
            )
        except NotFoundError as e:
            return ToolResult(success=False, data=None, message=str(e))

    def create_invoice(
        self, customer_id: int, amount: float, due_date: str, status: str = "OPEN"
    ) -> ToolResult:
        """Create a new invoice for a customer."""
        try:
            # Generate invoice ID
            invoice_id = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            invoice = self.repository.create_invoice(
                invoice_id=invoice_id,
                customer_id=customer_id,
                amount=amount,
                due_date=due_date,
                status=status,
            )
            return ToolResult(
                success=True,
                data=invoice,
                message=f"Invoice {invoice_id} created for ₹{amount:.2f}",
            )
        except (NotFoundError, ValidationError) as e:
            return ToolResult(success=False, data=None, message=str(e))

    def update_customer(self, customer_id: int, **fields: Any) -> ToolResult:
        """Update customer information."""
        try:
            updated_customer = self.repository.update_customer(customer_id, **fields)
            return ToolResult(
                success=True,
                data=updated_customer,
                message=f"Customer {customer_id} updated successfully",
            )
        except (NotFoundError, ValidationError) as e:
            return ToolResult(success=False, data=None, message=str(e))

    def refund_customer(self, customer_id: int, amount: float, reason: str) -> ToolResult:
        """Process a refund for a customer.

        This is a high-impact operation that should always go through strict verification.
        """
        try:
            # Verify customer exists
            customer = self.repository.get_customer(customer_id)

            # Validate amount
            if amount <= 0:
                raise ValidationError("Refund amount must be positive")

            # In a real system, this would:
            # 1. Find the original payment/invoice
            # 2. Create a refund transaction
            # 3. Update payment status
            # 4. Possibly adjust invoice status
            # 5. Trigger accounting entries

            # For this prototype, we'll create a payment record with REFUNDED status
            # and log the action
            refund_id = f"REF-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Get customer's invoices to validate refund is reasonable
            invoices = self.repository.get_customer_invoices(customer_id)
            if not invoices:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"No invoices found for customer {customer_id}",
                )

            # Create a refund record (simplified - using payments table with negative semantics)
            # In production, you'd have a separate refunds table
            conn = sqlite3.connect(self.database_path)
            try:
                conn.execute(
                    """
                    INSERT INTO payments (payment_id, invoice_id, amount, payment_date, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (refund_id, invoices[0].invoice_id, amount, datetime.now().isoformat(), "REFUNDED"),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

            return ToolResult(
                success=True,
                data={
                    "refund_id": refund_id,
                    "customer_id": customer_id,
                    "customer_name": customer.name,
                    "amount": amount,
                    "reason": reason,
                },
                message=f"Refund of ₹{amount:.2f} processed for {customer.name}",
            )
        except (NotFoundError, ValidationError) as e:
            return ToolResult(success=False, data=None, message=str(e))

    def send_email(self, recipient: str, subject: str, body: str) -> ToolResult:
        """Simulate sending an email by storing it in the database.

        In production, this would integrate with an email service.
        For this prototype, we log emails to demonstrate the tool.
        """
        try:
            # Validate email format (basic check)
            if "@" not in recipient:
                raise ValidationError(f"Invalid email address: {recipient}")

            if not subject.strip():
                raise ValidationError("Email subject cannot be empty")

            # Store simulated email in a simple table
            # We'll create this table on first use
            conn = sqlite3.connect(self.database_path)
            try:
                # Create emails table if it doesn't exist
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS emails (
                        email_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recipient TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        body TEXT NOT NULL,
                        sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                cursor = conn.execute(
                    "INSERT INTO emails (recipient, subject, body) VALUES (?, ?, ?)",
                    (recipient, subject, body),
                )
                email_id = cursor.lastrowid
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

            return ToolResult(
                success=True,
                data={
                    "email_id": email_id,
                    "recipient": recipient,
                    "subject": subject,
                },
                message=f"Email sent to {recipient}",
            )
        except (ValidationError, sqlite3.Error) as e:
            return ToolResult(success=False, data=None, message=str(e))

    def get_simulated_emails(self, limit: int = 10) -> ToolResult:
        """Retrieve recent simulated emails (for testing/demo purposes)."""
        try:
            conn = sqlite3.connect(self.database_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT email_id, recipient, subject, body, sent_at FROM emails ORDER BY email_id DESC LIMIT ?",
                    (limit,),
                )
                emails = [
                    EmailRecord(
                        email_id=row["email_id"],
                        recipient=row["recipient"],
                        subject=row["subject"],
                        body=row["body"],
                        sent_at=row["sent_at"],
                    )
                    for row in cursor.fetchall()
                ]
            finally:
                conn.close()

            return ToolResult(
                success=True,
                data=emails,
                message=f"Retrieved {len(emails)} email(s)",
            )
        except sqlite3.Error as e:
            return ToolResult(success=False, data=None, message=str(e))
