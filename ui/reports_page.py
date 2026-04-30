"""
Financial Reports UI — General Ledger, Trial Balance, Balance Sheet, P&L.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date

from backend.reports import (
    general_ledger, trial_balance, balance_sheet, profit_and_loss,
    accounts_receivable, accounts_payable,
)
from services.accounts import get_account_names
from services.parties import get_party_names

TRANSACTION_TYPES = ["All", "SalesInvoice", "PurchaseInvoice", "Payment", "JournalEntry"]


def render(conn):
    st.title("Financial Reports")

    report = st.selectbox(
        "Select Report",
        [
            "General Ledger",
            "Trial Balance",
            "Balance Sheet",
            "Profit & Loss",
            "Accounts Receivable",
            "Accounts Payable",
        ],
    )

    if report == "General Ledger":
        _render_general_ledger(conn)
    elif report == "Trial Balance":
        _render_trial_balance(conn)
    elif report == "Balance Sheet":
        _render_balance_sheet(conn)
    elif report == "Profit & Loss":
        _render_profit_and_loss(conn)
    elif report == "Accounts Receivable":
        _render_accounts_receivable(conn)
    elif report == "Accounts Payable":
        _render_accounts_payable(conn)


def _render_general_ledger(conn):
    st.subheader("General Ledger")

    with st.expander("Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            from_date = st.date_input(
                "From Date",
                value=date(datetime.today().year, 1, 1),
                key="gl_from",
            )
        with col2:
            to_date = st.date_input("To Date", value=datetime.today(), key="gl_to")
        with col3:
            txn_type = st.selectbox("Transaction Type", TRANSACTION_TYPES)

        col4, col5 = st.columns(2)
        with col4:
            account_names = [""] + get_account_names(conn)
            account_filter = st.selectbox("Account", account_names, key="gl_acc")
        with col5:
            party_names = [""] + get_party_names(conn)
            party_filter = st.selectbox("Party", party_names, key="gl_party")

    df = general_ledger(
        conn,
        from_date=str(from_date),
        to_date=str(to_date),
        account=account_filter or None,
        party=party_filter or None,
        transaction_type=txn_type,
    )

    if df.empty:
        st.info("No ledger entries found for the selected filters.")
        return

    display = df.copy()
    display["debit"] = display["debit"].apply(lambda x: f"{x:,.2f}")
    display["credit"] = display["credit"].apply(lambda x: f"{x:,.2f}")
    display["balance"] = display["balance"].apply(lambda x: f"{x:,.2f}")
    display.columns = ["Date", "Account", "Party", "Debit", "Credit", "Txn Type", "Reference", "Balance"]

    st.dataframe(display, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    col1.metric("Total Debit", f"{df['debit'].sum():,.2f}")
    col2.metric("Total Credit", f"{df['credit'].sum():,.2f}")

    csv = df.to_csv(index=False)
    st.download_button(
        "Download CSV", csv, "general_ledger.csv", "text/csv"
    )


def _render_trial_balance(conn):
    st.subheader("Trial Balance")

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input(
            "From Date", value=date(datetime.today().year, 1, 1), key="tb_from"
        )
    with col2:
        to_date = st.date_input("To Date", value=datetime.today(), key="tb_to")

    df = trial_balance(conn, from_date=str(from_date), to_date=str(to_date))

    if df.empty:
        st.info("No data for trial balance.")
        return

    hide_zero = st.checkbox("Hide zero-balance accounts", value=True)
    if hide_zero:
        df = df[df["balance"].abs() > 0.001]

    display = df.copy()
    display["total_debit"] = display["total_debit"].apply(lambda x: f"{x:,.2f}")
    display["total_credit"] = display["total_credit"].apply(lambda x: f"{x:,.2f}")
    display["balance"] = display["balance"].apply(lambda x: f"{x:,.2f}")
    display = display[["account", "root_type", "total_debit", "total_credit", "balance"]]
    display.columns = ["Account", "Root Type", "Debit", "Credit", "Balance"]

    st.dataframe(display, use_container_width=True, hide_index=True)

    total_dr = df["total_debit"].sum()
    total_cr = df["total_credit"].sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Debit", f"{total_dr:,.2f}")
    col2.metric("Total Credit", f"{total_cr:,.2f}")
    col3.metric("Difference", f"{abs(total_dr - total_cr):,.2f}")

    csv = df.to_csv(index=False)
    st.download_button("Download CSV", csv, "trial_balance.csv", "text/csv")


def _render_balance_sheet(conn):
    st.subheader("Balance Sheet")

    as_of = st.date_input("As of Date", value=datetime.today(), key="bs_date")
    data = balance_sheet(conn, as_of_date=str(as_of))

    if not any(data.values()):
        st.info("No data available. Submit some transactions first.")
        return

    for root_type in ["Asset", "Liability", "Equity"]:
        accounts = data.get(root_type, [])
        if accounts:
            st.markdown(f"#### {root_type}")
            rows = _flatten_account_tree(accounts)
            if rows:
                df = pd.DataFrame(rows)
                df["balance"] = df["balance"].apply(lambda x: f"{x:,.2f}")
                df = df[["indent", "account", "balance"]]
                df.columns = ["  ", "Account", "Balance"]
                st.dataframe(df, use_container_width=True, hide_index=True)


def _flatten_account_tree(nodes: list, depth: int = 0) -> list:
    rows = []
    for node in nodes:
        rows.append({
            "indent": "  " * depth,
            "account": node["account"],
            "balance": abs(node.get("balance", 0)),
        })
        for child in node.get("children", []):
            rows.extend(_flatten_account_tree([child], depth + 1))
    return rows


def _render_profit_and_loss(conn):
    st.subheader("Profit & Loss Statement")

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input(
            "From Date", value=date(datetime.today().year, 1, 1), key="pl_from"
        )
    with col2:
        to_date = st.date_input("To Date", value=datetime.today(), key="pl_to")

    data = profit_and_loss(conn, from_date=str(from_date), to_date=str(to_date))

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Income", f"{data['total_income']:,.2f}")
    col2.metric("Total Expense", f"{data['total_expense']:,.2f}")
    col3.metric(
        "Net Profit" if data["net_profit"] >= 0 else "Net Loss",
        f"{abs(data['net_profit']):,.2f}",
        delta=f"{'Profit' if data['net_profit'] >= 0 else 'Loss'}",
        delta_color="normal" if data["net_profit"] >= 0 else "inverse",
    )

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Income**")
        if data["income"]:
            inc_rows = [
                {"Account": k, "Amount": f"{abs(v['balance']):,.2f}"}
                for k, v in data["income"].items()
                if not v["is_group"] and abs(v["balance"]) > 0
            ]
            if inc_rows:
                st.dataframe(pd.DataFrame(inc_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No income entries.")

    with col_r:
        st.markdown("**Expenses**")
        if data["expense"]:
            exp_rows = [
                {"Account": k, "Amount": f"{abs(v['balance']):,.2f}"}
                for k, v in data["expense"].items()
                if not v["is_group"] and abs(v["balance"]) > 0
            ]
            if exp_rows:
                st.dataframe(pd.DataFrame(exp_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No expense entries.")


def _render_accounts_receivable(conn):
    st.subheader("Accounts Receivable")
    as_of = st.date_input("As of Date", value=datetime.today(), key="ar_date")
    df = accounts_receivable(conn, as_of_date=str(as_of))

    if df.empty:
        st.info("No outstanding receivables.")
        return

    df["grand_total"] = df["grand_total"].apply(lambda x: f"{x:,.2f}")
    df["outstanding_amount"] = df["outstanding_amount"].apply(lambda x: f"{x:,.2f}")
    df.columns = ["Invoice", "Customer", "Date", "Due Date", "Grand Total", "Outstanding", "Status"]
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_accounts_payable(conn):
    st.subheader("Accounts Payable")
    as_of = st.date_input("As of Date", value=datetime.today(), key="ap_date")
    df = accounts_payable(conn, as_of_date=str(as_of))

    if df.empty:
        st.info("No outstanding payables.")
        return

    df["grand_total"] = df["grand_total"].apply(lambda x: f"{x:,.2f}")
    df["outstanding_amount"] = df["outstanding_amount"].apply(lambda x: f"{x:,.2f}")
    df.columns = ["Invoice", "Supplier", "Date", "Due Date", "Grand Total", "Outstanding", "Status"]
    st.dataframe(df, use_container_width=True, hide_index=True)
