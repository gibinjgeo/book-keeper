"""
Purchase Invoice UI — list, create, submit, cancel.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from services.invoices import (
    get_all_purchase_invoices, get_purchase_invoice,
    create_purchase_invoice, submit_purchase_invoice,
    cancel_purchase_invoice, delete_purchase_invoice,
    calculate_invoice_totals,
)
from services.parties import get_party_names
from services.items import get_all_items, get_all_taxes
from services.accounts import get_account_names, get_payable_accounts


def render(conn):
    st.title("Purchase Invoices")

    tab_list, tab_create = st.tabs(["Invoice List", "New Invoice"])

    with tab_list:
        _render_invoice_list(conn)

    with tab_create:
        _render_create_invoice(conn)


def _render_invoice_list(conn):
    invoices = get_all_purchase_invoices(conn)
    if not invoices:
        st.info("No purchase invoices yet.")
        return

    df = pd.DataFrame(invoices)
    cols = ["name", "party", "date", "grand_total", "outstanding_amount", "status"]
    df_d = df[[c for c in cols if c in df.columns]].copy()
    df_d.columns = ["Invoice No", "Supplier", "Date", "Grand Total", "Outstanding", "Status"]
    df_d["Grand Total"] = df_d["Grand Total"].apply(lambda x: f"{x:,.2f}")
    df_d["Outstanding"] = df_d["Outstanding"].apply(lambda x: f"{x:,.2f}")

    status_filter = st.selectbox("Filter by Status", ["All", "Draft", "Submitted", "Paid", "Cancelled"])
    if status_filter != "All":
        df_d = df_d[df_d["Status"] == status_filter]

    st.dataframe(df_d, use_container_width=True, hide_index=True)

    st.subheader("View / Manage Invoice")
    inv_names = [i["name"] for i in invoices]
    selected = st.selectbox("Select invoice", [""] + inv_names, key="pi_select")

    if selected:
        inv = get_purchase_invoice(conn, selected)
        if inv:
            _render_invoice_detail(conn, inv)


def _render_invoice_detail(conn, inv: dict):
    status = inv.get("status", "Draft")
    st.markdown(f"**{inv['name']}** — Status: **{status}**")

    col1, col2, col3 = st.columns(3)
    col1.metric("Net Total", f"{inv.get('net_total', 0):,.2f}")
    col2.metric("Tax Total", f"{inv.get('tax_total', 0):,.2f}")
    col3.metric("Grand Total", f"{inv.get('grand_total', 0):,.2f}")
    st.caption(f"Supplier: {inv.get('party')} | Date: {inv.get('date')}")

    items = inv.get("items", [])
    if items:
        df_items = pd.DataFrame(items)
        cols = ["item", "description", "quantity", "rate", "amount", "tax_rate", "tax_amount"]
        df_items = df_items[[c for c in cols if c in df_items.columns]].copy()
        df_items.columns = ["Item", "Description", "Qty", "Rate", "Amount", "Tax %", "Tax Amt"]
        st.dataframe(df_items, use_container_width=True, hide_index=True)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if status == "Draft":
            if st.button("Submit Invoice", type="primary", key=f"pi_submit_{inv['name']}"):
                try:
                    submit_purchase_invoice(conn, inv["name"])
                    st.success("Invoice submitted.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    with col_b:
        if status in ("Submitted", "Overdue"):
            if st.button("Cancel Invoice", key=f"pi_cancel_{inv['name']}"):
                try:
                    cancel_purchase_invoice(conn, inv["name"])
                    st.success("Invoice cancelled.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    with col_c:
        if status == "Draft":
            if st.button("Delete Invoice", key=f"pi_del_{inv['name']}"):
                ok, msg = delete_purchase_invoice(conn, inv["name"])
                if ok:
                    st.success("Deleted.")
                    st.rerun()
                else:
                    st.error(msg)


def _render_create_invoice(conn):
    st.subheader("New Purchase Invoice")

    supplier_names = get_party_names(conn, "Supplier")
    payable_accounts = get_payable_accounts(conn)
    all_accounts = get_account_names(conn)
    items_list = get_all_items(conn, "Purchases")
    taxes = get_all_taxes(conn)
    tax_map = {t["name"]: t["rate"] for t in taxes}

    if not supplier_names:
        st.warning("No suppliers found. Add a Party with role 'Supplier' or 'Both' first.")
        return

    with st.form("create_pi_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            supplier = st.selectbox("Supplier *", supplier_names)
            inv_date = st.date_input("Invoice Date", value=datetime.today())
            due_date = st.date_input("Due Date", value=datetime.today() + timedelta(days=30))
        with col2:
            payable_opts = payable_accounts if payable_accounts else all_accounts
            payable_account = st.selectbox("Payable Account", [""] + payable_opts)
            currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "INR", "CAD"], index=0)
            user_remark = st.text_input("Remark")

        st.markdown("**Invoice Items**")
        num_items = st.number_input("Number of items", min_value=1, max_value=20, value=1, step=1)

        item_names = [i["name"] for i in items_list]
        item_rate_map = {i["name"]: float(i.get("rate", 0)) for i in items_list}
        item_acc_map = {i["name"]: i.get("expense_account", "") for i in items_list}
        item_tax_map = {i["name"]: i.get("tax") for i in items_list}
        expense_accounts = [""] + all_accounts

        line_items = []
        for idx in range(int(num_items)):
            st.markdown(f"*Item {idx + 1}*")
            c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 2, 2])
            with c1:
                item_name = st.selectbox("Item", [""] + item_names, key=f"pi_item_{idx}")
            with c2:
                qty = st.number_input("Qty", min_value=0.0, value=1.0, step=1.0, key=f"pi_qty_{idx}")
            with c3:
                default_rate = item_rate_map.get(item_name, 0.0)
                rate = st.number_input("Rate", min_value=0.0, value=default_rate, step=0.01, format="%.2f", key=f"pi_rate_{idx}")
            with c4:
                default_acc = item_acc_map.get(item_name, "")
                acc_idx = expense_accounts.index(default_acc) if default_acc in expense_accounts else 0
                account = st.selectbox("Account", expense_accounts, index=acc_idx, key=f"pi_acc_{idx}")
            with c5:
                item_tax = item_tax_map.get(item_name, "")
                tax_rate = tax_map.get(item_tax, 0.0) if item_tax else 0.0
                tax_rate_input = st.number_input("Tax %", min_value=0.0, value=tax_rate, step=0.5, key=f"pi_tax_{idx}")

            if item_name:
                amount = round(qty * rate, 2)
                tax_amount = round(amount * tax_rate_input / 100, 2)
                line_items.append({
                    "item": item_name,
                    "description": "",
                    "account": account or None,
                    "quantity": qty,
                    "rate": rate,
                    "amount": amount,
                    "tax_rate": tax_rate_input,
                    "tax_amount": tax_amount,
                    "tax_account": None,
                })

        if line_items:
            totals = calculate_invoice_totals([i.copy() for i in line_items])
            st.markdown(
                f"**Net:** {totals['net_total']:,.2f} | "
                f"**Tax:** {totals['tax_total']:,.2f} | "
                f"**Grand Total:** {totals['grand_total']:,.2f}"
            )

        if st.form_submit_button("Create Draft Invoice", type="primary", use_container_width=True):
            if not line_items:
                st.error("Please add at least one item.")
            else:
                try:
                    name = create_purchase_invoice(
                        conn,
                        {
                            "party": supplier,
                            "date": str(inv_date),
                            "due_date": str(due_date),
                            "account": payable_account or None,
                            "currency": currency,
                            "user_remark": user_remark,
                            "number_series": "PINV-",
                        },
                        line_items,
                    )
                    st.success(f"Invoice {name} created as Draft.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
