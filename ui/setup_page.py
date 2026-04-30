"""
Company setup wizard UI — shown on first run.
"""
import streamlit as st
from services.setup import complete_setup, get_countries, get_currencies, save_settings


def render(conn):
    st.title("Welcome to Frappe Books (Python Edition)")
    st.markdown(
        "This is a Python/Streamlit port of Frappe Books — "
        "a free, open-source double-entry bookkeeping application."
    )
    st.divider()

    st.subheader("Company Setup")

    with st.form("setup_form"):
        company_name = st.text_input("Company Name", placeholder="My Business Ltd.")

        countries = get_countries(conn)
        country = st.selectbox("Country", countries, index=countries.index("United States") if "United States" in countries else 0)

        currencies = get_currencies()
        currency = st.selectbox("Currency", currencies, index=0)

        submitted = st.form_submit_button("Complete Setup", type="primary", use_container_width=True)

        if submitted:
            if not company_name.strip():
                st.error("Company name is required.")
            else:
                try:
                    complete_setup(conn, company_name.strip(), country, currency)
                    st.success(f"Setup complete! Welcome, {company_name}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Setup failed: {e}")
