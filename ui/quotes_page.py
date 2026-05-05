"""
Quotes / Estimates UI.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from services.quotes import (
    get_all_quotes, get_quote, create_quote, update_quote,
    send_quote, convert_to_invoice, cancel_quote, delete_quote,
)
from services.parties import get_party_names
from services.items import get_all_items, get_all_taxes
from services.accounts import get_receivable_accounts
from services.invoices import calculate_invoice_totals

STATUS_COLORS = {
    "Draft": "blue", "Sent": "orange", "Converted": "green", "Cancelled": "red",
}


def render(conn):
    st.title("Quotes & Estimates")

    tabs = st.tabs(["Quote List", "New Quote"])
    with tabs[0]:
        _render_list(conn)
    with tabs[1]:
        _render_create(conn)


def _render_list(conn):
    quotes = get_all_quotes(conn)
    if not quotes:
        st.info("No quotes yet.")
        return

    df = pd.DataFrame(quotes)
    cols = ["name", "party", "date", "expiry_date", "grand_total", "status", "converted_to"]
    df_d = df[[c for c in cols if c in df.columns]].copy()
    df_d.rename(columns={
        "name": "Quote No", "party": "Customer", "date": "Date",
        "expiry_date": "Expiry", "grand_total": "Total",
        "status": "Status", "converted_to": "Invoice",
    }, inplace=True)
    if "Total" in df_d:
        df_d["Total"] = df_d["Total"].apply(lambda x: f"{x:,.2f}")

    status_filter = st.selectbox("Filter by Status", ["All", "Draft", "Sent", "Converted", "Cancelled"])
    if status_filter != "All":
        df_d = df_d[df_d["Status"] == status_filter]

    st.dataframe(df_d, use_container_width=True, hide_index=True)

    st.subheader("Manage Quote")
    q_names = [q["name"] for q in quotes]
    selected = st.selectbox("Select quote", [""] + q_names, key="q_select")
    if selected:
        q = get_quote(conn, selected)
        if q:
            _render_detail(conn, q)


def _render_detail(conn, q: dict):
    status = q.get("status", "Draft")
    color = STATUS_COLORS.get(status, "gray")
    st.markdown(f"**{q['name']}** — Status: **:{color}[{status}]**")

    col1, col2, col3 = st.columns(3)
    col1.write(f"**Customer:** {q.get('party', '')}")
    col2.write(f"**Date:** {q.get('date', '')}")
    col3.write(f"**Expiry:** {q.get('expiry_date', '')}")

    items = q.get("items", [])
    if items:
        df = pd.DataFrame(items)
        cols = ["item", "description", "quantity", "rate", "amount", "tax_rate", "tax_amount"]
        st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)

    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Net Total", f"{q.get('net_total', 0):,.2f}")
    col_t2.metric("Tax", f"{q.get('tax_total', 0):,.2f}")
    col_t3.metric("Grand Total", f"{q.get('grand_total', 0):,.2f}")

    st.divider()
    col_a, col_b, col_c = st.columns(3)

    if status == "Draft":
        with col_a:
            if st.button("Send Quote", use_container_width=True):
                try:
                    send_quote(conn, q["name"])
                    st.success("Quote marked as Sent.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    if status in ("Draft", "Sent"):
        receivable_accounts = get_receivable_accounts(conn)
        recv_acc = col_b.selectbox("Receivable Account", receivable_accounts, key=f"recv_{q['name']}")
        with col_b:
            if st.button("Convert to Invoice", use_container_width=True):
                try:
                    inv_name = convert_to_invoice(conn, q["name"], recv_acc)
                    st.success(f"Converted to invoice: **{inv_name}**")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        with col_c:
            if st.button("Cancel Quote", use_container_width=True):
                cancel_quote(conn, q["name"])
                st.success("Quote cancelled.")
                st.rerun()

    if status == "Draft":
        if st.button("Delete Draft", type="secondary", use_container_width=True):
            ok, msg = delete_quote(conn, q["name"])
            if ok:
                st.success("Deleted.")
                st.rerun()
            else:
                st.error(msg)

    if q.get("converted_to"):
        st.info(f"Converted to invoice: **{q['converted_to']}**")


def _render_create(conn):
    st.subheader("New Quote")
    customer_names = get_party_names(conn, role="Customer")
    all_items = get_all_items(conn)
    all_taxes = get_all_taxes(conn)
    tax_map = {t["name"]: t for t in all_taxes}

    with st.form("new_quote_form"):
        col1, col2 = st.columns(2)
        with col1:
            party = st.selectbox("Customer *", [""] + customer_names)
            date = st.date_input("Quote Date", value=datetime.today())
        with col2:
            expiry = st.date_input("Expiry Date", value=datetime.today() + timedelta(days=30))
            currency = st.text_input("Currency", value="USD")

        user_remark = st.text_area("Notes / Remarks", height=60)

        st.subheader("Line Items")
        item_names = [i["name"] for i in all_items]
        n_rows = st.number_input("Number of line items", min_value=1, max_value=20, value=1)

        item_rows = []
        for i in range(int(n_rows)):
            st.markdown(f"**Item {i+1}**")
            c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
            with c1:
                item_name = st.selectbox(f"Item", [""] + item_names, key=f"q_item_{i}")
            with c2:
                qty = st.number_input("Qty", min_value=0.0, value=1.0, step=1.0, key=f"q_qty_{i}")
            with c3:
                rate = st.number_input("Rate", min_value=0.0, value=0.0, step=0.01, key=f"q_rate_{i}")
            with c4:
                tax_sel = st.selectbox("Tax", ["None"] + list(tax_map.keys()), key=f"q_tax_{i}")

            if item_name:
                item_data = next((it for it in all_items if it["name"] == item_name), {})
                if rate == 0:
                    rate = float(item_data.get("rate", 0))
                tax_rate_val = 0.0
                tax_acc = None
                if tax_sel != "None" and tax_sel in tax_map:
                    tax_rate_val = float(tax_map[tax_sel]["rate"])
                    tax_acc = tax_map[tax_sel].get("account")
                elif item_data.get("tax") and item_data["tax"] in tax_map:
                    tax_rate_val = float(tax_map[item_data["tax"]]["rate"])
                    tax_acc = tax_map[item_data["tax"]].get("account")

                item_rows.append({
                    "item": item_name,
                    "description": item_data.get("description", ""),
                    "account": item_data.get("income_account"),
                    "quantity": qty,
                    "rate": rate,
                    "tax_rate": tax_rate_val,
                    "tax_account": tax_acc,
                })

        if st.form_submit_button("Save Quote", type="primary", use_container_width=True):
            if not party:
                st.error("Customer is required.")
            elif not item_rows:
                st.error("At least one item is required.")
            else:
                totals = calculate_invoice_totals(item_rows)
                try:
                    name = create_quote(conn, {
                        "party": party,
                        "date": str(date),
                        "expiry_date": str(expiry),
                        "currency": currency,
                        "user_remark": user_remark,
                        "number_series": "QTE-",
                    }, item_rows)
                    st.success(f"Quote **{name}** created.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
