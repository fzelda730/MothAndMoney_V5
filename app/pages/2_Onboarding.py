import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar

st.set_page_config(
    page_title="Onboarding | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("onboarding")
render_topbar("Search commands...")



# ── Step indicator ────────────────────────────────────────────────────────────
st.html("""
<div style="margin-bottom:0.75rem;">
    <span style="font-size:0.65rem;font-weight:800;text-transform:uppercase;
                 letter-spacing:0.2em;color:#154212;background:#bcf0ae;
                 padding:0.25rem 0.75rem;border-radius:0.75rem;">
        Initial Configuration
    </span>
</div>
<h1 style="font-family:'Manrope',sans-serif;font-size:2.5rem;font-weight:800;
           margin:1rem 0 0.25rem;letter-spacing:-0.02em;">
    Prepare Your
</h1>
<h1 style="font-family:'Manrope',sans-serif;font-size:2.5rem;font-weight:800;
           color:#154212;margin:0 0 1rem;font-style:italic;letter-spacing:-0.02em;">
    Digital Atelier
</h1>
<p style="color:#636262;max-width:36rem;line-height:1.6;margin-bottom:2.5rem;">
    Onboarding is the process of translating your physical ledger into our digital
    architecture. By mapping your existing financial artifacts, we create a pristine
    environment for your fiscal growth.
</p>
""")

# Step progress
st.html("""
<div class="mm-step-indicator">
    <div class="mm-step">
        <div class="mm-step-num active">1</div>
        <span class="mm-step-label active">Data Import</span>
    </div>
    <div class="mm-step-connector"></div>
    <div class="mm-step">
        <div class="mm-step-num inactive">2</div>
        <span class="mm-step-label">Verification</span>
    </div>
    <div class="mm-step-connector"></div>
    <div class="mm-step">
        <div class="mm-step-num inactive">3</div>
        <span class="mm-step-label">Final Polish</span>
    </div>
</div>
""")

# ── Option cards: Bank stmt template → Credit card → Bank accounts → Trial balance ─
col1, col2 = st.columns(2, gap="large")

with col1:
    st.html("""
    <div class="mm-option-card">
        <div class="mm-option-icon">
            <span class="material-symbols-outlined">account_balance</span>
        </div>
        <div class="mm-option-title">Bank Statement Template</div>
        <div class="mm-option-desc">
            Define column mappings for automated transaction ingestion from bank exports.
        </div>
    </div>
    """)
    if st.button("CONFIGURE MAPPING →", key="go_bank_stmt", use_container_width=True):
        st.switch_page("pages/4_Bank_Statement_Template.py")

with col2:
    st.html("""
    <div class="mm-option-card">
        <div class="mm-option-icon">
            <span class="material-symbols-outlined" style="color:#71151d;">credit_card</span>
        </div>
        <div class="mm-option-title">Credit Card Mapping</div>
        <div class="mm-option-desc">
            Parse PDF or CSV statements specifically for expenditure tracking
            and reconciliation.
        </div>
    </div>
    """)
    if st.button("INGEST DATA →", key="go_cc", use_container_width=True):
        st.switch_page("pages/5_Credit_Card_Config.py")

st.html("<div style='height:1.5rem'></div>")

col3, col4 = st.columns(2, gap="large")

with col3:
    st.html("""
    <div class="mm-option-card">
        <div class="mm-option-icon">
            <span class="material-symbols-outlined">wallet</span>
        </div>
        <div class="mm-option-title">Bank &amp; Card Accounts</div>
        <div class="mm-option-desc">
            Register checking, savings, cash, and credit card accounts with last four digits
            and the import template used for ledger mapping. Required before using the Ledger
            with PostgreSQL.
        </div>
    </div>
    """)
    if st.button("REGISTER ACCOUNTS →", key="go_bank_accounts", use_container_width=True):
        st.switch_page("pages/9_Bank_Accounts.py")

with col4:
    st.html("""
    <div class="mm-option-card">
        <div class="mm-option-icon">
            <span class="material-symbols-outlined">upload_file</span>
        </div>
        <div class="mm-option-title">Upload Trial Balance</div>
        <div class="mm-option-desc">
            Import your historical balances via .csv to establish your opening ledger
            positions. Recommended for established studios.
        </div>
    </div>
    """)
    if st.button("SELECT CSV FILE →", key="go_trial_balance", use_container_width=True):
        st.switch_page("pages/3_Trial_Balance.py")

st.html("<div style='height:1.5rem'></div>")

col_payee_a, col_payee_b = st.columns(2, gap="large")

with col_payee_a:
    st.html("""
    <div class="mm-option-card" style="position:relative;">
        <span class="mm-badge-fuzzy" style="position:absolute;top:1rem;right:1rem;">
            Fuzzy Logic Enabled
        </span>
        <div class="mm-option-icon">
            <span class="material-symbols-outlined">auto_awesome</span>
        </div>
        <div class="mm-option-title">Payee Intelligence Mapping</div>
        <div class="mm-option-desc">
            Use our proprietary suggestions to auto-categorize vendors and recurring
            clients across all imports. Available inline during bank and credit card
            template setup.
        </div>
        <div class="mm-option-cta">
            <span>Analyze Patterns</span>
            <span class="material-symbols-outlined" style="font-size:0.875rem;">chevron_right</span>
        </div>
    </div>
    """)
    st.caption("Configure via Bank Statement or Credit Card template steps above.")

with col_payee_b:
    st.empty()

st.html("<div style='height:3rem'></div>")

# ── Guided tour CTA ───────────────────────────────────────────────────────────
st.html("""
<div style="background:#eeeeee;border-radius:0.5rem;padding:2rem;
            display:flex;justify-content:space-between;align-items:center;">
    <div>
        <p style="font-weight:700;font-size:0.9rem;margin:0 0 0.25rem 0;">
            Need a guided tour?
        </p>
        <p style="font-size:0.8rem;color:#636262;margin:0;">
            Our curatorial staff is available to help you map your first ledger.
            Schedule a 15-minute alignment session.
        </p>
    </div>
""")

col_skip, col_continue = st.columns([1, 1], gap="small")
with col_skip:
    if st.button("SKIP FOR NOW", key="skip_onboard"):
        st.switch_page("pages/1_Dashboard.py")
with col_continue:
    if st.button("CONTINUE SETUP →", key="continue_setup", type="primary"):
        st.switch_page("pages/4_Bank_Statement_Template.py")

st.html("</div>")

# ── Decorative footer ─────────────────────────────────────────────────────────
st.html("""
<div style="margin-top:4rem;width:100%;height:10rem;border-radius:0.5rem;overflow:hidden;
            background:linear-gradient(135deg,#154212,#2d5a27 60%,#a1d494);
            display:flex;align-items:center;justify-content:center;">
    <span style="font-family:'Manrope',sans-serif;font-size:1.25rem;font-weight:800;
                 color:rgba(255,255,255,0.2);letter-spacing:-0.02em;">
        The Digital Atelier
    </span>
</div>
<div style="display:flex;justify-content:space-between;padding:1.5rem 0;
            font-size:0.65rem;color:#636262;">
    <span>MOTH &amp; MONEY V4</span>
    <span>DOCUMENTING EXCELLENCE</span>
    <span>© 2024 ATELIER SYSTEMS</span>
</div>
""")

