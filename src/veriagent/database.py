"""Synthetic SQLite database used by the controlled business environment."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


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
-- Customers 101-120 to match dataset generator range
INSERT OR IGNORE INTO customers VALUES
    (101, 'Aarav Demo', 'aarav@example.test', '+91-00000-00101', 'ACTIVE'),
    (102, 'Diya Demo', 'diya@example.test', '+91-00000-00102', 'ACTIVE'),
    (103, 'Arjun Kumar', 'arjun.k@example.test', '+91-00000-00103', 'ACTIVE'),
    (104, 'Priya Singh', 'priya.s@example.test', '+91-00000-00104', 'ACTIVE'),
    (105, 'Rohan Patel', 'rohan.p@example.test', '+91-00000-00105', 'ACTIVE'),
    (106, 'Ananya Sharma', 'ananya.s@example.test', '+91-00000-00106', 'ACTIVE'),
    (107, 'Vihaan Reddy', 'vihaan.r@example.test', '+91-00000-00107', 'ACTIVE'),
    (108, 'Ishita Gupta', 'ishita.g@example.test', '+91-00000-00108', 'ACTIVE'),
    (109, 'Aditya Mehta', 'aditya.m@example.test', '+91-00000-00109', 'ACTIVE'),
    (110, 'Saanvi Joshi', 'saanvi.j@example.test', '+91-00000-00110', 'ACTIVE'),
    (111, 'Kabir Verma', 'kabir.v@example.test', '+91-00000-00111', 'ACTIVE'),
    (112, 'Myra Kapoor', 'myra.k@example.test', '+91-00000-00112', 'ACTIVE'),
    (113, 'Reyansh Nair', 'reyansh.n@example.test', '+91-00000-00113', 'ACTIVE'),
    (114, 'Aadhya Das', 'aadhya.d@example.test', '+91-00000-00114', 'ACTIVE'),
    (115, 'Ayaan Shah', 'ayaan.s@example.test', '+91-00000-00115', 'ACTIVE'),
    (116, 'Kiara Bose', 'kiara.b@example.test', '+91-00000-00116', 'ACTIVE'),
    (117, 'Vivaan Iyer', 'vivaan.i@example.test', '+91-00000-00117', 'ACTIVE'),
    (118, 'Aanya Desai', 'aanya.d@example.test', '+91-00000-00118', 'ACTIVE'),
    (119, 'Shaurya Pillai', 'shaurya.p@example.test', '+91-00000-00119', 'ACTIVE'),
    (120, 'Navya Menon', 'navya.m@example.test', '+91-00000-00120', 'ACTIVE');

-- Invoices for each customer (INV-1001 to INV-1020)
INSERT OR IGNORE INTO invoices VALUES
    ('INV-1001', 101, 4500.00, '2026-10-01', 'OPEN'),
    ('INV-1002', 102, 12000.00, '2026-09-01', 'OVERDUE'),
    ('INV-1003', 103, 2800.00, '2026-10-15', 'OPEN'),
    ('INV-1004', 104, 6700.00, '2026-09-20', 'OPEN'),
    ('INV-1005', 105, 3400.00, '2026-10-05', 'PAID'),
    ('INV-1006', 106, 8900.00, '2026-09-15', 'OPEN'),
    ('INV-1007', 107, 5200.00, '2026-10-10', 'OPEN'),
    ('INV-1008', 108, 4100.00, '2026-09-25', 'OVERDUE'),
    ('INV-1009', 109, 7300.00, '2026-10-08', 'OPEN'),
    ('INV-1010', 110, 3900.00, '2026-09-30', 'PAID'),
    ('INV-1011', 111, 5600.00, '2026-10-12', 'OPEN'),
    ('INV-1012', 112, 9200.00, '2026-09-18', 'OPEN'),
    ('INV-1013', 113, 4800.00, '2026-10-03', 'PAID'),
    ('INV-1014', 114, 6100.00, '2026-09-22', 'OPEN'),
    ('INV-1015', 115, 3700.00, '2026-10-14', 'OPEN'),
    ('INV-1016', 116, 7800.00, '2026-09-28', 'OVERDUE'),
    ('INV-1017', 117, 5400.00, '2026-10-06', 'OPEN'),
    ('INV-1018', 118, 4300.00, '2026-09-19', 'PAID'),
    ('INV-1019', 119, 8500.00, '2026-10-11', 'OPEN'),
    ('INV-1020', 120, 6900.00, '2026-09-24', 'OPEN');

-- User roles
INSERT OR IGNORE INTO users VALUES
    (1, 'READ_ONLY'), (2, 'AGENT'), (3, 'ADMIN');

-- Policies
INSERT OR IGNORE INTO policies VALUES
    (1, 'refund_customer', 10000.00, 1);
"""


def initialize_database(path: str | Path = "data/veriagent.db") -> Path:
    """Create and seed the synthetic database, returning its path."""

    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with _db_connection(database_path) as connection:
        connection.executescript(SCHEMA)
        connection.executescript(SYNTHETIC_SEED)
    return database_path
