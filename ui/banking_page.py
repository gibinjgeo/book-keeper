"""
Banking UI — bank/cash accounts, deposits, withdrawals, transfers, reconciliation.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from services.banking import (
    get_all_bank_accounts, get_bank_account, create_bank_account,
    update_bank_account, get_bank_transactions,
    record_deposit, record_withdrawal, record_transfer,
    mark_reconciled, get_reconciliation_summary, get_bank_account_names,
)
from services.accounts import get_cash_and_bank_accounts


def render(conn):
    st.title("Banking")

    tabs = st.tabs(["Accounts", "Transactions", "New Transaction", "Reconciliation"])

    with tabs[0]:
        _render_accounts(conn)
    with tabs[1]:
        _render_transactions(conn)
    with tabs[2]:
        _render_new_transaction(conn)
    with tabs[3]:
        _render_reconciliation(conn)


def _render_accounts(conn):
    st.subheader("Bank & Cash Accounts")

    accounts = get_all_bank_accounts(conn)

    if accounts:
        df = pd.DataFrame(accounts)
        display_cols = ["name", "account_type", "bank_name", "currency", "opening_balance", "current_balance"]
        df_d = df[[c for c in display_cols if c in df.columns]].copy()
        df_d.columns = ["Account", "Type", "Bank", "Currency", "Opening Balance", "Current Balance"]
        for col in ["Opening Balance", "Current Balance"]:
            df_d[col] = df_d[col].apply(lambda x: f"{x:,.2f}")
        st.dataframe(df_d, use_container_width=True, hide_index=True)
    else:
        st.info("No bank accounts yet.")

    st.divider()
    _render_account_form(conn)


def _render_account_form(conn):
    with st.expander("Add / Edit Bank Account"):
        gl_accounts = [""] + get_cash_and_bank_accounts(conn)
        names = [""] + [a["name"] for a in get_all_bank_accounts(conn)]
        edit_name = st.selectbox("Edit existing (or leave blank to add new)", names, key="ba_edit_sel")

        existing = get_bank_account(conn, edit_name) if edit_name else {}

        with st.form("bank_account_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Account Name *", value=existing.get("name", ""))
                bank_name = st.text_input("Bank Name", value=existing.get("bank_name", ""))
                account_number = st.text_input("Account Number", value=existing.get("account_number", ""))
            with col2:
                acc_type = st.selectbox(
                    "Account Type",
                    ["Bank", "Cash", "Credit Card"],
                    index=["Bank", "Cash", "Credit Card"].index(existing.get("account_type", "Bank")),
                )
                currency = st.text_input("Currency", value=existing.get("currency", "USD"))
                opening_bal = st.number_input("Opening Balance", value=float(existing.get("opening_balance", 0)), step=0.01)

            gl_idx = gl_accounts.index(existing.get("gl_account", "")) if existing.get("gl_account") in gl_accounts else 0
            gl_account = st.selectbox("Linked GL Account", gl_accounts, index=gl_idx)

            if st.form_submit_button("Save Account", type="primary", use_container_width=True):
                if not name:
                    st.error("Account name is required.")
                else:
                    data = {
                        "name": name,
                        "account_type": acc_type,
                        "bank_name": bank_name,
                        "account_number": account_number,
                        "currency": currency,
                        "opening_balance": opening_bal,
                        "gl_account": gl_account or None,
                    }
                    if edit_name:
                        update_bank_account(conn, edit_name, data)
                        st.success(f"Account '{name}' updated.")
                    else:
                        create_bank_account(conn, data)
                        st.success(f"Account '{name}' created.")
                    st.rerun()


def _render_transactions(conn):
    st.subheader("Bank Transactions")

    accounts = get_bank_account_names(conn)
    if not accounts:
        st.info("No bank accounts. Create one in the Accounts tab.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        sel_account = st.selectbox("Account", ["All"] + accounts, key="bt_account")
    with col2:
        from_date = st.date_input("From", value=datetime(datetime.today().year, 1, 1), key="bt_from")
    with col3:
        to_date = st.date_input("To", value=datetime.today(), key="bt_to")

    reconciled_filter = st.selectbox("Reconciled", ["All", "Reconciled", "Unreconciled"], key="bt_rec")
    rec_val = None
    if reconciled_filter == "Reconciled":
        rec_val = 1
    elif reconciled_filter == "Unreconciled":
        rec_val = 0

    txns = get_bank_transactions(
        conn,
        bank_account=sel_account if sel_account != "All" else None,
        from_date=str(from_date),
        to_date=str(to_date),
        reconciled=rec_val,
    )

    if not txns:
        st.info("No transactions found.")
        return

    df = pd.DataFrame(txns)
    cols = ["id", "bank_account", "date", "transaction_type", "amount", "description", "reference", "reconciled"]
    df_d = df[[c for c in cols if c in df.columns]].copy()
    df_d.columns = ["ID", "Account", "Date", "Type", "Amount", "Description", "Reference", "Reconciled"]
    df_d["Amount"] = df_d["Amount"].apply(lambda x: f"{x:,.2f}")
    df_d["Reconciled"] = df_d["Reconciled"].apply(lambda x: "✓" if x else "")
    st.dataframe(df_d, use_container_width=True, hide_index=True)

    st.subheader("Mark as Reconciled")
    with st.form("reconcile_form"):
        txn_id = st.number_input("Transaction ID", min_value=1, step=1)
        is_rec = st.checkbox("Mark as reconciled", value=True)
        if st.form_submit_button("Update"):
            mark_reconciled(conn, int(txn_id), is_rec)
            st.success("Updated.")
            st.rerun()


def _render_new_transaction(conn):
    st.subheader("Record Transaction")

    accounts = get_bank_account_names(conn)
    if not accounts:
        st.info("Create a bank account first.")
        return

    txn_type = st.selectbox("Transaction Type", ["Deposit", "Withdrawal", "Transfer"], key="nt_type")

    with st.form("new_txn_form"):
        if txn_type == "Transfer":
            col1, col2 = st.columns(2)
            with col1:
                from_acc = st.selectbox("From Account *", accounts)
            with col2:
                to_acc = st.selectbox("To Account *", accounts)
        else:
            bank_account = st.selectbox("Bank Account *", accounts)

        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date", value=datetime.today())
            amount = st.number_input("Amount *", min_value=0.01, step=0.01)
        with col2:
            description = st.text_input("Description")
            reference = st.text_input("Reference")
            if txn_type != "Transfer":
                category = st.text_input("Category")

        if st.form_submit_button("Record Transaction", type="primary", use_container_width=True):
            date_str = str(date)
            if txn_type == "Deposit":
                record_deposit(conn, bank_account, date_str, amount, description, reference, category)
                st.success(f"Deposit of {amount:,.2f} recorded.")
            elif txn_type == "Withdrawal":
                record_withdrawal(conn, bank_account, date_str, amount, description, reference, category)
                st.success(f"Withdrawal of {amount:,.2f} recorded.")
            elif txn_type == "Transfer":
                if from_acc == to_acc:
                    st.error("From and To accounts must be different.")
                else:
                    record_transfer(conn, from_acc, to_acc, date_str, amount, description)
                    st.success(f"Transfer of {amount:,.2f} recorded.")
            st.rerun()


def _render_reconciliation(conn):
    st.subheader("Account Reconciliation")

    accounts = get_bank_account_names(conn)
    if not accounts:
        st.info("No bank accounts found.")
        return

    sel_acc = st.selectbox("Select Account", accounts, key="rec_acc")
    summary = get_reconciliation_summary(conn, sel_acc)

    col1, col2, col3 = st.columns(3)
    col1.metric("Opening Balance", f"{summary['opening_balance']:,.2f}")
    col2.metric("Reconciled Balance", f"{summary['reconciled_balance']:,.2f}")
    col3.metric("Current Balance", f"{summary['current_balance']:,.2f}")

    st.divider()
    unreconciled_txns = get_bank_transactions(conn, bank_account=sel_acc, reconciled=0)
    if unreconciled_txns:
        st.subheader(f"Unreconciled Transactions ({len(unreconciled_txns)})")
        df = pd.DataFrame(unreconciled_txns)
        cols = ["id", "date", "transaction_type", "amount", "description"]
        df_d = df[[c for c in cols if c in df.columns]].copy()
        df_d["amount"] = df_d["amount"].apply(lambda x: f"{x:,.2f}")
        st.dataframe(df_d, use_container_width=True, hide_index=True)

        if st.button("Mark All Unreconciled as Reconciled"):
            for txn in unreconciled_txns:
                mark_reconciled(conn, txn["id"], True)
            st.success("All transactions marked as reconciled.")
            st.rerun()
    else:
        st.success("All transactions are reconciled.")
