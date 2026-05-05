"""
Accounting correctness tests: Decimal money, double-entry balance,
invoice statuses, payment application, overdue update, report totals.
"""
import pytest
import sqlite3
from decimal import Decimal

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import get_or_create_db, next_series_name
from backend import ledger, reports
from services.invoices import (
    calculate_invoice_totals, create_sales_invoice, submit_sales_invoice,
    cancel_sales_invoice, create_purchase_invoice, submit_purchase_invoice,
    apply_payment_to_invoice, update_overdue_statuses,
    create_credit_note,
)
from services.payments import create_payment, submit_payment
from services.journal import (
    create_journal_entry, submit_journal_entry, validate_journal_entry,
)
from services.parties import create_party
from services.items import create_item
from services.quotes import create_quote, convert_to_invoice
from services.banking import create_bank_account, record_deposit, record_withdrawal, record_transfer
from services.setup import complete_setup


@pytest.fixture(scope="function")
def conn():
    """In-memory SQLite database for each test."""
    c = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    from backend.database import create_schema, migrate_schema, seed_number_series
    create_schema(c)
    migrate_schema(c)
    complete_setup(c, "Test Co", "United States", "USD")
    seed_number_series(c)
    return c


def _find_account(conn, keyword):
    row = conn.execute(
        "SELECT name FROM account WHERE name LIKE ? AND is_group = 0 LIMIT 1",
        (f"%{keyword}%",),
    ).fetchone()
    assert row, f"Could not find account matching '{keyword}'"
    return row["name"]


# ---------- Money calculations ----------

class TestDecimalCalculations:
    def test_basic_totals(self):
        items = [{"quantity": 3, "rate": 10.00, "tax_rate": 10}]
        t = calculate_invoice_totals(items)
        assert t["net_total"] == 30.00
        assert t["tax_total"] == 3.00
        assert t["grand_total"] == 33.00

    def test_float_precision_avoided(self):
        items = [{"quantity": 3, "rate": 1.1, "tax_rate": 0}]
        t = calculate_invoice_totals(items)
        assert t["net_total"] == 3.30

    def test_discount_percent(self):
        items = [{"quantity": 1, "rate": 100.00, "tax_rate": 0}]
        t = calculate_invoice_totals(items, discount_percent=10)
        assert t["discount_amount"] == 10.00
        assert t["grand_total"] == 90.00

    def test_zero_quantity(self):
        items = [{"quantity": 0, "rate": 100.00, "tax_rate": 18}]
        t = calculate_invoice_totals(items)
        assert t["grand_total"] == 0.00

    def test_multiple_items(self):
        items = [
            {"quantity": 2, "rate": 50.00, "tax_rate": 10},
            {"quantity": 1, "rate": 200.00, "tax_rate": 5},
        ]
        t = calculate_invoice_totals(items)
        assert t["net_total"] == 300.00
        assert t["tax_total"] == 20.00
        assert t["grand_total"] == 320.00


# ---------- Double-entry journal ----------

class TestJournalEntry:
    def test_balanced_entry_accepted(self, conn):
        accounts = [
            {"account": _find_account(conn, "cash"), "debit": 100, "credit": 0},
            {"account": _find_account(conn, "sales"), "debit": 0, "credit": 100},
        ]
        ok, msg = validate_journal_entry(accounts)
        assert ok, msg

    def test_unbalanced_entry_rejected(self, conn):
        accounts = [
            {"account": _find_account(conn, "cash"), "debit": 100, "credit": 0},
            {"account": _find_account(conn, "sales"), "debit": 0, "credit": 90},
        ]
        ok, msg = validate_journal_entry(accounts)
        assert not ok
        assert "Debits" in msg

    def test_submit_posts_to_ledger(self, conn):
        cash = _find_account(conn, "cash")
        sales = _find_account(conn, "sales")
        accounts = [
            {"account": cash, "debit": 500, "credit": 0},
            {"account": sales, "debit": 0, "credit": 500},
        ]
        name = create_journal_entry(conn, {"date": "2026-01-01"}, accounts)
        submit_journal_entry(conn, name)
        bal = ledger.get_account_balance(conn, cash)
        assert bal["total_debit"] == 500

    def test_cancelled_entries_excluded(self, conn):
        cash = _find_account(conn, "cash")
        sales = _find_account(conn, "sales")
        accounts = [
            {"account": cash, "debit": 300, "credit": 0},
            {"account": sales, "debit": 0, "credit": 300},
        ]
        from services.journal import cancel_journal_entry
        name = create_journal_entry(conn, {"date": "2026-01-01"}, accounts)
        submit_journal_entry(conn, name)
        cancel_journal_entry(conn, name)
        bal = ledger.get_account_balance(conn, cash)
        assert bal["total_debit"] == 0

    def test_trial_balance_balances(self, conn):
        cash = _find_account(conn, "cash")
        sales = _find_account(conn, "sales")
        accounts = [
            {"account": cash, "debit": 100, "credit": 0},
            {"account": sales, "debit": 0, "credit": 100},
        ]
        name = create_journal_entry(conn, {"date": "2026-01-01"}, accounts)
        submit_journal_entry(conn, name)
        df = reports.trial_balance(conn)
        total_dr = df["total_debit"].sum()
        total_cr = df["total_credit"].sum()
        assert abs(total_dr - total_cr) < 0.01


# ---------- Invoice statuses ----------

class TestInvoiceStatuses:
    def _setup(self, conn):
        create_party(conn, {"name": "Test Customer", "role": "Customer"})
        income = _find_account(conn, "sales")
        receivable = _find_account(conn, "debtor")
        items = [{"quantity": 1, "rate": 100, "tax_rate": 0, "account": income, "tax_account": None}]
        name = create_sales_invoice(
            conn,
            {"party": "Test Customer", "date": "2026-01-01", "due_date": "2026-02-01", "account": receivable},
            items,
        )
        return name, receivable

    def test_draft_invoice_created(self, conn):
        name, _ = self._setup(conn)
        row = conn.execute("SELECT status FROM sales_invoice WHERE name = ?", (name,)).fetchone()
        assert row["status"] == "Draft"

    def test_submit_changes_status(self, conn):
        name, _ = self._setup(conn)
        submit_sales_invoice(conn, name)
        row = conn.execute("SELECT status FROM sales_invoice WHERE name = ?", (name,)).fetchone()
        assert row["status"] == "Submitted"

    def test_payment_marks_paid(self, conn):
        name, _ = self._setup(conn)
        submit_sales_invoice(conn, name)
        apply_payment_to_invoice(conn, "SalesInvoice", name, 100.0)
        row = conn.execute("SELECT status, outstanding_amount FROM sales_invoice WHERE name = ?", (name,)).fetchone()
        assert row["status"] == "Paid"
        assert float(row["outstanding_amount"]) == 0.0

    def test_partial_payment_status(self, conn):
        name, _ = self._setup(conn)
        submit_sales_invoice(conn, name)
        apply_payment_to_invoice(conn, "SalesInvoice", name, 60.0)
        row = conn.execute("SELECT status, outstanding_amount FROM sales_invoice WHERE name = ?", (name,)).fetchone()
        assert row["status"] == "Partially Paid"
        assert float(row["outstanding_amount"]) == 40.0

    def test_overdue_status_update(self, conn):
        name, _ = self._setup(conn)
        submit_sales_invoice(conn, name)
        conn.execute("UPDATE sales_invoice SET due_date = '2020-01-01' WHERE name = ?", (name,))
        conn.commit()
        update_overdue_statuses(conn)
        row = conn.execute("SELECT status FROM sales_invoice WHERE name = ?", (name,)).fetchone()
        assert row["status"] == "Overdue"

    def test_cancel_removes_ledger_entries(self, conn):
        name, receivable = self._setup(conn)
        submit_sales_invoice(conn, name)
        bal_before = ledger.get_account_balance(conn, receivable)
        assert bal_before["total_debit"] > 0
        cancel_sales_invoice(conn, name)
        bal_after = ledger.get_account_balance(conn, receivable)
        assert bal_after["balance"] == 0

    def test_cannot_edit_submitted(self, conn):
        name, _ = self._setup(conn)
        submit_sales_invoice(conn, name)
        from services.invoices import update_sales_invoice
        with pytest.raises(ValueError):
            update_sales_invoice(conn, name, {}, [])


# ---------- Credit notes ----------

class TestCreditNotes:
    def test_credit_note_created_as_return(self, conn):
        create_party(conn, {"name": "Cust", "role": "Customer"})
        income = _find_account(conn, "sales")
        receivable = _find_account(conn, "debtor")
        items = [{"quantity": 2, "rate": 50, "tax_rate": 0, "account": income, "tax_account": None}]
        inv_name = create_sales_invoice(
            conn, {"party": "Cust", "date": "2026-01-01", "account": receivable}, items
        )
        submit_sales_invoice(conn, inv_name)
        cn_name = create_credit_note(conn, inv_name)
        row = conn.execute("SELECT is_return, return_against FROM sales_invoice WHERE name = ?", (cn_name,)).fetchone()
        assert row["is_return"] == 1
        assert row["return_against"] == inv_name


# ---------- Payment double-entry ----------

class TestPayments:
    def test_payment_posts_correct_entries(self, conn):
        create_party(conn, {"name": "PayCust", "role": "Customer"})
        receivable = _find_account(conn, "debtor")
        bank = _find_account(conn, "bank")
        pay_name = create_payment(
            conn,
            {"party": "PayCust", "date": "2026-01-01",
             "payment_type": "Receive", "amount": 500,
             "account": receivable, "payment_account": bank},
            [],
        )
        submit_payment(conn, pay_name)
        bank_bal = ledger.get_account_balance(conn, bank)
        recv_bal = ledger.get_account_balance(conn, receivable)
        assert bank_bal["total_debit"] == 500
        assert recv_bal["total_credit"] == 500


# ---------- Quote workflow ----------

class TestQuotes:
    def test_convert_quote_to_invoice(self, conn):
        create_party(conn, {"name": "QuoteCust", "role": "Customer"})
        income = _find_account(conn, "sales")
        receivable = _find_account(conn, "debtor")
        items = [{"quantity": 1, "rate": 200, "tax_rate": 0, "account": income, "tax_account": None}]
        q_name = create_quote(
            conn, {"party": "QuoteCust", "date": "2026-01-01", "expiry_date": "2026-02-01"}, items
        )
        inv_name = convert_to_invoice(conn, q_name, receivable)
        assert inv_name is not None
        row = conn.execute("SELECT status, converted_to FROM quote WHERE name = ?", (q_name,)).fetchone()
        assert row["status"] == "Converted"
        assert row["converted_to"] == inv_name


# ---------- Banking ----------

class TestBanking:
    def test_deposit_increases_balance(self, conn):
        create_bank_account(conn, {"name": "Main Bank", "opening_balance": 1000})
        record_deposit(conn, "Main Bank", "2026-01-01", 500, "Sale receipt", post_ledger=False)
        from services.banking import get_bank_account
        ba = get_bank_account(conn, "Main Bank")
        assert ba["current_balance"] == 1500

    def test_withdrawal_decreases_balance(self, conn):
        create_bank_account(conn, {"name": "Cash Account", "opening_balance": 2000})
        record_withdrawal(conn, "Cash Account", "2026-01-01", 300, post_ledger=False)
        from services.banking import get_bank_account
        ba = get_bank_account(conn, "Cash Account")
        assert ba["current_balance"] == 1700

    def test_transfer_moves_funds(self, conn):
        create_bank_account(conn, {"name": "BankA", "opening_balance": 1000})
        create_bank_account(conn, {"name": "BankB", "opening_balance": 500})
        record_transfer(conn, "BankA", "BankB", "2026-01-01", 200, post_ledger=False)
        from services.banking import get_bank_account
        assert get_bank_account(conn, "BankA")["current_balance"] == 800
        assert get_bank_account(conn, "BankB")["current_balance"] == 700


# ---------- Report totals ----------

class TestReports:
    def test_pl_net_profit(self, conn):
        create_party(conn, {"name": "RC", "role": "Customer"})
        create_party(conn, {"name": "RS", "role": "Supplier"})
        income_row = conn.execute("SELECT name FROM account WHERE root_type='Income' AND is_group=0 LIMIT 1").fetchone()
        expense_row = conn.execute("SELECT name FROM account WHERE root_type='Expense' AND is_group=0 LIMIT 1").fetchone()
        income = income_row["name"] if income_row else _find_account(conn, "sales")
        expense = expense_row["name"] if expense_row else _find_account(conn, "expense")
        receivable = _find_account(conn, "debtor")
        payable = _find_account(conn, "creditor")

        sinv = create_sales_invoice(conn, {"party": "RC", "date": "2026-01-01", "account": receivable},
                                    [{"quantity": 1, "rate": 500, "tax_rate": 0, "account": income, "tax_account": None}])
        submit_sales_invoice(conn, sinv)

        pinv = create_purchase_invoice(conn, {"party": "RS", "date": "2026-01-01", "account": payable},
                                       [{"quantity": 1, "rate": 200, "tax_rate": 0, "account": expense, "tax_account": None}])
        submit_purchase_invoice(conn, pinv)

        data = reports.profit_and_loss(conn)
        assert data["total_income"] > 0
        assert data["total_expense"] > 0
        assert data["net_profit"] == data["total_income"] - data["total_expense"]

    def test_sales_by_customer(self, conn):
        create_party(conn, {"name": "BigBuyer", "role": "Customer"})
        income = _find_account(conn, "sales")
        receivable = _find_account(conn, "debtor")
        sinv = create_sales_invoice(conn, {"party": "BigBuyer", "date": "2026-01-01", "account": receivable},
                                    [{"quantity": 2, "rate": 150, "tax_rate": 0, "account": income, "tax_account": None}])
        submit_sales_invoice(conn, sinv)
        df = reports.sales_by_customer(conn)
        assert not df.empty
        row = df[df["customer"] == "BigBuyer"].iloc[0]
        assert row["grand_total"] == 300

    def test_ar_aging_buckets(self, conn):
        create_party(conn, {"name": "LatePayer", "role": "Customer"})
        income = _find_account(conn, "sales")
        receivable = _find_account(conn, "debtor")
        sinv = create_sales_invoice(
            conn,
            {"party": "LatePayer", "date": "2026-01-01", "due_date": "2026-01-01", "account": receivable},
            [{"quantity": 1, "rate": 100, "tax_rate": 0, "account": income, "tax_account": None}],
        )
        submit_sales_invoice(conn, sinv)
        df = reports.ar_aging(conn, as_of_date="2026-05-01")
        assert not df.empty
        row = df[df["Invoice"] == sinv].iloc[0]
        assert row["90+ Days"] == 100.0 or row["61-90 Days"] == 100.0 or row["31-60 Days"] == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
