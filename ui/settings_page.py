"""
Company settings and system overview UI.
"""
import streamlit as st
import sqlite3
from services.setup import get_settings, save_settings, get_countries, get_currencies


def render(conn):
    st.title("Settings")

    tab_company, tab_stats = st.tabs(["Company Settings", "Database Stats"])

    with tab_company:
        _render_company_settings(conn)

    with tab_stats:
        _render_stats(conn)


def _render_company_settings(conn):
    st.subheader("Company Information")
    settings = get_settings(conn)

    countries = get_countries(conn)
    currencies = get_currencies()

    with st.form("settings_form"):
        company_name = st.text_input("Company Name", value=settings.get("company_name", ""))

        country_val = settings.get("country", "United States")
        country_idx = countries.index(country_val) if country_val in countries else 0
        country = st.selectbox("Country", countries, index=country_idx)

        curr_val = settings.get("currency", "USD")
        curr_idx = currencies.index(curr_val) if curr_val in currencies else 0
        currency = st.selectbox("Currency", currencies, index=curr_idx)

        col1, col2 = st.columns(2)
        with col1:
            fy_start = st.text_input(
                "Fiscal Year Start (MM-DD)",
                value=settings.get("fiscal_year_start", "01-01"),
            )
        with col2:
            fy_end = st.text_input(
                "Fiscal Year End (MM-DD)",
                value=settings.get("fiscal_year_end", "12-31"),
            )

        if st.form_submit_button("Save Settings", type="primary", use_container_width=True):
            save_settings(conn, {
                "company_name": company_name,
                "country": country,
                "currency": currency,
                "fiscal_year_start": fy_start,
                "fiscal_year_end": fy_end,
            })
            st.success("Settings saved.")
            st.rerun()


def _render_stats(conn):
    st.subheader("Database Overview")

    stats = {
        "Accounts": conn.execute("SELECT COUNT(*) as c FROM account").fetchone()["c"],
        "Parties": conn.execute("SELECT COUNT(*) as c FROM party").fetchone()["c"],
        "Items": conn.execute("SELECT COUNT(*) as c FROM item").fetchone()["c"],
        "Sales Invoices": conn.execute("SELECT COUNT(*) as c FROM sales_invoice").fetchone()["c"],
        "Purchase Invoices": conn.execute("SELECT COUNT(*) as c FROM purchase_invoice").fetchone()["c"],
        "Payments": conn.execute("SELECT COUNT(*) as c FROM payment").fetchone()["c"],
        "Journal Entries": conn.execute("SELECT COUNT(*) as c FROM journal_entry").fetchone()["c"],
        "Ledger Entries": conn.execute("SELECT COUNT(*) as c FROM accounting_ledger_entry").fetchone()["c"],
    }

    col1, col2, col3, col4 = st.columns(4)
    cols = [col1, col2, col3, col4]
    for idx, (label, value) in enumerate(stats.items()):
        cols[idx % 4].metric(label, value)

    st.divider()
    st.subheader("Quick Stats")
    total_receivable = conn.execute(
        "SELECT COALESCE(SUM(outstanding_amount), 0) as t FROM sales_invoice WHERE status IN ('Submitted', 'Overdue')"
    ).fetchone()["t"]
    total_payable = conn.execute(
        "SELECT COALESCE(SUM(outstanding_amount), 0) as t FROM purchase_invoice WHERE status IN ('Submitted', 'Overdue')"
    ).fetchone()["t"]

    col1, col2 = st.columns(2)
    col1.metric("Total Receivable", f"{total_receivable:,.2f}")
    col2.metric("Total Payable", f"{total_payable:,.2f}")
