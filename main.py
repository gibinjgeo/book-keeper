"""
Frappe Books — Python Edition
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
    page_title="Frappe Books (Python)",
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

    if not is_setup_done(conn):
        render_setup(conn)
        return

    settings = get_settings(conn)
    company = settings.get("company_name", "My Company")

    with st.sidebar:
        st.markdown(f"## 📒 Frappe Books")
        st.caption(company)
        st.divider()

        pages = {
            "Dashboard": "📊",
            "Chart of Accounts": "🏦",
            "Parties": "👥",
            "Items": "📦",
            "Sales Invoices": "🧾",
            "Purchase Invoices": "🛒",
            "Payments": "💳",
            "Journal Entries": "📓",
            "Reports": "📈",
            "Settings": "⚙️",
        }

        selected = st.radio(
            "Navigation",
            list(pages.keys()),
            format_func=lambda x: f"{pages[x]} {x}",
            label_visibility="collapsed",
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
    elif selected == "Sales Invoices":
        render_sales(conn)
    elif selected == "Purchase Invoices":
        render_purchases(conn)
    elif selected == "Payments":
        render_payments(conn)
    elif selected == "Journal Entries":
        render_journal(conn)
    elif selected == "Reports":
        render_reports(conn)
    elif selected == "Settings":
        render_settings(conn)


def _render_dashboard(conn, company: str):
    st.title(f"Dashboard")
    st.caption(company)

    col1, col2, col3, col4 = st.columns(4)

    total_sales = conn.execute(
        "SELECT COALESCE(SUM(grand_total), 0) as t FROM sales_invoice WHERE status NOT IN ('Cancelled', 'Draft')"
    ).fetchone()["t"]
    total_purchases = conn.execute(
        "SELECT COALESCE(SUM(grand_total), 0) as t FROM purchase_invoice WHERE status NOT IN ('Cancelled', 'Draft')"
    ).fetchone()["t"]
    total_receivable = conn.execute(
        "SELECT COALESCE(SUM(outstanding_amount), 0) as t FROM sales_invoice WHERE status IN ('Submitted', 'Overdue')"
    ).fetchone()["t"]
    total_payable = conn.execute(
        "SELECT COALESCE(SUM(outstanding_amount), 0) as t FROM purchase_invoice WHERE status IN ('Submitted', 'Overdue')"
    ).fetchone()["t"]

    col1.metric("Total Sales", f"{total_sales:,.2f}")
    col2.metric("Total Purchases", f"{total_purchases:,.2f}")
    col3.metric("Receivable", f"{total_receivable:,.2f}")
    col4.metric("Payable", f"{total_payable:,.2f}")

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Recent Sales Invoices")
        rows = conn.execute(
            """SELECT name, party, date, grand_total, status
               FROM sales_invoice ORDER BY created_at DESC LIMIT 10"""
        ).fetchall()
        if rows:
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in rows])
            df["grand_total"] = df["grand_total"].apply(lambda x: f"{x:,.2f}")
            df.columns = ["Invoice", "Customer", "Date", "Total", "Status"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No invoices yet.")

    with col_r:
        st.subheader("Recent Payments")
        rows = conn.execute(
            """SELECT name, party, date, amount, payment_type, status
               FROM payment ORDER BY created_at DESC LIMIT 10"""
        ).fetchall()
        if rows:
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in rows])
            df["amount"] = df["amount"].apply(lambda x: f"{x:,.2f}")
            df.columns = ["Payment", "Party", "Date", "Amount", "Type", "Status"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No payments yet.")

    st.divider()
    st.subheader("Quick Actions")
    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        if st.button("New Sales Invoice", use_container_width=True):
            st.session_state["_nav"] = "Sales Invoices"
            st.rerun()

    with col_b:
        if st.button("New Purchase Invoice", use_container_width=True):
            st.session_state["_nav"] = "Purchase Invoices"
            st.rerun()

    with col_c:
        if st.button("Receive Payment", use_container_width=True):
            st.session_state["_nav"] = "Payments"
            st.rerun()

    with col_d:
        if st.button("View Reports", use_container_width=True):
            st.session_state["_nav"] = "Reports"
            st.rerun()


if __name__ == "__main__":
    main()
