"""
CSV import/export UI for contacts, items, invoices, ledger, and transactions.
"""
import streamlit as st
from datetime import datetime

from services.import_export import (
    export_parties_csv, export_items_csv,
    export_sales_invoices_csv, export_purchase_invoices_csv,
    export_general_ledger_csv, export_payments_csv,
    export_bank_transactions_csv,
    import_parties_csv, import_items_csv,
)
from services.banking import get_bank_account_names


def render(conn):
    st.title("Import / Export")

    tab_export, tab_import = st.tabs(["Export CSV", "Import CSV"])

    with tab_export:
        _render_export(conn)
    with tab_import:
        _render_import(conn)


def _render_export(conn):
    st.subheader("Export Data as CSV")
    today = datetime.today().strftime("%Y%m%d")

    exports = {
        "Contacts (Parties)": ("parties", export_parties_csv, {}),
        "Items": ("items", export_items_csv, {}),
        "Sales Invoices": ("sales_invoices", export_sales_invoices_csv, {}),
        "Purchase Invoices": ("purchase_invoices", export_purchase_invoices_csv, {}),
        "Payments": ("payments", export_payments_csv, {}),
    }

    for label, (slug, fn, kwargs) in exports.items():
        with st.expander(label):
            if st.button(f"Generate {label} CSV", key=f"exp_{slug}"):
                csv_data = fn(conn, **kwargs)
                if csv_data:
                    st.download_button(
                        f"Download {label}",
                        data=csv_data.encode(),
                        file_name=f"{slug}_{today}.csv",
                        mime="text/csv",
                        key=f"dl_{slug}",
                    )
                else:
                    st.info("No data to export.")

    with st.expander("General Ledger"):
        col1, col2 = st.columns(2)
        with col1:
            gl_from = st.date_input("From Date", value=datetime(datetime.today().year, 1, 1), key="gl_exp_from")
        with col2:
            gl_to = st.date_input("To Date", value=datetime.today(), key="gl_exp_to")
        if st.button("Generate Ledger CSV", key="exp_gl"):
            csv_data = export_general_ledger_csv(conn, str(gl_from), str(gl_to))
            if csv_data:
                st.download_button(
                    "Download General Ledger",
                    data=csv_data.encode(),
                    file_name=f"general_ledger_{today}.csv",
                    mime="text/csv",
                    key="dl_gl",
                )
            else:
                st.info("No ledger entries found.")

    with st.expander("Bank Transactions"):
        bank_accounts = ["All"] + get_bank_account_names(conn)
        sel_ba = st.selectbox("Bank Account", bank_accounts, key="exp_ba_sel")
        if st.button("Generate Bank Transactions CSV", key="exp_bt"):
            csv_data = export_bank_transactions_csv(conn, sel_ba if sel_ba != "All" else None)
            if csv_data:
                st.download_button(
                    "Download Bank Transactions",
                    data=csv_data.encode(),
                    file_name=f"bank_transactions_{today}.csv",
                    mime="text/csv",
                    key="dl_bt",
                )
            else:
                st.info("No bank transactions found.")


def _render_import(conn):
    st.subheader("Import from CSV")
    st.caption("Supported: Contacts and Items. Existing records (by name) will be skipped.")

    import_type = st.selectbox("Import Type", ["Contacts (Parties)", "Items"])

    uploaded = st.file_uploader("Upload CSV file", type=["csv"])

    if uploaded:
        csv_content = uploaded.read().decode("utf-8")
        st.caption(f"File: {uploaded.name} ({len(csv_content)} bytes)")

        with st.expander("Preview (first 500 chars)"):
            st.code(csv_content[:500])

        if st.button("Import Now", type="primary"):
            if import_type == "Contacts (Parties)":
                inserted, skipped, errors = import_parties_csv(conn, csv_content)
            else:
                inserted, skipped, errors = import_items_csv(conn, csv_content)

            st.success(f"Imported: {inserted} | Skipped (existing): {skipped}")
            if errors:
                st.error(f"{len(errors)} errors:")
                for e in errors[:20]:
                    st.caption(e)

    with st.expander("CSV Format Guide"):
        st.markdown("**Contacts CSV columns:**")
        st.code("name,role,email,phone,address,city,state,country,zip_code,currency,tax_id,is_active,notes,opening_balance,contact_person")
        st.caption("`role` must be one of: Customer, Supplier, Both")
        st.divider()
        st.markdown("**Items CSV columns:**")
        st.code("name,item_code,item_group,for_purpose,item_type,unit,rate,purchase_rate,description,is_active")
        st.caption("`for_purpose` must be one of: Sales, Purchase, Both")
