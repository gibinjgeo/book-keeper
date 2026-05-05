"""
Financial Reports UI — all reports with CSV export.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date

from backend.reports import (
    general_ledger, trial_balance, balance_sheet, profit_and_loss,
    accounts_receivable, accounts_payable,
    ar_aging, ap_aging, tax_summary,
    sales_by_customer, purchases_by_supplier,
    item_sales_report, cash_flow_summary, bank_account_summary,
)
from services.accounts import get_account_names
from services.parties import get_party_names

TRANSACTION_TYPES = ["All", "SalesInvoice", "PurchaseInvoice", "Payment", "JournalEntry"]

REPORTS = [
    "General Ledger",
    "Trial Balance",
    "Balance Sheet",
    "Profit & Loss",
    "Accounts Receivable",
    "Accounts Payable",
    "AR Aging",
    "AP Aging",
    "Tax Summary",
    "Sales by Customer",
    "Purchases by Supplier",
    "Item Sales Report",
    "Cash Flow Summary",
    "Bank Account Summary",
]


def render(conn):
    st.title("Financial Reports")

    report = st.selectbox("Select Report", REPORTS)

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
    elif report == "AR Aging":
        _render_ar_aging(conn)
    elif report == "AP Aging":
        _render_ap_aging(conn)
    elif report == "Tax Summary":
        _render_tax_summary(conn)
    elif report == "Sales by Customer":
        _render_sales_by_customer(conn)
    elif report == "Purchases by Supplier":
        _render_purchases_by_supplier(conn)
    elif report == "Item Sales Report":
        _render_item_sales(conn)
    elif report == "Cash Flow Summary":
        _render_cash_flow(conn)
    elif report == "Bank Account Summary":
        _render_bank_summary(conn)


def _date_filters(key_prefix: str):
    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("From Date", value=date(datetime.today().year, 1, 1), key=f"{key_prefix}_from")
    with col2:
        to_date = st.date_input("To Date", value=datetime.today(), key=f"{key_prefix}_to")
    return str(from_date), str(to_date)


def _csv_download(df: pd.DataFrame, filename: str):
    if not df.empty:
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", data=csv.encode(), file_name=filename, mime="text/csv")


def _render_general_ledger(conn):
    st.subheader("General Ledger")
    with st.expander("Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            from_date = st.date_input("From Date", value=date(datetime.today().year, 1, 1), key="gl_from")
        with col2:
            to_date = st.date_input("To Date", value=datetime.today(), key="gl_to")
        with col3:
            txn_type = st.selectbox("Transaction Type", TRANSACTION_TYPES)
        col4, col5 = st.columns(2)
        with col4:
            account_filter = st.selectbox("Account", [""] + get_account_names(conn), key="gl_acc")
        with col5:
            party_filter = st.selectbox("Party", [""] + get_party_names(conn), key="gl_party")

    df = general_ledger(
        conn, from_date=str(from_date), to_date=str(to_date),
        account=account_filter or None, party=party_filter or None, transaction_type=txn_type,
    )
    if df.empty:
        st.info("No entries found.")
        return

    df_display = df.copy()
    df_display["debit"] = df_display["debit"].apply(lambda x: f"{x:,.2f}")
    df_display["credit"] = df_display["credit"].apply(lambda x: f"{x:,.2f}")
    df_display["balance"] = df_display["balance"].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"general_ledger_{date.today()}.csv")


def _render_trial_balance(conn):
    st.subheader("Trial Balance")
    from_date, to_date = _date_filters("tb")
    df = trial_balance(conn, from_date=from_date, to_date=to_date)
    if df.empty:
        st.info("No accounts found.")
        return

    df = df[df["total_debit"] + df["total_credit"] > 0]
    total_dr = df["total_debit"].sum()
    total_cr = df["total_credit"].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Debits", f"{total_dr:,.2f}")
    col2.metric("Total Credits", f"{total_cr:,.2f}")
    diff = abs(total_dr - total_cr)
    col3.metric("Difference", f"{diff:,.2f}")
    if diff > 0.01:
        st.error("Trial balance is NOT balanced. Review ledger entries.")

    df_display = df[["account", "root_type", "total_debit", "total_credit", "balance"]].copy()
    for col in ["total_debit", "total_credit", "balance"]:
        df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"trial_balance_{date.today()}.csv")


def _render_balance_sheet(conn):
    st.subheader("Balance Sheet")
    as_of_date = st.date_input("As of Date", value=datetime.today(), key="bs_date")
    data = balance_sheet(conn, as_of_date=str(as_of_date))

    def _section(title: str, items: list, sign: int = 1) -> float:
        st.markdown(f"**{title}**")
        total = 0.0
        rows = []
        for item in items:
            bal = item.get("balance", 0) * sign
            total += bal
            rows.append({"Account": item["account"], "Balance": f"{bal:,.2f}"})
            for child in item.get("children", []):
                c_bal = child.get("balance", 0) * sign
                total += c_bal
                rows.append({"Account": f"  {child['account']}", "Balance": f"{c_bal:,.2f}"})
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        return total

    col1, col2 = st.columns(2)
    with col1:
        total_assets = _section("Assets", data.get("Asset", []))
        st.metric("Total Assets", f"{total_assets:,.2f}")
    with col2:
        total_liabilities = _section("Liabilities", data.get("Liability", []), sign=-1)
        total_equity = _section("Equity", data.get("Equity", []), sign=-1)
        st.metric("Total Liabilities + Equity", f"{total_liabilities + total_equity:,.2f}")


def _render_profit_and_loss(conn):
    st.subheader("Profit & Loss")
    from_date, to_date = _date_filters("pl")
    data = profit_and_loss(conn, from_date=from_date, to_date=to_date)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Income", f"{data['total_income']:,.2f}")
    col2.metric("Total Expenses", f"{data['total_expense']:,.2f}")
    profit = data["net_profit"]
    col3.metric("Net Profit / Loss", f"{profit:,.2f}",
                delta=f"{'Profit' if profit >= 0 else 'Loss'}",
                delta_color="normal" if profit >= 0 else "inverse")

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Income**")
        rows = [{"Account": k, "Balance": f"{abs(v['balance']):,.2f}"}
                for k, v in data["income"].items() if not v["is_group"]]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with col_r:
        st.markdown("**Expenses**")
        rows = [{"Account": k, "Balance": f"{abs(v['balance']):,.2f}"}
                for k, v in data["expense"].items() if not v["is_group"]]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_accounts_receivable(conn):
    st.subheader("Accounts Receivable")
    as_of = st.date_input("As of Date", value=datetime.today(), key="ar_date")
    df = accounts_receivable(conn, as_of_date=str(as_of))
    if df.empty:
        st.info("No outstanding receivables.")
        return
    total = df["outstanding_amount"].sum()
    st.metric("Total Outstanding", f"{total:,.2f}")
    df_display = df.copy()
    for col in ["grand_total", "outstanding_amount"]:
        df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"ar_{date.today()}.csv")


def _render_accounts_payable(conn):
    st.subheader("Accounts Payable")
    as_of = st.date_input("As of Date", value=datetime.today(), key="ap_date")
    df = accounts_payable(conn, as_of_date=str(as_of))
    if df.empty:
        st.info("No outstanding payables.")
        return
    total = df["outstanding_amount"].sum()
    st.metric("Total Outstanding", f"{total:,.2f}")
    df_display = df.copy()
    for col in ["grand_total", "outstanding_amount"]:
        df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"ap_{date.today()}.csv")


def _render_ar_aging(conn):
    st.subheader("AR Aging Report")
    as_of = st.date_input("As of Date", value=datetime.today(), key="ar_aging_date")
    df = ar_aging(conn, as_of_date=str(as_of))
    if df.empty:
        st.info("No outstanding receivables.")
        return
    df_display = df.copy()
    for col in ["Outstanding", "Current", "1-30 Days", "31-60 Days", "61-90 Days", "90+ Days"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"ar_aging_{date.today()}.csv")


def _render_ap_aging(conn):
    st.subheader("AP Aging Report")
    as_of = st.date_input("As of Date", value=datetime.today(), key="ap_aging_date")
    df = ap_aging(conn, as_of_date=str(as_of))
    if df.empty:
        st.info("No outstanding payables.")
        return
    df_display = df.copy()
    for col in ["Outstanding", "Current", "1-30 Days", "31-60 Days", "61-90 Days", "90+ Days"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"ap_aging_{date.today()}.csv")


def _render_tax_summary(conn):
    st.subheader("Tax Summary")
    from_date, to_date = _date_filters("tax")
    data = tax_summary(conn, from_date=from_date, to_date=to_date)

    col1, col2, col3 = st.columns(3)
    col1.metric("Tax Collected (Sales)", f"{data['total_collected']:,.2f}")
    col2.metric("Tax Paid (Purchases)", f"{data['total_paid']:,.2f}")
    net = data["net_payable"]
    col3.metric("Net Tax Payable", f"{net:,.2f}",
                delta_color="normal" if net >= 0 else "inverse")

    if data["breakdown"]:
        df = pd.DataFrame(data["breakdown"])
        df.rename(columns={"rate": "Tax Rate %", "collected": "Collected", "paid": "Paid", "net": "Net Payable"}, inplace=True)
        df_display = df.copy()
        for col in ["Collected", "Paid", "Net Payable"]:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("No tax transactions found.")


def _render_sales_by_customer(conn):
    st.subheader("Sales by Customer")
    from_date, to_date = _date_filters("sbc")
    df = sales_by_customer(conn, from_date=from_date, to_date=to_date)
    if df.empty:
        st.info("No sales data found.")
        return
    df.rename(columns={
        "customer": "Customer", "invoice_count": "Invoices",
        "net_total": "Net Total", "tax_total": "Tax",
        "grand_total": "Grand Total", "outstanding": "Outstanding",
    }, inplace=True)
    df_display = df.copy()
    for col in ["Net Total", "Tax", "Grand Total", "Outstanding"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"sales_by_customer_{date.today()}.csv")


def _render_purchases_by_supplier(conn):
    st.subheader("Purchases by Supplier")
    from_date, to_date = _date_filters("pbs")
    df = purchases_by_supplier(conn, from_date=from_date, to_date=to_date)
    if df.empty:
        st.info("No purchase data found.")
        return
    df.rename(columns={
        "supplier": "Supplier", "invoice_count": "Bills",
        "net_total": "Net Total", "tax_total": "Tax",
        "grand_total": "Grand Total", "outstanding": "Outstanding",
    }, inplace=True)
    df_display = df.copy()
    for col in ["Net Total", "Tax", "Grand Total", "Outstanding"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"purchases_by_supplier_{date.today()}.csv")


def _render_item_sales(conn):
    st.subheader("Item Sales Report")
    from_date, to_date = _date_filters("isr")
    df = item_sales_report(conn, from_date=from_date, to_date=to_date)
    if df.empty:
        st.info("No item sales data found.")
        return
    df.rename(columns={
        "item": "Item", "total_qty": "Qty Sold",
        "net_amount": "Net Amount", "tax_amount": "Tax",
        "invoice_count": "Invoices",
    }, inplace=True)
    df_display = df.copy()
    for col in ["Net Amount", "Tax"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"item_sales_{date.today()}.csv")


def _render_cash_flow(conn):
    st.subheader("Cash Flow Summary")
    from_date, to_date = _date_filters("cf")
    data = cash_flow_summary(conn, from_date=from_date, to_date=to_date)

    col1, col2, col3 = st.columns(3)
    col1.metric("Operating Inflows", f"{data['operating_inflow']:,.2f}")
    col2.metric("Operating Outflows", f"{data['operating_outflow']:,.2f}")
    col3.metric("Net Operating", f"{data['net_operating']:,.2f}",
                delta_color="normal" if data["net_operating"] >= 0 else "inverse")

    st.divider()
    col4, col5, col6 = st.columns(3)
    col4.metric("Bank Inflows", f"{data['bank_inflow']:,.2f}")
    col5.metric("Bank Outflows", f"{data['bank_outflow']:,.2f}")
    col6.metric("Net Cash Position", f"{data['net_cash']:,.2f}",
                delta_color="normal" if data["net_cash"] >= 0 else "inverse")


def _render_bank_summary(conn):
    st.subheader("Bank Account Summary")
    df = bank_account_summary(conn)
    if df.empty:
        st.info("No bank accounts configured.")
        return
    total_balance = df["Current Balance"].sum()
    st.metric("Total Cash & Bank Balance", f"{total_balance:,.2f}")
    df_display = df.copy()
    for col in ["Opening Balance", "Movements", "Current Balance"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    _csv_download(df, f"bank_summary_{date.today()}.csv")
