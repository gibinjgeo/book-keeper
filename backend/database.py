"""
SQLite database connection and schema management.
Mirrors the better-sqlite3 schema from the original Frappe Books project.
"""
import sqlite3
import os
from pathlib import Path

STORAGE_DIR = Path(__file__).parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


def get_db_path(company: str = "default") -> str:
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in company)
    return str(STORAGE_DIR / f"{safe_name}.db")


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounting_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            company_name TEXT NOT NULL DEFAULT 'My Company',
            country TEXT DEFAULT 'United States',
            currency TEXT DEFAULT 'USD',
            fiscal_year_start TEXT DEFAULT '01-01',
            fiscal_year_end TEXT DEFAULT '12-31',
            round_off_account TEXT,
            write_off_account TEXT,
            discount_account TEXT,
            bank_account TEXT,
            setup_done INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS number_series (
            name TEXT PRIMARY KEY,
            reference_type TEXT,
            current INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS account (
            name TEXT PRIMARY KEY,
            root_type TEXT NOT NULL,
            account_type TEXT DEFAULT '',
            parent_account TEXT,
            is_group INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS party (
            name TEXT PRIMARY KEY,
            role TEXT NOT NULL DEFAULT 'Both',
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            country TEXT DEFAULT '',
            zip_code TEXT DEFAULT '',
            default_account TEXT REFERENCES account(name),
            currency TEXT DEFAULT 'USD',
            tax_id TEXT DEFAULT '',
            loyalty_points INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS item_group (
            name TEXT PRIMARY KEY,
            parent_group TEXT
        );

        CREATE TABLE IF NOT EXISTS tax (
            name TEXT PRIMARY KEY,
            rate REAL DEFAULT 0,
            account TEXT REFERENCES account(name)
        );

        CREATE TABLE IF NOT EXISTS item (
            name TEXT PRIMARY KEY,
            item_code TEXT DEFAULT '',
            item_group TEXT REFERENCES item_group(name),
            for_purpose TEXT DEFAULT 'Both',
            item_type TEXT DEFAULT 'Product',
            unit TEXT DEFAULT 'Unit',
            rate REAL DEFAULT 0,
            description TEXT DEFAULT '',
            income_account TEXT REFERENCES account(name),
            expense_account TEXT REFERENCES account(name),
            tax TEXT REFERENCES tax(name),
            track_item INTEGER DEFAULT 0,
            barcode TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sales_invoice (
            name TEXT PRIMARY KEY,
            party TEXT REFERENCES party(name),
            date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Draft',
            account TEXT,
            net_total REAL DEFAULT 0,
            tax_total REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            grand_total REAL DEFAULT 0,
            outstanding_amount REAL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            exchange_rate REAL DEFAULT 1,
            is_return INTEGER DEFAULT 0,
            return_against TEXT,
            user_remark TEXT DEFAULT '',
            number_series TEXT DEFAULT 'SINV-',
            created_at TEXT DEFAULT (datetime('now')),
            submitted_at TEXT,
            cancelled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sales_invoice_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent TEXT NOT NULL REFERENCES sales_invoice(name),
            item TEXT REFERENCES item(name),
            description TEXT DEFAULT '',
            account TEXT REFERENCES account(name),
            quantity REAL DEFAULT 1,
            rate REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            tax_rate REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            tax_account TEXT REFERENCES account(name)
        );

        CREATE TABLE IF NOT EXISTS purchase_invoice (
            name TEXT PRIMARY KEY,
            party TEXT REFERENCES party(name),
            date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Draft',
            account TEXT,
            net_total REAL DEFAULT 0,
            tax_total REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            grand_total REAL DEFAULT 0,
            outstanding_amount REAL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            exchange_rate REAL DEFAULT 1,
            is_return INTEGER DEFAULT 0,
            return_against TEXT,
            user_remark TEXT DEFAULT '',
            number_series TEXT DEFAULT 'PINV-',
            created_at TEXT DEFAULT (datetime('now')),
            submitted_at TEXT,
            cancelled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS purchase_invoice_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent TEXT NOT NULL REFERENCES purchase_invoice(name),
            item TEXT REFERENCES item(name),
            description TEXT DEFAULT '',
            account TEXT REFERENCES account(name),
            quantity REAL DEFAULT 1,
            rate REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            tax_rate REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            tax_account TEXT REFERENCES account(name)
        );

        CREATE TABLE IF NOT EXISTS payment (
            name TEXT PRIMARY KEY,
            party TEXT REFERENCES party(name),
            date TEXT,
            payment_type TEXT NOT NULL DEFAULT 'Receive',
            payment_method TEXT DEFAULT 'Cash',
            amount REAL DEFAULT 0,
            account TEXT REFERENCES account(name),
            payment_account TEXT REFERENCES account(name),
            status TEXT DEFAULT 'Draft',
            user_remark TEXT DEFAULT '',
            number_series TEXT DEFAULT 'PAY-',
            created_at TEXT DEFAULT (datetime('now')),
            submitted_at TEXT,
            cancelled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS payment_for (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent TEXT NOT NULL REFERENCES payment(name),
            reference_type TEXT,
            reference_name TEXT,
            amount REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS journal_entry (
            name TEXT PRIMARY KEY,
            date TEXT,
            entry_type TEXT DEFAULT 'Journal Entry',
            total_debit REAL DEFAULT 0,
            total_credit REAL DEFAULT 0,
            user_remark TEXT DEFAULT '',
            reference_number TEXT DEFAULT '',
            reference_date TEXT,
            status TEXT DEFAULT 'Draft',
            number_series TEXT DEFAULT 'JV-',
            created_at TEXT DEFAULT (datetime('now')),
            submitted_at TEXT,
            cancelled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS journal_entry_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent TEXT NOT NULL REFERENCES journal_entry(name),
            account TEXT REFERENCES account(name),
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            party TEXT DEFAULT '',
            reference_type TEXT DEFAULT '',
            reference_name TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS accounting_ledger_entry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            account TEXT REFERENCES account(name),
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            transaction_type TEXT,
            transaction_name TEXT,
            party TEXT DEFAULT '',
            is_cancelled INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


def get_or_create_db(company: str = "default") -> tuple[sqlite3.Connection, str]:
    db_path = get_db_path(company)
    conn = get_connection(db_path)
    create_schema(conn)
    return conn, db_path


def seed_number_series(conn: sqlite3.Connection) -> None:
    series = [
        ("SINV-", "SalesInvoice", 0),
        ("PINV-", "PurchaseInvoice", 0),
        ("PAY-", "Payment", 0),
        ("JV-", "JournalEntry", 0),
    ]
    for name, ref_type, current in series:
        conn.execute(
            "INSERT OR IGNORE INTO number_series (name, reference_type, current) VALUES (?, ?, ?)",
            (name, ref_type, current),
        )
    conn.commit()


def next_series_name(conn: sqlite3.Connection, prefix: str) -> str:
    row = conn.execute(
        "SELECT current FROM number_series WHERE name = ?", (prefix,)
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO number_series (name, current) VALUES (?, 1)", (prefix,)
        )
        conn.commit()
        return f"{prefix}0001"
    next_num = row["current"] + 1
    conn.execute(
        "UPDATE number_series SET current = ? WHERE name = ?", (next_num, prefix)
    )
    conn.commit()
    return f"{prefix}{next_num:04d}"
