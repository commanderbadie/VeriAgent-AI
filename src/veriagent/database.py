"""Synthetic SQLite database used by the controlled business environment."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CLOSED'))
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    amount REAL NOT NULL CHECK (amount >= 0),
    due_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('DRAFT', 'OPEN', 'PAID', 'OVERDUE', 'VOID'))
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
    amount REAL NOT NULL CHECK (amount > 0),
    payment_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'COMPLETED', 'FAILED', 'REFUNDED'))
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('READ_ONLY', 'AGENT', 'ADMIN'))
);

CREATE TABLE IF NOT EXISTS policies (
    policy_id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    amount_limit REAL,
    requires_approval INTEGER NOT NULL DEFAULT 0 CHECK (requires_approval IN (0, 1))
);

CREATE TABLE IF NOT EXISTS action_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    action TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('ALLOW', 'REVIEW', 'BLOCK')),
    reason TEXT NOT NULL,
    risk_score REAL
);
"""

SYNTHETIC_SEED = """
INSERT OR IGNORE INTO customers VALUES
    (101, 'Aarav Demo', 'aarav@example.test', '+91-00000-00101', 'ACTIVE'),
    (102, 'Diya Demo', 'diya@example.test', '+91-00000-00102', 'ACTIVE');
INSERT OR IGNORE INTO invoices VALUES
    ('INV-1001', 101, 4500.00, '2026-10-01', 'OPEN'),
    ('INV-1002', 102, 12000.00, '2026-09-01', 'OVERDUE');
INSERT OR IGNORE INTO users VALUES
    (1, 'READ_ONLY'), (2, 'AGENT'), (3, 'ADMIN');
INSERT OR IGNORE INTO policies VALUES
    (1, 'refund_customer', 10000.00, 1);
"""


def initialize_database(path: str | Path = "data/veriagent.db") -> Path:
    """Create and seed the synthetic database, returning its path."""

    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)
        connection.executescript(SYNTHETIC_SEED)
    return database_path
