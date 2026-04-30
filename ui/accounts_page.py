"""
Chart of Accounts UI — view, create, and manage accounts.
"""
import streamlit as st
import pandas as pd
from services.accounts import (
    get_all_accounts, create_account, update_account, delete_account
)

ROOT_TYPES = ["Asset", "Liability", "Equity", "Income", "Expense"]

ACCOUNT_TYPES = [
    "", "Accumulated Depreciation", "Asset Received But Not Billed",
    "Bank", "Cash", "Chargeable", "Cost of Goods Sold", "Depreciation",
    "Equity", "Expense Account", "Expenses Included In Asset Valuation",
    "Expenses Included In Valuation", "Fixed Asset", "Income Account",
    "Payable", "Receivable", "Round Off", "Stock", "Stock Adjustment",
    "Temporary", "Tax", "Write Off",
]


def render(conn):
    st.title("Chart of Accounts")

    tab_view, tab_create = st.tabs(["View Accounts", "Add Account"])

    with tab_view:
        _render_accounts_list(conn)

    with tab_create:
        _render_create_form(conn)


def _render_accounts_list(conn):
    accounts = get_all_accounts(conn)
    if not accounts:
        st.info("No accounts found. Run company setup to load the standard chart of accounts.")
        return

    df = pd.DataFrame(accounts)
    display_cols = ["name", "root_type", "account_type", "parent_account", "is_group"]
    df_display = df[display_cols].copy()
    df_display.columns = ["Account", "Root Type", "Account Type", "Parent Account", "Group"]
    df_display["Group"] = df_display["Group"].map({1: "Yes", 0: "No"})

    root_filter = st.selectbox("Filter by Root Type", ["All"] + ROOT_TYPES, key="acc_filter")
    if root_filter != "All":
        df_display = df_display[df_display["Root Type"] == root_filter]

    st.dataframe(df_display, use_container_width=True, hide_index=True)
    st.caption(f"Total: {len(df_display)} accounts")

    st.subheader("Edit / Delete Account")
    account_names = [a["name"] for a in accounts]
    selected = st.selectbox("Select account", [""] + account_names, key="acc_select_edit")

    if selected:
        acc = next((a for a in accounts if a["name"] == selected), None)
        if acc:
            with st.form("edit_account_form"):
                new_name = st.text_input("Account Name", value=acc["name"])
                new_root = st.selectbox("Root Type", ROOT_TYPES,
                                        index=ROOT_TYPES.index(acc["root_type"]) if acc["root_type"] in ROOT_TYPES else 0)
                new_type = st.selectbox("Account Type", ACCOUNT_TYPES,
                                        index=ACCOUNT_TYPES.index(acc["account_type"]) if acc["account_type"] in ACCOUNT_TYPES else 0)
                parent_opts = [""] + [a["name"] for a in accounts if a["is_group"] == 1]
                parent_val = acc.get("parent_account") or ""
                parent_idx = parent_opts.index(parent_val) if parent_val in parent_opts else 0
                new_parent = st.selectbox("Parent Account", parent_opts, index=parent_idx)
                new_is_group = st.checkbox("Is Group Account", value=bool(acc["is_group"]))

                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Save Changes", use_container_width=True):
                        try:
                            update_account(
                                conn, selected, new_name, new_root, new_type,
                                new_parent or None, 1 if new_is_group else 0
                            )
                            st.success("Account updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                with col2:
                    if st.form_submit_button("Delete Account", type="secondary", use_container_width=True):
                        ok, msg = delete_account(conn, selected)
                        if ok:
                            st.success("Account deleted.")
                            st.rerun()
                        else:
                            st.error(msg)


def _render_create_form(conn):
    st.subheader("Create New Account")
    accounts = get_all_accounts(conn)
    group_accounts = [a["name"] for a in accounts if a["is_group"] == 1]

    with st.form("create_account_form"):
        name = st.text_input("Account Name *", placeholder="e.g., Office Supplies")
        root_type = st.selectbox("Root Type *", ROOT_TYPES)
        account_type = st.selectbox("Account Type", ACCOUNT_TYPES)
        parent_account = st.selectbox("Parent Account", [""] + group_accounts)
        is_group = st.checkbox("Is Group Account")

        if st.form_submit_button("Create Account", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Account name is required.")
            else:
                try:
                    create_account(
                        conn,
                        name.strip(),
                        root_type,
                        account_type,
                        parent_account or None,
                        1 if is_group else 0,
                    )
                    st.success(f"Account '{name}' created.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
