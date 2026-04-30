"""
Journal Entries UI — create, view, submit double-entry journal entries.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from services.journal import (
    get_all_journal_entries, get_journal_entry,
    create_journal_entry, update_journal_entry,
    submit_journal_entry, cancel_journal_entry, delete_journal_entry,
    ENTRY_TYPES, validate_journal_entry,
)
from services.accounts import get_account_names
from services.parties import get_party_names


def render(conn):
    st.title("Journal Entries")

    tab_list, tab_create = st.tabs(["Entry List", "New Entry"])

    with tab_list:
        _render_entry_list(conn)

    with tab_create:
        _render_create_entry(conn)


def _render_entry_list(conn):
    entries = get_all_journal_entries(conn)
    if not entries:
        st.info("No journal entries yet.")
        return

    df = pd.DataFrame(entries)
    cols = ["name", "date", "entry_type", "total_debit", "total_credit", "status", "user_remark"]
    df_d = df[[c for c in cols if c in df.columns]].copy()
    df_d.columns = ["Entry No", "Date", "Type", "Total Debit", "Total Credit", "Status", "Remark"]
    df_d["Total Debit"] = df_d["Total Debit"].apply(lambda x: f"{x:,.2f}")
    df_d["Total Credit"] = df_d["Total Credit"].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_d, use_container_width=True, hide_index=True)

    st.subheader("View / Manage Entry")
    je_names = [e["name"] for e in entries]
    selected = st.selectbox("Select entry", [""] + je_names, key="je_select")

    if selected:
        je = get_journal_entry(conn, selected)
        if je:
            _render_entry_detail(conn, je)


def _render_entry_detail(conn, je: dict):
    status = je.get("status", "Draft")
    st.markdown(f"**{je['name']}** — {je.get('entry_type')} — Status: **{status}**")
    st.caption(f"Date: {je.get('date')} | Remark: {je.get('user_remark')}")

    accounts = je.get("accounts", [])
    if accounts:
        df = pd.DataFrame(accounts)
        cols = ["account", "debit", "credit", "party", "reference_type", "reference_name"]
        df = df[[c for c in cols if c in df.columns]].copy()
        df.columns = ["Account", "Debit", "Credit", "Party", "Ref Type", "Ref Name"]
        df["Debit"] = df["Debit"].apply(lambda x: f"{x:,.2f}")
        df["Credit"] = df["Credit"].apply(lambda x: f"{x:,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Debit", f"{je.get('total_debit', 0):,.2f}")
    col2.metric("Total Credit", f"{je.get('total_credit', 0):,.2f}")
    balanced = abs(je.get("total_debit", 0) - je.get("total_credit", 0)) < 0.01
    col3.metric("Balanced", "Yes" if balanced else "No")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if status == "Draft":
            if st.button("Submit", type="primary", key=f"je_submit_{je['name']}"):
                try:
                    submit_journal_entry(conn, je["name"])
                    st.success("Journal entry submitted.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    with col_b:
        if status == "Submitted":
            if st.button("Cancel", key=f"je_cancel_{je['name']}"):
                try:
                    cancel_journal_entry(conn, je["name"])
                    st.success("Entry cancelled.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    with col_c:
        if status == "Draft":
            if st.button("Delete", key=f"je_del_{je['name']}"):
                ok, msg = delete_journal_entry(conn, je["name"])
                if ok:
                    st.success("Entry deleted.")
                    st.rerun()
                else:
                    st.error(msg)


def _render_create_entry(conn):
    st.subheader("New Journal Entry")
    account_names = get_account_names(conn)
    party_names = [""] + get_party_names(conn)

    with st.form("create_je_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            je_date = st.date_input("Date", value=datetime.today())
        with col2:
            entry_type = st.selectbox("Entry Type", ENTRY_TYPES)
        with col3:
            ref_number = st.text_input("Reference No.")

        user_remark = st.text_input("Remark / Narration")

        st.markdown("**Accounts (minimum 2 rows — Debits must equal Credits)**")
        num_rows = st.number_input("Number of rows", min_value=2, max_value=15, value=2, step=1)

        account_opts = [""] + account_names
        rows = []
        total_debit = 0.0
        total_credit = 0.0

        for idx in range(int(num_rows)):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
            with c1:
                account = st.selectbox("Account", account_opts, key=f"je_acc_{idx}")
            with c2:
                debit = st.number_input("Debit", min_value=0.0, step=0.01, format="%.2f", key=f"je_dr_{idx}")
            with c3:
                credit = st.number_input("Credit", min_value=0.0, step=0.01, format="%.2f", key=f"je_cr_{idx}")
            with c4:
                party = st.selectbox("Party", party_names, key=f"je_party_{idx}")

            if account:
                rows.append({
                    "account": account,
                    "debit": debit,
                    "credit": credit,
                    "party": party,
                    "reference_type": "",
                    "reference_name": "",
                })
                total_debit += debit
                total_credit += credit

        diff = abs(total_debit - total_credit)
        balance_status = "Balanced" if diff < 0.01 else f"Out of balance by {diff:,.2f}"
        st.info(
            f"Total Debit: {total_debit:,.2f} | Total Credit: {total_credit:,.2f} | {balance_status}"
        )

        if st.form_submit_button("Create Draft Entry", type="primary", use_container_width=True):
            if not rows:
                st.error("Please fill in account rows.")
            else:
                valid, msg = validate_journal_entry(rows)
                if not valid:
                    st.error(msg)
                else:
                    try:
                        name = create_journal_entry(
                            conn,
                            {
                                "date": str(je_date),
                                "entry_type": entry_type,
                                "user_remark": user_remark,
                                "reference_number": ref_number,
                                "number_series": "JV-",
                            },
                            rows,
                        )
                        st.success(f"Journal Entry {name} created as Draft.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
