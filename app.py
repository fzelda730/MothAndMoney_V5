import streamlit as st
from database.bootstrap import initialize_database_schema
from database.sqlite_lifecycle import count_chart_of_accounts_rows
from ui.styles import apply_custom_styles, render_header
from ui.dashboard import render_dashboard_page
from ui.trial_balance import render_trial_balance_page
from ui.onboarding_page import render_onboarding_page
from ui.admin_settings import render_admin_settings_page
from ui.template_manager import render_template_manager_page
from ui.statement_upload import render_statement_upload_page
from ui.general_ledger import render_general_ledger_page

# Placeholder for modules not yet built
def placeholder_page(name):
    st.title(name)
    st.info(f"The {name} room is under construction. Follow the forge.")

st.set_page_config(page_title="Moth and Money", layout="wide")

initialize_database_schema()
chart_of_accounts_row_count = count_chart_of_accounts_rows()

# Apply our Teal/Gold CSS
apply_custom_styles()

# 1. Initialize the Hub State
if "current_module" not in st.session_state:
    st.session_state.current_module = "HUB"

# 2. The Launch Pad (Hub View)
if st.session_state.current_module == "HUB":
    render_header()  # Logo in the main area for the Hub
    st.title("The Launch Pad")
    st.subheader("Select your environment:")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🦋 Moth and Money", width="stretch"):
            st.session_state.current_module = "M&M"
            st.rerun()
    with col2:
        if st.button("📉 Low Stress Trading", width="stretch"):
            st.session_state.current_module = "TRADING"
            st.rerun()
    with col3:
        if st.button("🎨 Cosmic Smash Booking", width="stretch"):
            st.session_state.current_module = "BOOKING"
            st.rerun()

# 3. The Moth and Money Module (Zoned Sidebar) — init gate only here
elif st.session_state.current_module == "M&M":
    render_header()  # Logo moves to sidebar
    if st.sidebar.button("⬅ Back to Launch Pad"):
        st.session_state.current_module = "HUB"
        st.rerun()

    if chart_of_accounts_row_count == 0:
        render_onboarding_page()
    else:
        st.sidebar.divider()

        # Persist current page across reruns (e.g. file uploader drag-and-drop on
        # Template Manager). Buttons (not one radio) allow section headings between groups.
        if "mm_nav_radio" not in st.session_state:
            st.session_state.mm_nav_radio = "Dashboard"

        _legacy_mm_nav_label = {
            "Settings": "Onboarding",
            "GL Report": "General Ledger",
            "P&L": "P& L",
        }
        if st.session_state.mm_nav_radio in _legacy_mm_nav_label:
            st.session_state.mm_nav_radio = _legacy_mm_nav_label[
                st.session_state.mm_nav_radio
            ]

        def _moth_and_money_sidebar_nav_button(
            display_label: str, widget_key: str
        ) -> None:
            """Move the owner to one Moth and Money room; keeps mm_nav_radio on reruns.

            Accounting rule: N/A (UI navigation only).
            """
            is_current_page = st.session_state.mm_nav_radio == display_label
            if st.sidebar.button(
                display_label,
                key=widget_key,
                use_container_width=True,
                type="primary" if is_current_page else "secondary",
            ):
                st.session_state.mm_nav_radio = display_label
                st.rerun()

        st.sidebar.markdown("### Dashboard")
        _moth_and_money_sidebar_nav_button("Dashboard", "mm_nav_dashboard")

        st.sidebar.markdown("### Onboarding")
        _moth_and_money_sidebar_nav_button("Onboarding", "mm_nav_onboarding")

        st.sidebar.markdown("### Ingest")
        _moth_and_money_sidebar_nav_button(
            "Template Manager", "mm_nav_template_manager"
        )
        _moth_and_money_sidebar_nav_button(
            "Statement Upload", "mm_nav_statement_upload"
        )

        st.sidebar.markdown("### Reports")
        _moth_and_money_sidebar_nav_button("Trial Balance", "mm_nav_trial_balance")
        _moth_and_money_sidebar_nav_button("P& L", "mm_nav_profit_and_loss")
        _moth_and_money_sidebar_nav_button("Balance Sheet", "mm_nav_balance_sheet")
        _moth_and_money_sidebar_nav_button(
            "General Ledger", "mm_nav_general_ledger"
        )
        _moth_and_money_sidebar_nav_button(
            "Personal Spending", "mm_nav_personal_spending"
        )

        view_page = st.session_state.mm_nav_radio

        # Route to the selected page
        if view_page == "Dashboard":
            render_dashboard_page()
        elif view_page == "Trial Balance":
            render_trial_balance_page()
        elif view_page == "Onboarding":
            render_admin_settings_page()
        elif view_page == "Template Manager":
            render_template_manager_page()
        elif view_page == "Statement Upload":
            render_statement_upload_page()
        elif view_page == "General Ledger":
            render_general_ledger_page()
        else:
            placeholder_page(view_page)

# 4. Handle Trading and Booking Modules
else:
    render_header()
    if st.sidebar.button("⬅ Back to Launch Pad"):
        st.session_state.current_module = "HUB"
        st.rerun()
    placeholder_page(st.session_state.current_module)
