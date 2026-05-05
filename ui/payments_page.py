"""
Payments UI — Receive from customers, Pay to suppliers.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from services.payments import (
    get_all_payments, get_payment,
    create_payment, submit_payment, cancel_payment, delete_payment,
    get_outstanding_invoices,
)
from services.parties import get_party_names
from services.accounts import (
    get_account_names, get_receivable_accounts,
    get_payable_accounts, get_cash_and_bank_accounts,
)

PAYMENT_METHODS = ["Cash", "Bank Transfer", "Cheque", "Card", "Online"]


def render(conn):
    st.title("Payments")

    open_new = st.session_state.pop("_new_payment", False)

    if open_new:
        tabs = st.tabs(["New Payment", "Payment List"])
        with tabs[0]:
            _render_create_payment(conn)
        with tabs[1]:
            _render_payment_list(conn)
    else:
        tabs = st.tabs(["Payment List", "New Payment"])
        with tabs[0]:
            _render_payment_list(conn)
        with tabs[1]:
            _render_create_payment(conn)


def _render_payment_list(conn):
    payments = get_all_payments(conn)
    if not payments:
        st.info("No payments yet.")
        return

    df = pd.DataFrame(payments)
    cols = ["name", "party", "date", "payment_type", "amount", "payment_method", "status"]
    df_d = df[[c for c in cols if c in df.columns]].copy()
    df_d.columns = ["Payment No", "Party", "Date", "Type", "Amount", "Method", "Status"]
    df_d["Amount"] = df_d["Amount"].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_d, use_container_width=True, hide_index=True)

    st.subheader("View / Manage Payment")
    pmt_names = [p["name"] for p in payments]
    selected = st.selectbox("Select payment", [""] + pmt_names, key="pmt_select")

    if selected:
        pmt = get_payment(conn, selected)
        if pmt:
            _render_payment_detail(conn, pmt)


def _render_payment_detail(conn, pmt: dict):
    status = pmt.get("status", "Draft")
    ptype = pmt.get("payment_type", "Receive")
    st.markdown(f"**{pmt['name']}** — **{ptype}** — Status: **{status}**")

    col1, col2, col3 = st.columns(3)
    col1.metric("Party", pmt.get("party", ""))
    col2.metric("Amount", f"{pmt.get('amount', 0):,.2f}")
    col3.metric("Method", pmt.get("payment_method", ""))

    st.caption(f"From: {pmt.get('account')} → To: {pmt.get('payment_account')} | Date: {pmt.get('date')}")

    refs = pmt.get("for_references", [])
    if refs:
        df_refs = pd.DataFrame(refs)
        df_refs = df_refs[["reference_type", "reference_name", "amount"]].copy()
        df_refs.columns = ["Type", "Reference", "Amount"]
        df_refs["Amount"] = df_refs["Amount"].apply(lambda x: f"{x:,.2f}")
        st.markdown("**Applied Against:**")
        st.dataframe(df_refs, use_container_width=True, hide_index=True)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if status == "Draft":
            if st.button("Submit", type="primary", key=f"pmt_submit_{pmt['name']}"):
                try:
                    submit_payment(conn, pmt["name"])
                    st.success("Payment submitted.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    with col_b:
        if status == "Submitted":
            if st.button("Cancel", key=f"pmt_cancel_{pmt['name']}"):
                try:
                    cancel_payment(conn, pmt["name"])
                    st.success("Payment cancelled.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    with col_c:
        if status == "Draft":
            if st.button("Delete", key=f"pmt_del_{pmt['name']}"):
                ok, msg = delete_payment(conn, pmt["name"])
                if ok:
                    st.success("Deleted.")
                    st.rerun()
                else:
                    st.error(msg)


def _render_create_payment(conn):
    st.subheader("New Payment")

    all_party_names = get_party_names(conn)
    cash_bank = get_cash_and_bank_accounts(conn)
    all_accounts = get_account_names(conn)
    receivable_accs = get_receivable_accounts(conn)
    payable_accs = get_payable_accounts(conn)

    if not all_party_names:
        st.warning("No parties found. Add a customer or supplier first.")
        return

    payment_type = st.radio("Payment Type", ["Receive", "Pay"], horizontal=True)

    if payment_type == "Receive":
        party_role = "Customer"
        from_account_label = "Receivable Account (From)"
        to_account_label = "Cash/Bank Account (To)"
        from_account_opts = receivable_accs or all_accounts
        to_account_opts = cash_bank or all_accounts
    else:
        party_role = "Supplier"
        from_account_label = "Cash/Bank Account (From)"
        to_account_label = "Payable Account (To)"
        from_account_opts = cash_bank or all_accounts
        to_account_opts = payable_accs or all_accounts

    party_names = get_party_names(conn, party_role)
    party_names = party_names if party_names else all_party_names

    with st.form("create_pmt_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            party = st.selectbox("Party *", party_names)
            pmt_date = st.date_input("Date", value=datetime.today())
            method = st.selectbox("Payment Method", PAYMENT_METHODS)
        with col2:
            amount = st.number_input("Amount *", min_value=0.0, step=0.01, format="%.2f")
            from_account = st.selectbox(from_account_label, [""] + from_account_opts)
            to_account = st.selectbox(to_account_label, [""] + to_account_opts)

        user_remark = st.text_input("Remark")

        # Show outstanding invoices for reference
        if party:
            outstanding = get_outstanding_invoices(conn, party, payment_type)
            references = []
            if outstanding:
                st.markdown("**Outstanding Invoices (select to allocate):**")
                for inv in outstanding:
                    checked = st.checkbox(
                        f"{inv['name']} — {inv['date']} — Grand: {inv['grand_total']:,.2f} — Outstanding: {inv['outstanding_amount']:,.2f}",
                        key=f"ref_{inv['name']}",
                    )
                    if checked:
                        alloc = st.number_input(
                            f"Allocate to {inv['name']}",
                            min_value=0.0,
                            max_value=float(inv["outstanding_amount"]),
                            value=min(float(amount), float(inv["outstanding_amount"])),
                            step=0.01,
                            format="%.2f",
                            key=f"alloc_{inv['name']}",
                        )
                        references.append({
                            "reference_type": inv["ref_type"],
                            "reference_name": inv["name"],
                            "amount": alloc,
                        })

        if st.form_submit_button("Create Payment", type="primary", use_container_width=True):
            if amount <= 0:
                st.error("Amount must be greater than zero.")
            elif not from_account:
                st.error(f"{from_account_label} is required.")
            elif not to_account:
                st.error(f"{to_account_label} is required.")
            else:
                try:
                    name = create_payment(
                        conn,
                        {
                            "party": party,
                            "date": str(pmt_date),
                            "payment_type": payment_type,
                            "payment_method": method,
                            "amount": amount,
                            "account": from_account,
                            "payment_account": to_account,
                            "user_remark": user_remark,
                            "number_series": "PAY-",
                        },
                        references if outstanding else [],
                    )
                    st.success(f"Payment {name} created as Draft.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
