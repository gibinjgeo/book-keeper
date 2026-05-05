"""
SQLite database connection and schema management.
"""
import sqlite3
import os
from pathlib import Path

STORAGE_DIR = Path(__file__).parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

SCHEMA_VERSION = 3


def get_db_path(company: str = "default") -> str:
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in company)
    return str(STORAGE_DIR / f"{safe_name}.db")


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
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
            setup_done INTEGER DEFAULT 0,
            tax_number TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            website TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            zip_code TEXT DEFAULT '',
            invoice_prefix TEXT DEFAULT 'SINV-',
            bill_prefix TEXT DEFAULT 'PINV-',
            quote_prefix TEXT DEFAULT 'QTE-',
            payment_prefix TEXT DEFAULT 'PAY-',
            logo_path TEXT DEFAULT ''
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
            created_at TEXT DEFAULT (datetime('now')),
            is_active INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            opening_balance REAL DEFAULT 0,
            contact_person TEXT DEFAULT '',
            shipping_address TEXT DEFAULT '',
            shipping_city TEXT DEFAULT '',
            shipping_state TEXT DEFAULT '',
            shipping_country TEXT DEFAULT '',
            shipping_zip TEXT DEFAULT ''
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
            purchase_rate REAL DEFAULT 0,
            description TEXT DEFAULT '',
            income_account TEXT REFERENCES account(name),
            expense_account TEXT REFERENCES account(name),
            tax TEXT REFERENCES tax(name),
            track_item INTEGER DEFAULT 0,
            stock_quantity REAL DEFAULT 0,
            barcode TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS quote (
            name TEXT PRIMARY KEY,
            party TEXT REFERENCES party(name),
            date TEXT,
            expiry_date TEXT,
            status TEXT DEFAULT 'Draft',
            net_total REAL DEFAULT 0,
            tax_total REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            grand_total REAL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            user_remark TEXT DEFAULT '',
            number_series TEXT DEFAULT 'QTE-',
            converted_to TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS quote_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent TEXT NOT NULL REFERENCES quote(name),
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

        CREATE TABLE IF NOT EXISTS bank_account (
            name TEXT PRIMARY KEY,
            account_type TEXT DEFAULT 'Bank',
            account_number TEXT DEFAULT '',
            bank_name TEXT DEFAULT '',
            currency TEXT DEFAULT 'USD',
            opening_balance REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            gl_account TEXT REFERENCES account(name),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bank_transaction (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account TEXT NOT NULL REFERENCES bank_account(name),
            date TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            description TEXT DEFAULT '',
            reference TEXT DEFAULT '',
            category TEXT DEFAULT '',
            payment_method TEXT DEFAULT '',
            linked_type TEXT DEFAULT '',
            linked_name TEXT DEFAULT '',
            reconciled INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS opening_balance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account TEXT REFERENCES account(name),
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            date TEXT,
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


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Apply incremental ALTER TABLE statements for new columns on existing DBs."""
    migrations = [
        ("accounting_settings", "tax_number", "TEXT DEFAULT ''"),
        ("accounting_settings", "phone", "TEXT DEFAULT ''"),
        ("accounting_settings", "email", "TEXT DEFAULT ''"),
        ("accounting_settings", "website", "TEXT DEFAULT ''"),
        ("accounting_settings", "address", "TEXT DEFAULT ''"),
        ("accounting_settings", "city", "TEXT DEFAULT ''"),
        ("accounting_settings", "state", "TEXT DEFAULT ''"),
        ("accounting_settings", "zip_code", "TEXT DEFAULT ''"),
        ("accounting_settings", "invoice_prefix", "TEXT DEFAULT 'SINV-'"),
        ("accounting_settings", "bill_prefix", "TEXT DEFAULT 'PINV-'"),
        ("accounting_settings", "quote_prefix", "TEXT DEFAULT 'QTE-'"),
        ("accounting_settings", "payment_prefix", "TEXT DEFAULT 'PAY-'"),
        ("accounting_settings", "logo_path", "TEXT DEFAULT ''"),
        ("party", "is_active", "INTEGER DEFAULT 1"),
        ("party", "notes", "TEXT DEFAULT ''"),
        ("party", "opening_balance", "REAL DEFAULT 0"),
        ("party", "contact_person", "TEXT DEFAULT ''"),
        ("party", "shipping_address", "TEXT DEFAULT ''"),
        ("party", "shipping_city", "TEXT DEFAULT ''"),
        ("party", "shipping_state", "TEXT DEFAULT ''"),
        ("party", "shipping_country", "TEXT DEFAULT ''"),
        ("party", "shipping_zip", "TEXT DEFAULT ''"),
        ("item", "purchase_rate", "REAL DEFAULT 0"),
        ("item", "stock_quantity", "REAL DEFAULT 0"),
        ("item", "is_active", "INTEGER DEFAULT 1"),
    ]
    for table, column, col_def in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        except Exception:
            pass
    conn.commit()


def get_or_create_db(company: str = "default") -> tuple[sqlite3.Connection, str]:
    db_path = get_db_path(company)
    conn = get_connection(db_path)
    create_schema(conn)
    migrate_schema(conn)
    return conn, db_path


def seed_number_series(conn: sqlite3.Connection) -> None:
    series = [
        ("SINV-", "SalesInvoice", 0),
        ("PINV-", "PurchaseInvoice", 0),
        ("PAY-", "Payment", 0),
        ("JV-", "JournalEntry", 0),
        ("QTE-", "Quote", 0),
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
