"""
Book Keeper
A local double-entry bookkeeping application built with Streamlit and SQLite.

Run with:
    streamlit run main.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from backend.database import get_or_create_db
from services.setup import is_setup_done, get_settings

st.set_page_config(
    page_title="Book Keeper",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def init_db():
    conn, db_path = get_or_create_db("books")
    return conn, db_path


conn, db_path = init_db()


def main():
    from ui.setup_page import render as render_setup
    from ui.accounts_page import render as render_accounts
    from ui.parties_page import render as render_parties
    from ui.items_page import render as render_items
    from ui.sales_page import render as render_sales
    from ui.purchases_page import render as render_purchases
    from ui.payments_page import render as render_payments
    from ui.journal_page import render as render_journal
    from ui.reports_page import render as render_reports
    from ui.settings_page import render as render_settings
    from ui.banking_page import render as render_banking
    from ui.quotes_page import render as render_quotes
    from ui.import_export_page import render as render_import_export
    from services.invoices import update_overdue_statuses

    if not is_setup_done(conn):
        render_setup(conn)
        return

    update_overdue_statuses(conn)

    settings = get_settings(conn)
    company = settings.get("company_name", "My Company")

    with st.sidebar:
        st.markdown(f"## 📒 Book Keeper")
        st.caption(company)
        st.divider()

        pages = {
            "Dashboard": "📊",
            "Chart of Accounts": "🏦",
            "Parties": "👥",
            "Items": "📦",
            "Quotes": "📋",
            "Sales Invoices": "🧾",
            "Purchase Invoices": "🛒",
            "Payments": "💳",
            "Banking": "🏦",
            "Journal Entries": "📓",
            "Reports": "📈",
            "Import / Export": "🔄",
            "Settings": "⚙️",
        }

        if "_nav" in st.session_state:
            st.session_state["nav_page"] = st.session_state.pop("_nav")

        selected = st.radio(
            "Navigation",
            list(pages.keys()),
            format_func=lambda x: f"{pages[x]} {x}",
            label_visibility="collapsed",
            key="nav_page",
        )

        st.divider()
        st.caption(f"DB: `{os.path.basename(db_path)}`")

    if selected == "Dashboard":
        _render_dashboard(conn, company)
    elif selected == "Chart of Accounts":
        render_accounts(conn)
    elif selected == "Parties":
        render_parties(conn)
    elif selected == "Items":
        render_items(conn)
    elif selected == "Quotes":
        render_quotes(conn)
    elif selected == "Sales Invoices":
        render_sales(conn)
    elif selected == "Purchase Invoices":
        render_purchases(conn)
    elif selected == "Payments":
        render_payments(conn)
    elif selected == "Banking":
        render_banking(conn)
    elif selected == "Journal Entries":
        render_journal(conn)
    elif selected == "Reports":
        render_reports(conn)
    elif selected == "Import / Export":
        render_import_export(conn)
    elif selected == "Settings":
        render_settings(conn)


def _render_dashboard(conn, company: str):
    import pandas as pd
    from datetime import datetime

    st.title("Dashboard")
    st.caption(company)

    today = datetime.now()
    month_start = today.strftime(f"%Y-%{today.month:02d}-01") if False else f"{today.year}-{today.month:02d}-01"

    # Monthly metrics
    month_income = conn.execute(
        "SELECT COALESCE(SUM(grand_total), 0) as t FROM sales_invoice WHERE status NOT IN ('Cancelled','Draft') AND date >= ?",
        (month_start,),
    ).fetchone()["t"]
    month_expenses = conn.execute(
        "SELECT COALESCE(SUM(grand_total), 0) as t FROM purchase_invoice WHERE status NOT IN ('Cancelled','Draft') AND date >= ?",
        (month_start,),
    ).fetchone()["t"]
    total_receivable = conn.execute(
        "SELECT COALESCE(SUM(outstanding_amount), 0) as t FROM sales_invoice WHERE status IN ('Submitted', 'Overdue', 'Partially Paid')"
    ).fetchone()["t"]
    total_payable = conn.execute(
        "SELECT COALESCE(SUM(outstanding_amount), 0) as t FROM purchase_invoice WHERE status IN ('Submitted', 'Overdue', 'Partially Paid')"
    ).fetchone()["t"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Income This Month", f"{month_income:,.2f}")
    col2.metric("Expenses This Month", f"{month_expenses:,.2f}")
    col3.metric("Total Receivable", f"{total_receivable:,.2f}")
    col4.metric("Total Payable", f"{total_payable:,.2f}")

    st.divider()

    # Overdue alerts + net profit
    overdue_invoices = conn.execute(
        "SELECT COUNT(*) as c, COALESCE(SUM(outstanding_amount),0) as t FROM sales_invoice WHERE status = 'Overdue'"
    ).fetchone()
    overdue_bills = conn.execute(
        "SELECT COUNT(*) as c, COALESCE(SUM(outstanding_amount),0) as t FROM purchase_invoice WHERE status = 'Overdue'"
    ).fetchone()
    net_profit = month_income - month_expenses

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Overdue Invoices", overdue_invoices["c"],
                delta=f"{overdue_invoices['t']:,.2f} outstanding",
                delta_color="inverse" if overdue_invoices["c"] > 0 else "normal")
    col6.metric("Overdue Bills", overdue_bills["c"],
                delta=f"{overdue_bills['t']:,.2f} outstanding",
                delta_color="inverse" if overdue_bills["c"] > 0 else "normal")
    col7.metric("Net Profit (Month)", f"{net_profit:,.2f}",
                delta_color="normal" if net_profit >= 0 else "inverse")

    # Bank balance
    bank_balance = conn.execute(
        """SELECT COALESCE(
             SUM(ba.opening_balance) + COALESCE(
               (SELECT SUM(CASE WHEN bt.transaction_type IN ('Deposit','Transfer In') THEN bt.amount
                               WHEN bt.transaction_type IN ('Withdrawal','Transfer Out') THEN -bt.amount
                               ELSE 0 END)
                FROM bank_transaction bt WHERE bt.bank_account = ba.name), 0), 0) as total
           FROM bank_account ba WHERE ba.is_active = 1"""
    ).fetchone()["total"]
    col8.metric("Cash & Bank Balance", f"{bank_balance:,.2f}")

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Recent Sales Invoices")
        rows = conn.execute(
            """SELECT name, party, date, grand_total, outstanding_amount, status
               FROM sales_invoice ORDER BY created_at DESC LIMIT 8"""
        ).fetchall()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            df["grand_total"] = df["grand_total"].apply(lambda x: f"{x:,.2f}")
            df["outstanding_amount"] = df["outstanding_amount"].apply(lambda x: f"{x:,.2f}")
            df.columns = ["Invoice", "Customer", "Date", "Total", "Outstanding", "Status"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No invoices yet.")

    with col_r:
        st.subheader("Recent Payments")
        rows = conn.execute(
            """SELECT name, party, date, amount, payment_type, status
               FROM payment ORDER BY created_at DESC LIMIT 8"""
        ).fetchall()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            df["amount"] = df["amount"].apply(lambda x: f"{x:,.2f}")
            df.columns = ["Payment", "Party", "Date", "Amount", "Type", "Status"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No payments yet.")

    st.divider()

    col_ll, col_rr = st.columns(2)
    with col_ll:
        st.subheader("Top Customers (This Month)")
        rows = conn.execute(
            """SELECT party, SUM(grand_total) as total
               FROM sales_invoice WHERE status NOT IN ('Draft','Cancelled') AND date >= ?
               GROUP BY party ORDER BY total DESC LIMIT 5""",
            (month_start,),
        ).fetchall()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            df["total"] = df["total"].apply(lambda x: f"{x:,.2f}")
            df.columns = ["Customer", "Total"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No sales this month.")

    with col_rr:
        st.subheader("Top Expenses (This Month)")
        rows = conn.execute(
            """SELECT party, SUM(grand_total) as total
               FROM purchase_invoice WHERE status NOT IN ('Draft','Cancelled') AND date >= ?
               GROUP BY party ORDER BY total DESC LIMIT 5""",
            (month_start,),
        ).fetchall()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            df["total"] = df["total"].apply(lambda x: f"{x:,.2f}")
            df.columns = ["Supplier", "Total"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No purchases this month.")

    st.divider()
    st.subheader("Quick Actions")
    col_a, col_b, col_c, col_d, col_e = st.columns(5)

    with col_a:
        if st.button("New Quote", use_container_width=True):
            st.session_state["_nav"] = "Quotes"
            st.rerun()
    with col_b:
        if st.button("New Sales Invoice", use_container_width=True):
            st.session_state["_nav"] = "Sales Invoices"
            st.session_state["_new_sales_invoice"] = True
            st.rerun()
    with col_c:
        if st.button("New Purchase Invoice", use_container_width=True):
            st.session_state["_nav"] = "Purchase Invoices"
            st.session_state["_new_purchase_invoice"] = True
            st.rerun()
    with col_d:
        if st.button("Receive Payment", use_container_width=True):
            st.session_state["_nav"] = "Payments"
            st.session_state["_new_payment"] = True
            st.rerun()
    with col_e:
        if st.button("View Reports", use_container_width=True):
            st.session_state["_nav"] = "Reports"
            st.rerun()


if __name__ == "__main__":
    main()
