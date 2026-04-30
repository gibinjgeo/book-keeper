"""
Items (Products & Services) and Tax management UI.
"""
import streamlit as st
import pandas as pd
from services.items import (
    get_all_items, get_item, create_item, update_item, delete_item,
    get_item_groups, get_tax_names,
    get_all_taxes, create_tax, update_tax, delete_tax,
)
from services.accounts import get_account_names

FOR_PURPOSE = ["Both", "Sales", "Purchases"]
ITEM_TYPES = ["Product", "Service"]


def render(conn):
    st.title("Items")

    tab_items, tab_taxes = st.tabs(["Items", "Taxes"])

    with tab_items:
        _render_items(conn)

    with tab_taxes:
        _render_taxes(conn)


def _render_items(conn):
    tab_list, tab_create = st.tabs(["Item List", "Add Item"])

    with tab_list:
        purpose_filter = st.radio(
            "Purpose", ["All", "Sales", "Purchases"], horizontal=True, key="item_purp_filter"
        )
        items = get_all_items(conn, None if purpose_filter == "All" else purpose_filter)

        if not items:
            st.info("No items found. Add products or services to get started.")
        else:
            df = pd.DataFrame(items)
            cols = ["name", "item_type", "for_purpose", "unit", "rate", "tax"]
            df_d = df[[c for c in cols if c in df.columns]].copy()
            df_d.columns = ["Name", "Type", "Purpose", "Unit", "Rate", "Tax"]
            df_d["Rate"] = df_d["Rate"].apply(lambda x: f"{x:,.2f}")
            st.dataframe(df_d, use_container_width=True, hide_index=True)

        st.subheader("Edit Item")
        item_names = [i["name"] for i in items] if items else []
        selected = st.selectbox("Select item", [""] + item_names, key="item_select_edit")

        if selected:
            itm = get_item(conn, selected)
            if itm:
                _render_item_form(conn, itm, is_edit=True)

    with tab_create:
        st.subheader("Add New Item")
        _render_item_form(conn, None, is_edit=False)


def _render_item_form(conn, item: dict | None, is_edit: bool):
    account_names = [""] + get_account_names(conn)
    item_groups = [""] + get_item_groups(conn)
    tax_names = [""] + get_tax_names(conn)

    form_key = "edit_item_form" if is_edit else "create_item_form"

    with st.form(form_key):
        name = st.text_input("Item Name *", value=item["name"] if item else "")
        item_code = st.text_input("Item Code", value=item.get("item_code", "") if item else "")
        col1, col2 = st.columns(2)
        with col1:
            purpose_val = item.get("for_purpose", "Both") if item else "Both"
            purpose_idx = FOR_PURPOSE.index(purpose_val) if purpose_val in FOR_PURPOSE else 0
            for_purpose = st.selectbox("Purpose", FOR_PURPOSE, index=purpose_idx)

            type_val = item.get("item_type", "Product") if item else "Product"
            type_idx = ITEM_TYPES.index(type_val) if type_val in ITEM_TYPES else 0
            item_type = st.selectbox("Item Type", ITEM_TYPES, index=type_idx)

            group_val = item.get("item_group") or "" if item else ""
            group_idx = item_groups.index(group_val) if group_val in item_groups else 0
            item_group = st.selectbox("Item Group", item_groups, index=group_idx)

        with col2:
            unit = st.text_input("Unit", value=item.get("unit", "Unit") if item else "Unit")
            rate = st.number_input("Rate", value=float(item.get("rate", 0)) if item else 0.0, min_value=0.0, step=0.01, format="%.2f")
            barcode = st.text_input("Barcode", value=item.get("barcode", "") if item else "")

        description = st.text_area("Description", value=item.get("description", "") if item else "")

        col3, col4, col5 = st.columns(3)
        with col3:
            inc_val = item.get("income_account") or "" if item else ""
            inc_idx = account_names.index(inc_val) if inc_val in account_names else 0
            income_account = st.selectbox("Income Account", account_names, index=inc_idx)
        with col4:
            exp_val = item.get("expense_account") or "" if item else ""
            exp_idx = account_names.index(exp_val) if exp_val in account_names else 0
            expense_account = st.selectbox("Expense Account", account_names, index=exp_idx)
        with col5:
            tax_val = item.get("tax") or "" if item else ""
            tax_idx = tax_names.index(tax_val) if tax_val in tax_names else 0
            tax = st.selectbox("Tax", tax_names, index=tax_idx)

        track_item = st.checkbox("Track Inventory", value=bool(item.get("track_item", False)) if item else False)

        if is_edit:
            col_s, col_d = st.columns(2)
            with col_s:
                save = st.form_submit_button("Save Changes", use_container_width=True)
            with col_d:
                delete = st.form_submit_button("Delete Item", type="secondary", use_container_width=True)

            if save:
                _save_item(conn, item["name"], {
                    "name": name, "item_code": item_code, "item_group": item_group or None,
                    "for_purpose": for_purpose, "item_type": item_type, "unit": unit,
                    "rate": rate, "description": description,
                    "income_account": income_account or None,
                    "expense_account": expense_account or None,
                    "tax": tax or None, "track_item": track_item, "barcode": barcode,
                }, is_new=False)
            if delete:
                ok, msg = delete_item(conn, item["name"])
                if ok:
                    st.success("Item deleted.")
                    st.rerun()
                else:
                    st.error(msg)
        else:
            if st.form_submit_button("Create Item", type="primary", use_container_width=True):
                _save_item(conn, None, {
                    "name": name, "item_code": item_code, "item_group": item_group or None,
                    "for_purpose": for_purpose, "item_type": item_type, "unit": unit,
                    "rate": rate, "description": description,
                    "income_account": income_account or None,
                    "expense_account": expense_account or None,
                    "tax": tax or None, "track_item": track_item, "barcode": barcode,
                }, is_new=True)


def _save_item(conn, original_name, data, is_new):
    if not data["name"].strip():
        st.error("Item name is required.")
        return
    try:
        if is_new:
            create_item(conn, data)
            st.success(f"Item '{data['name']}' created.")
        else:
            update_item(conn, original_name, data)
            st.success("Item updated.")
        st.rerun()
    except Exception as e:
        st.error(str(e))


def _render_taxes(conn):
    st.subheader("Tax Rates")
    tab_list, tab_add = st.tabs(["Tax List", "Add Tax"])

    with tab_list:
        taxes = get_all_taxes(conn)
        if taxes:
            df = pd.DataFrame(taxes)
            df_d = df[["name", "rate", "account"]].copy()
            df_d.columns = ["Tax Name", "Rate (%)", "Account"]
            st.dataframe(df_d, use_container_width=True, hide_index=True)

            selected_tax = st.selectbox("Select tax to edit", [""] + [t["name"] for t in taxes])
            if selected_tax:
                tax = next((t for t in taxes if t["name"] == selected_tax), None)
                if tax:
                    account_names = [""] + get_account_names(conn)
                    with st.form("edit_tax_form"):
                        new_name = st.text_input("Tax Name", value=tax["name"])
                        new_rate = st.number_input("Rate (%)", value=float(tax["rate"]), min_value=0.0, max_value=100.0, step=0.5)
                        acc_val = tax.get("account") or ""
                        acc_idx = account_names.index(acc_val) if acc_val in account_names else 0
                        new_account = st.selectbox("Tax Account", account_names, index=acc_idx)

                        c1, c2 = st.columns(2)
                        with c1:
                            if st.form_submit_button("Save", use_container_width=True):
                                update_tax(conn, selected_tax, new_name, new_rate, new_account or "")
                                st.success("Tax updated.")
                                st.rerun()
                        with c2:
                            if st.form_submit_button("Delete", type="secondary", use_container_width=True):
                                ok, msg = delete_tax(conn, selected_tax)
                                if ok:
                                    st.success("Tax deleted.")
                                    st.rerun()
                                else:
                                    st.error(msg)
        else:
            st.info("No taxes configured.")

    with tab_add:
        st.subheader("Add Tax")
        account_names = [""] + get_account_names(conn)
        with st.form("create_tax_form"):
            name = st.text_input("Tax Name *", placeholder="e.g., GST 18%")
            rate = st.number_input("Rate (%)", min_value=0.0, max_value=100.0, value=18.0, step=0.5)
            account = st.selectbox("Tax Account", account_names)
            if st.form_submit_button("Create Tax", type="primary", use_container_width=True):
                if not name.strip():
                    st.error("Tax name is required.")
                else:
                    try:
                        create_tax(conn, name.strip(), rate, account or "")
                        st.success(f"Tax '{name}' created.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
