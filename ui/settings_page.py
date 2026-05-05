"""
Company settings, backup/restore, and system stats UI.
"""
import os
import streamlit as st
from pathlib import Path
from services.setup import get_settings, save_settings, get_countries, get_currencies
from services.import_export import backup_database, list_backups, restore_database


def render(conn):
    st.title("Settings")

    tabs = st.tabs(["Company Profile", "Document Prefixes", "Backup & Restore", "Database Stats"])

    with tabs[0]:
        _render_company_settings(conn)
    with tabs[1]:
        _render_prefix_settings(conn)
    with tabs[2]:
        _render_backup_restore(conn)
    with tabs[3]:
        _render_stats(conn)


def _render_company_settings(conn):
    st.subheader("Company Information")
    settings = get_settings(conn)
    countries = get_countries(conn)
    currencies = get_currencies()

    with st.form("settings_form"):
        company_name = st.text_input("Company Name *", value=settings.get("company_name", ""))
        tax_number = st.text_input("Tax / VAT / GST Number", value=settings.get("tax_number", ""))

        col1, col2 = st.columns(2)
        with col1:
            phone = st.text_input("Phone", value=settings.get("phone", ""))
            email = st.text_input("Email", value=settings.get("email", ""))
        with col2:
            website = st.text_input("Website", value=settings.get("website", ""))

        st.markdown("**Address**")
        address = st.text_input("Street Address", value=settings.get("address", ""))
        col_c, col_s, col_z = st.columns(3)
        with col_c:
            city = st.text_input("City", value=settings.get("city", ""))
        with col_s:
            state = st.text_input("State/Province", value=settings.get("state", ""))
        with col_z:
            zip_code = st.text_input("ZIP/Postal Code", value=settings.get("zip_code", ""))

        country_val = settings.get("country", "United States")
        country_idx = countries.index(country_val) if country_val in countries else 0
        country = st.selectbox("Country", countries, index=country_idx)

        st.markdown("**Financial Settings**")
        col_curr, col_fy1, col_fy2 = st.columns(3)
        with col_curr:
            curr_val = settings.get("currency", "USD")
            curr_idx = currencies.index(curr_val) if curr_val in currencies else 0
            currency = st.selectbox("Default Currency", currencies, index=curr_idx)
        with col_fy1:
            fy_start = st.text_input("Fiscal Year Start (MM-DD)", value=settings.get("fiscal_year_start", "01-01"))
        with col_fy2:
            fy_end = st.text_input("Fiscal Year End (MM-DD)", value=settings.get("fiscal_year_end", "12-31"))

        if st.form_submit_button("Save Settings", type="primary", use_container_width=True):
            save_settings(conn, {
                **settings,
                "company_name": company_name,
                "country": country,
                "currency": currency,
                "fiscal_year_start": fy_start,
                "fiscal_year_end": fy_end,
                "tax_number": tax_number,
                "phone": phone,
                "email": email,
                "website": website,
                "address": address,
                "city": city,
                "state": state,
                "zip_code": zip_code,
            })
            st.success("Settings saved.")
            st.rerun()


def _render_prefix_settings(conn):
    st.subheader("Document Number Prefixes")
    st.caption("These prefixes are used when generating document numbers.")
    settings = get_settings(conn)

    with st.form("prefix_form"):
        col1, col2 = st.columns(2)
        with col1:
            inv_pfx = st.text_input("Sales Invoice Prefix", value=settings.get("invoice_prefix", "SINV-"))
            quote_pfx = st.text_input("Quote Prefix", value=settings.get("quote_prefix", "QTE-"))
        with col2:
            bill_pfx = st.text_input("Purchase Bill Prefix", value=settings.get("bill_prefix", "PINV-"))
            pay_pfx = st.text_input("Payment Prefix", value=settings.get("payment_prefix", "PAY-"))

        if st.form_submit_button("Save Prefixes", type="primary", use_container_width=True):
            save_settings(conn, {
                **settings,
                "invoice_prefix": inv_pfx,
                "bill_prefix": bill_pfx,
                "quote_prefix": quote_pfx,
                "payment_prefix": pay_pfx,
            })
            st.success("Prefixes saved.")
            st.rerun()


def _render_backup_restore(conn):
    st.subheader("Local Backup & Restore")

    from backend.database import get_db_path
    db_path = get_db_path("books")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Create Backup**")
        st.caption(f"Database: `{db_path}`")
        if st.button("Create Backup Now", type="primary", use_container_width=True):
            backup_path = backup_database(db_path)
            st.success(f"Backup created: `{backup_path}`")

    with col2:
        st.markdown("**Available Backups**")
        backups = list_backups(db_path)
        if not backups:
            st.caption("No backups found.")
        else:
            selected_backup = st.selectbox("Select backup", backups)
            if st.button("Restore Selected Backup", type="secondary", use_container_width=True):
                st.warning(f"This will OVERWRITE the current database with the selected backup. Confirm?")
                if st.button("YES, RESTORE NOW", type="primary"):
                    restore_database(selected_backup, db_path)
                    st.success("Database restored. Please restart the application.")

    st.divider()
    st.subheader("Download Database")
    try:
        with open(db_path, "rb") as f:
            db_bytes = f.read()
        st.download_button(
            "Download Database File",
            data=db_bytes,
            file_name=f"books_backup_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
            mime="application/octet-stream",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Could not read database: {e}")


def _render_stats(conn):
    st.subheader("Database Overview")

    def _count(table):
        try:
            return conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()["c"]
        except Exception:
            return 0

    stats = {
        "Accounts": _count("account"),
        "Parties": _count("party"),
        "Items": _count("item"),
        "Sales Invoices": _count("sales_invoice"),
        "Purchase Invoices": _count("purchase_invoice"),
        "Quotes": _count("quote"),
        "Payments": _count("payment"),
        "Journal Entries": _count("journal_entry"),
        "Bank Accounts": _count("bank_account"),
        "Bank Transactions": _count("bank_transaction"),
        "Ledger Entries": _count("accounting_ledger_entry"),
        "Taxes": _count("tax"),
    }

    col1, col2, col3, col4 = st.columns(4)
    cols = [col1, col2, col3, col4]
    for idx, (label, value) in enumerate(stats.items()):
        cols[idx % 4].metric(label, value)

    st.divider()
    st.subheader("Financial Snapshot")
    total_receivable = conn.execute(
        """SELECT COALESCE(SUM(outstanding_amount), 0) as t FROM sales_invoice
           WHERE status IN ('Submitted', 'Overdue', 'Partially Paid')"""
    ).fetchone()["t"]
    total_payable = conn.execute(
        """SELECT COALESCE(SUM(outstanding_amount), 0) as t FROM purchase_invoice
           WHERE status IN ('Submitted', 'Overdue', 'Partially Paid')"""
    ).fetchone()["t"]

    col1, col2 = st.columns(2)
    col1.metric("Total Receivable", f"{total_receivable:,.2f}")
    col2.metric("Total Payable", f"{total_payable:,.2f}")
