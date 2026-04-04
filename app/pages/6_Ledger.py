import streamlit as st
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.providers import (
    bank_accounts,
    db_ready,
    import_templates,
    ledger_summary,
    ledger_transactions,
)

st.set_page_config(
    page_title="Ledger | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("ledger")
render_topbar("Search entries...")

if not db_ready():
    st.stop()

BANK_ACCOUNTS = bank_accounts()
IMPORT_TEMPLATES = import_templates()

account_options = [
    f"{a['account_name']} ****{a['masked']}"
    for a in BANK_ACCOUNTS if a["account_type"] != "cash"
]

if not account_options:
    st.warning("No bank or card accounts found. Complete onboarding or set USE_SAMPLE_DATA=true.")
    st.stop()


def _acct_id_for_label(label: str):
    for a in BANK_ACCOUNTS:
        if f"{a['account_name']} ****{a['masked']}" == label:
            return a["id"]
    return None


st.html("""
<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;">
    <span class="material-symbols-outlined" style="font-size:0.9rem;color:#636262;">
        account_balance
    </span>
    <span style="font-size:0.65rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.1em;color:#636262;">Working On:</span>
</div>
""")
selected_account = st.selectbox(
    "working_account",
    account_options,
    label_visibility="collapsed",
)
aid = _acct_id_for_label(selected_account)
s = ledger_summary(aid)
ledger_txns = ledger_transactions(aid)

# ── Balance summary bar ───────────────────────────────────────────────────────
st.html(f"""
<div class="mm-balance-bar">
    <div class="mm-balance-item">
        <div class="mm-balance-label">Beginning Balance</div>
        <div class="mm-balance-value">${s['beginning_balance']:,.2f}</div>
    </div>
    <div class="mm-balance-item">
        <div class="mm-balance-label">Total Debits</div>
        <div class="mm-balance-value">${s['total_debits']:,.2f}</div>
    </div>
    <div class="mm-balance-item">
        <div class="mm-balance-label">Total Credits</div>
        <div class="mm-balance-value">${s['total_credits']:,.2f}</div>
    </div>
    <div class="mm-balance-item">
        <div class="mm-balance-label">Ending Balance</div>
        <div class="mm-balance-value ending">${s['ending_balance']:,.2f}
            <span class="material-symbols-outlined"
                  style="font-size:1rem;vertical-align:middle;color:#154212;">
                check_circle
            </span>
        </div>
    </div>
</div>
""")

st.html("<div style='height:1.5rem'></div>")

# ── Upload zone + Parsing template ───────────────────────────────────────────
col_upload, col_template = st.columns([1.5, 1], gap="large")

with col_upload:
    uploaded = st.file_uploader(
        "Upload Bank or Credit Card Statement",
        type=["csv", "ofx"],
        help="Drag and drop your CSV or OFX files here to automatically populate the ledger.",
        label_visibility="visible",
    )

    st.html("<div style='height:0.75rem'></div>")

    # Date range
    col_start, col_end = st.columns(2, gap="medium")
    with col_start:
        start_date = st.date_input("Start Date",
                                    value=date.today().replace(day=1),
                                    label_visibility="visible")
    with col_end:
        end_date = st.date_input("End Date",
                                  value=date.today(),
                                  label_visibility="visible")

    if uploaded:
        if st.button("Process File", type="primary"):
            st.success(f"Processing {uploaded.name} for {selected_account}...")

with col_template:
    template_names = [t["name"] for t in IMPORT_TEMPLATES]
    st.html("""
    <div class="mm-card-low" style="height:100%;">
        <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem;">
            <span class="material-symbols-outlined" style="font-size:1.25rem;color:#154212;">
                copy_all
            </span>
            <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1rem;margin:0;">
                Parsing Template
            </h4>
        </div>
        <p style="font-size:0.75rem;color:#636262;margin-bottom:1rem;">
            Select a pre-configured template to ensure your bank's columns align with the
            ledger structure.
        </p>
    """)

    selected_template = st.selectbox(
        "parsing_template",
        template_names + ["Standard CSV Template"],
        label_visibility="collapsed",
    )

    st.html("""
    </div>
    """)

    if st.button("+ Create New Template", key="new_template"):
        st.switch_page("pages/4_Bank_Statement_Template.py")

st.html("<div style='height:2rem'></div>")

# ── Current Transactions table ────────────────────────────────────────────────
col_title, col_actions = st.columns([3, 1], gap="small")
with col_title:
    st.html("""
    <h3 style="font-family:'Manrope',sans-serif;font-size:1.4rem;font-weight:700;
               margin:0;">Current Transactions</h3>
    """)
with col_actions:
    col_filter, col_export = st.columns(2, gap="small")
    with col_filter:
        st.button("⚙ Filter", key="ledger_filter")
    with col_export:
        st.button("↑ Export", key="ledger_export")

st.html("<div style='height:0.75rem'></div>")

# Transaction rows
rows_html = ""
for txn in ledger_txns:
    deb_str = f"${txn['debit']:,.2f}"  if txn["debit"]   else "—"
    crd_str = f"${txn['credit']:,.2f}" if txn["credit"]  else "—"
    deb_color = "#1a1c1c" if txn["debit"] else "#c2c9bb"
    crd_color = "#1a1c1c" if txn["credit"] else "#c2c9bb"

    if txn["coa"]:
        coa_cell = f'<span class="mm-coa-badge">{txn["coa"]}</span>'
    else:
        coa_cell = '<span class="mm-assign-badge">Assign...</span>'

    flag_icon = (
        '<span class="material-symbols-outlined" style="color:#ba1a1a;font-size:1rem;">'
        'warning</span>'
        if txn["flagged"] else ""
    )

    rows_html += f"""
    <tr style="background:#ffffff;">
        <td style="padding:1rem;font-size:0.8rem;color:#636262;">{txn['date']}</td>
        <td style="padding:1rem;">
            <div class="mm-payee-name">{txn['payee']}</div>
            <div class="mm-payee-sub">{txn['sub']}</div>
        </td>
        <td style="padding:1rem;">{coa_cell}</td>
        <td style="padding:1rem;text-align:right;font-size:0.875rem;
                   color:{deb_color};font-weight:500;">{deb_str}</td>
        <td style="padding:1rem;text-align:right;font-size:0.875rem;
                   color:{crd_color};font-weight:500;">{crd_str}
                   {flag_icon}</td>
    </tr>
    <tr><td colspan="5" style="height:0.25rem;background:transparent;"></td></tr>"""

st.html(f"""
<div style="overflow-x:auto;margin-right:2rem;">
    <table class="mm-transaction-table" style="width:100%;border-collapse:separate;
                                               border-spacing:0 0.25rem;">
        <thead>
            <tr>
                <th>Date</th>
                <th>Payee</th>
                <th>COA Number</th>
                <th style="text-align:right;">Debits</th>
                <th style="text-align:right;">Credits</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
</div>
""")

# ── Subtotal row ──────────────────────────────────────────────────────────────
st.html(f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            padding:1rem 1rem;margin-right:2rem;border-top:1px solid rgba(194,201,187,0.2);">
    <span style="font-size:0.8rem;color:#154212;font-weight:600;cursor:pointer;">
        + Manual Entry
    </span>
    <div style="display:flex;align-items:center;gap:2rem;">
        <span style="font-size:0.8rem;color:#636262;">
            Subtotal Debits: <strong style="color:#1a1c1c;">${s['total_debits']:,.2f}</strong>
        </span>
        <span style="font-size:0.8rem;color:#636262;">
            Subtotal Credits: <strong style="color:#1a1c1c;">${s['total_credits']:,.2f}</strong>
        </span>
        <span style="display:flex;align-items:center;gap:0.25rem;font-size:0.8rem;
                     color:#154212;font-weight:600;">
            <span class="material-symbols-outlined" style="font-size:1rem;">check_circle</span>
            Balanced
        </span>
    </div>
</div>
""")

st.html("<div style='height:3rem'></div>")

# ── Finalize & Submit ─────────────────────────────────────────────────────────
col_info, col_actions2 = st.columns([2, 1], gap="large")
with col_info:
    st.html("""
    <p style="font-size:0.8rem;color:#636262;line-height:1.6;">
        By submitting this ledger, you are finalizing the transactions for the current period.
        This action is recorded in the immutable studio audit log.
    </p>
    """)

with col_actions2:
    col_draft, col_submit = st.columns([1, 2], gap="small")
    with col_draft:
        st.button("Save Draft", key="save_draft")
    with col_submit:
        if st.button("Finalize & Submit Ledger", key="finalize", type="primary"):
            st.success("Ledger finalized and submitted. Dashboard updated.")

# ── Decorative footer ─────────────────────────────────────────────────────────
st.html("""
<div style="margin-top:4rem;width:100%;height:8rem;border-radius:0.5rem;overflow:hidden;
            background:linear-gradient(135deg,#154212,#2d5a27 60%,#a1d494);">
</div>
<div style="display:flex;justify-content:space-between;padding:1rem 0;
            font-size:0.6rem;color:#636262;font-weight:700;text-transform:uppercase;
            letter-spacing:0.1em;">
    <span>MOTH AND MONEY © 2024</span>
    <span>STUDIO LEDGER SYSTEM V4.2.0</span>
</div>
""")

