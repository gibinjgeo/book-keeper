"""
Parties (Customers & Suppliers) UI.
"""
import streamlit as st
import pandas as pd
from services.parties import (
    get_all_parties, get_party, create_party, update_party,
    delete_party, get_outstanding_balance
)
from services.accounts import get_account_names

ROLES = ["Customer", "Supplier", "Both"]
CURRENCIES = ["USD", "EUR", "GBP", "INR", "CAD", "AUD", "JPY", "SGD", "AED"]


def render(conn):
    st.title("Parties")
    st.caption("Manage Customers and Suppliers")

    tab_list, tab_create = st.tabs(["Party List", "Add Party"])

    with tab_list:
        _render_parties_list(conn)

    with tab_create:
        _render_create_form(conn)


def _render_parties_list(conn):
    role_filter = st.radio("Show", ["All", "Customer", "Supplier"], horizontal=True)
    parties = get_all_parties(conn, None if role_filter == "All" else role_filter)

    if not parties:
        st.info("No parties found. Add a Customer or Supplier to get started.")
        return

    df = pd.DataFrame(parties)
    display_cols = ["name", "role", "email", "phone", "currency", "loyalty_points"]
    df_display = df[[c for c in display_cols if c in df.columns]].copy()
    df_display.columns = ["Name", "Role", "Email", "Phone", "Currency", "Loyalty Pts"]
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.subheader("Edit Party")
    party_names = [p["name"] for p in parties]
    selected = st.selectbox("Select party", [""] + party_names, key="party_select")

    if selected:
        party = get_party(conn, selected)
        if party:
            balance = get_outstanding_balance(conn, selected)
            col1, col2 = st.columns(2)
            col1.metric("Outstanding Receivable", f"{balance['receivable']:,.2f}")
            col2.metric("Outstanding Payable", f"{balance['payable']:,.2f}")

            account_names = [""] + get_account_names(conn)
            with st.form("edit_party_form"):
                new_name = st.text_input("Name *", value=party["name"])
                role = st.selectbox("Role", ROLES, index=ROLES.index(party["role"]) if party["role"] in ROLES else 0)
                col_a, col_b = st.columns(2)
                with col_a:
                    email = st.text_input("Email", value=party.get("email", ""))
                    phone = st.text_input("Phone", value=party.get("phone", ""))
                    tax_id = st.text_input("Tax ID", value=party.get("tax_id", ""))
                with col_b:
                    address = st.text_input("Address", value=party.get("address", ""))
                    city = st.text_input("City", value=party.get("city", ""))
                    country = st.text_input("Country", value=party.get("country", ""))

                curr_idx = CURRENCIES.index(party.get("currency", "USD")) if party.get("currency") in CURRENCIES else 0
                currency = st.selectbox("Currency", CURRENCIES, index=curr_idx)
                acc_val = party.get("default_account") or ""
                acc_idx = account_names.index(acc_val) if acc_val in account_names else 0
                default_account = st.selectbox("Default Account", account_names, index=acc_idx)

                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Save", use_container_width=True):
                        try:
                            update_party(conn, selected, {
                                "name": new_name, "role": role, "email": email,
                                "phone": phone, "tax_id": tax_id, "address": address,
                                "city": city, "country": country, "currency": currency,
                                "default_account": default_account or None,
                            })
                            st.success("Party updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                with col2:
                    if st.form_submit_button("Delete", type="secondary", use_container_width=True):
                        ok, msg = delete_party(conn, selected)
                        if ok:
                            st.success("Party deleted.")
                            st.rerun()
                        else:
                            st.error(msg)


def _render_create_form(conn):
    st.subheader("Add New Party")
    account_names = [""] + get_account_names(conn)

    with st.form("create_party_form"):
        name = st.text_input("Name *", placeholder="Customer or Supplier Name")
        role = st.selectbox("Role", ROLES)
        col_a, col_b = st.columns(2)
        with col_a:
            email = st.text_input("Email", placeholder="email@example.com")
            phone = st.text_input("Phone")
            tax_id = st.text_input("Tax ID / GSTIN")
        with col_b:
            address = st.text_input("Address")
            city = st.text_input("City")
            country = st.text_input("Country", value="United States")

        currency = st.selectbox("Currency", CURRENCIES)
        default_account = st.selectbox("Default Account", account_names)

        if st.form_submit_button("Create Party", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Party name is required.")
            else:
                try:
                    create_party(conn, {
                        "name": name.strip(), "role": role, "email": email,
                        "phone": phone, "tax_id": tax_id, "address": address,
                        "city": city, "country": country, "currency": currency,
                        "default_account": default_account or None,
                    })
                    st.success(f"Party '{name}' created.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
