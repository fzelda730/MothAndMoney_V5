import streamlit as st
from ui.styles import apply_custom_styles, render_header
from ui.dashboard import render_dashboard_page
from ui.trial_balance import render_trial_balance_page

# Placeholder for modules not yet built
def placeholder_page(name):
    st.title(name)
    st.info(f"The {name} room is under construction. Follow the forge.")

st.set_page_config(page_title="Moth and Money", layout="wide")

# Apply our Teal/Gold CSS
apply_custom_styles()

# 1. Initialize the Hub State
if 'current_module' not in st.session_state:
    st.session_state.current_module = "HUB"

# 2. The Launch Pad (Hub View)
if st.session_state.current_module == "HUB":
    render_header() # Logo in the main area for the Hub
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

# 3. The Moth and Money Module (Zoned Sidebar)
elif st.session_state.current_module == "M&M":
    render_header() # Logo moves to sidebar
    if st.sidebar.button("⬅ Back to Launch Pad"):
        st.session_state.current_module = "HUB"
        st.rerun()

    st.sidebar.divider()
    
    # --- Zoned Navigation ---
    st.sidebar.markdown("### THE VIEW")
    view_page = st.sidebar.radio("Snapshots & Financials", 
                                ["Dashboard", "Trial Balance", "P&L", "Balance Sheet", "Personal Spending"])
    
    st.sidebar.markdown("### THE INGEST")
    if st.sidebar.button("Statement Upload"): view_page = "Upload"
    if st.sidebar.button("Template Manager"): view_page = "Templates"
    
    st.sidebar.markdown("### THE LEDGER")
    if st.sidebar.button("General Ledger Report"): view_page = "GL Report"

    # Route to the selected page
    if view_page == "Dashboard":
        render_dashboard_page()
    elif view_page == "Trial Balance":
        render_trial_balance_page()
    else:
        placeholder_page(view_page)

# 4. Handle Trading and Booking Modules
else:
    render_header()
    if st.sidebar.button("⬅ Back to Launch Pad"):
        st.session_state.current_module = "HUB"
        st.rerun()
    placeholder_page(st.session_state.current_module)