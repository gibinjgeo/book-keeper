"""
Company setup: load settings, seed COA, seed number series.
"""
import json
import sqlite3
from pathlib import Path

from backend.database import seed_number_series
from services.accounts import load_standard_coa

DATA_DIR = Path(__file__).parent.parent / "data"


def is_setup_done(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT setup_done FROM accounting_settings WHERE id = 1"
    ).fetchone()
    return bool(row and row["setup_done"])


def get_settings(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM accounting_settings WHERE id = 1").fetchone()
    if not row:
        return {
            "company_name": "",
            "country": "United States",
            "currency": "USD",
            "fiscal_year_start": "01-01",
            "fiscal_year_end": "12-31",
            "setup_done": 0,
        }
    return dict(row)


def save_settings(conn: sqlite3.Connection, settings: dict) -> None:
    existing = conn.execute(
        "SELECT id FROM accounting_settings WHERE id = 1"
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE accounting_settings SET
               company_name = ?, country = ?, currency = ?,
               fiscal_year_start = ?, fiscal_year_end = ?,
               round_off_account = ?, bank_account = ?, discount_account = ?
               WHERE id = 1""",
            (
                settings.get("company_name", ""),
                settings.get("country", "United States"),
                settings.get("currency", "USD"),
                settings.get("fiscal_year_start", "01-01"),
                settings.get("fiscal_year_end", "12-31"),
                settings.get("round_off_account"),
                settings.get("bank_account"),
                settings.get("discount_account"),
            ),
        )
    else:
        conn.execute(
            """INSERT INTO accounting_settings
               (id, company_name, country, currency,
                fiscal_year_start, fiscal_year_end)
               VALUES (1, ?, ?, ?, ?, ?)""",
            (
                settings.get("company_name", "My Company"),
                settings.get("country", "United States"),
                settings.get("currency", "USD"),
                settings.get("fiscal_year_start", "01-01"),
                settings.get("fiscal_year_end", "12-31"),
            ),
        )
    conn.commit()


def complete_setup(conn: sqlite3.Connection, company_name: str, country: str, currency: str) -> None:
    existing = conn.execute(
        "SELECT id FROM accounting_settings WHERE id = 1"
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE accounting_settings SET
               company_name = ?, country = ?, currency = ?, setup_done = 1
               WHERE id = 1""",
            (company_name, country, currency),
        )
    else:
        conn.execute(
            """INSERT INTO accounting_settings
               (id, company_name, country, currency, setup_done)
               VALUES (1, ?, ?, ?, 1)""",
            (company_name, country, currency),
        )
    conn.commit()

    load_standard_coa(conn)
    seed_number_series(conn)
    _seed_taxes(conn)
    _seed_default_items(conn)


def _seed_taxes(conn: sqlite3.Connection) -> None:
    taxes = [
        ("GST 18%", 18.0, "Duties and Taxes"),
        ("GST 12%", 12.0, "Duties and Taxes"),
        ("GST 5%", 5.0, "Duties and Taxes"),
        ("VAT 20%", 20.0, "Duties and Taxes"),
        ("VAT 10%", 10.0, "Duties and Taxes"),
    ]
    duties_account = conn.execute(
        "SELECT name FROM account WHERE name LIKE '%Duties%' LIMIT 1"
    ).fetchone()
    tax_account = duties_account["name"] if duties_account else None

    for name, rate, _ in taxes:
        conn.execute(
            "INSERT OR IGNORE INTO tax (name, rate, account) VALUES (?, ?, ?)",
            (name, rate, tax_account),
        )
    conn.commit()


def _seed_default_items(conn: sqlite3.Connection) -> None:
    groups = [
        ("Products", None),
        ("Services", None),
        ("Raw Materials", "Products"),
    ]
    for name, parent in groups:
        conn.execute(
            "INSERT OR IGNORE INTO item_group (name, parent_group) VALUES (?, ?)",
            (name, parent),
        )
    conn.commit()


def get_countries(conn: sqlite3.Connection) -> list[str]:
    country_path = DATA_DIR / "country_info.json"
    try:
        with open(country_path) as f:
            data = json.load(f)
        return sorted(data.keys())
    except Exception:
        return ["United States", "India", "United Kingdom", "Canada", "Australia"]


def get_currencies() -> list[str]:
    return [
        "USD", "EUR", "GBP", "INR", "CAD", "AUD", "JPY", "CNY",
        "SGD", "AED", "MXN", "BRL", "ZAR", "CHF", "SEK", "NOK",
    ]
