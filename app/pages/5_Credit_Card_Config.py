import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.providers import db_ready, save_credit_card_template_to_db
from data.sample_data import CC_PREVIEW_ROWS
from db.connection import use_sample_data

st.set_page_config(
    page_title="Credit Card Config | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("onboarding")
render_topbar()



# ── Back link + Header ────────────────────────────────────────────────────────
if st.button("← Back to Onboarding", key="cc_back"):
    st.switch_page("pages/2_Onboarding.py")

st.html("""
<h1 class="mm-page-title" style="margin-top:1rem;margin-bottom:0.25rem;">
    Moth and Money Ledger For Creatives
</h1>
<div style="font-size:0.65rem;color:#636262;font-weight:700;text-transform:uppercase;
            letter-spacing:0.1em;margin-bottom:0.25rem;">Configuration Stage</div>
<h2 style="font-family:'Manrope',sans-serif;font-size:1.6rem;font-weight:800;
           margin:0 0 2rem;letter-spacing:-0.02em;">
    Credit Card Statement Template Configuration
</h2>
""")

col_left, col_right = st.columns([1, 1.2], gap="large")

# ── Left: Template Identity + Upload + Column Mapping ─────────────────────────
with col_left:
    st.html("""
    <h4 class="mm-settings-label" style="font-size:0.65rem;margin-bottom:0.5rem;">
        Template Identity
    </h4>
    """)

    st.html('<label class="mm-settings-label">Template Name</label>')
    st.text_input(
        "cc_tmpl_name",
        value="Amex Business Gold",
        label_visibility="collapsed",
        key="cc_tmpl_name",
    )

    st.html("<div style='height:1.5rem'></div>")

    st.html("""
    <h4 class="mm-settings-label" style="font-size:0.65rem;margin-bottom:0.5rem;">
        Upload Sample Statement
    </h4>
    """)

    uploaded = st.file_uploader(
        "Drag and drop a CSV or PDF statement",
        type=["csv", "pdf"],
        help="Maximum file size 10MB",
        label_visibility="collapsed",
    )
    if uploaded:
        st.success(f"Loaded: {uploaded.name}")

    st.html("<div style='height:1.5rem'></div>")

    # Column mapping with "5 Fields Detected" badge
    col_cm_title, col_cm_badge = st.columns([2, 1], gap="small")
    with col_cm_title:
        st.html("""
        <h4 class="mm-settings-label" style="font-size:0.65rem;margin-bottom:0.5rem;">
            Column Mapping
        </h4>
        """)
    with col_cm_badge:
        st.html("""
        <span style="background:#bcf0ae;color:#154212;font-size:0.6rem;font-weight:700;
                     padding:0.2rem 0.6rem;border-radius:0.75rem;">5 Fields Detected</span>
        """)

    st.button("Cancel", key="cc_cancel_map")

    CC_TEMPLATE_FIELDS = [
        ("transaction_type", "Transaction Type", ["Type", "Transaction Type", "Dr/Cr"]),
        ("payee", "Payee", ["Description", "Payee", "Merchant", "Vendor"]),
        ("amount", "Amount", ["Amount", "Transaction Amount", "Net"]),
        ("account", "Chart of Account", ["Account Code", "GL Code", "Category", "Account"]),
        ("description", "Description", ["Note", "Memo", "Reference", "Narrative"]),
    ]

    for map_key, field, options in CC_TEMPLATE_FIELDS:
        col_label, col_select = st.columns([1, 2], gap="small")
        with col_label:
            st.html(f"<div style='padding-top:0.7rem;font-size:0.8rem;font-weight:600;"
                        f"color:#1a1c1c;'>{field}</div>")
        with col_select:
            st.selectbox(
                f"cc_map_{field}",
                options,
                label_visibility="collapsed",
                key=f"tpl_cc_{map_key}",
            )

    # ── Payee Intelligence (inline) ───────────────────────────────────────────
    st.html("<div style='height:1rem'></div>")
    with st.expander("✨ Payee Intelligence — Auto-categorize CC vendors", expanded=False):
        st.caption(
            "These rules are scoped to this credit card template only. "
            "The same payee may map to a different COA on your bank statement template."
        )
        cc_payee_rules = [
            ("Adobe Systems Inc.",  "5500 - Software & Subs",    1.00),
            ("Amazon Web Services", "5500 - Software & Subs",    0.95),
            ("Starbucks",           "5700 - Travel & Dining",    1.00),
            ("Delta Airlines",      "5700 - Travel & Dining",    1.00),
        ]
        for payee, coa, conf in cc_payee_rules:
            pc, cc_col = st.columns([2, 2], gap="small")
            with pc:
                st.html(f"<div style='padding:0.5rem 0;font-size:0.8rem;font-weight:600;'>"
                            f"{payee}</div>")
            with cc_col:
                st.selectbox(f"cc_pi_{payee}", [coa, "5100", "5200", "5300", "4100"],
                             label_visibility="collapsed")

# ── Right: Live Preview ───────────────────────────────────────────────────────
with col_right:
    col_preview_title, col_rendering = st.columns([2, 1], gap="small")
    with col_preview_title:
        st.html("""
        <h4 class="mm-settings-label" style="font-size:0.65rem;margin-bottom:0.5rem;">
            Live Preview
        </h4>
        """)
    with col_rendering:
        st.html("""
        <span style="font-size:0.6rem;font-weight:700;color:#154212;">● Rendering Active</span>
        """)

    rows_html = ""
    for row in CC_PREVIEW_ROWS:
        amt_color = "#71151d" if row["amount"] < 0 else "#154212"
        rows_html += f"""
        <tr style="background:#ffffff;">
            <td style="padding:0.75rem;font-size:0.75rem;color:#636262;">{row['date']}</td>
            <td style="padding:0.75rem;">
                <div style="font-size:0.8rem;font-weight:600;">{row['payee']}</div>
                <div style="font-size:0.65rem;color:#636262;">{row['sub']}</div>
            </td>
            <td style="padding:0.75rem;">
                <span style="background:#eeeeee;color:#636262;font-size:0.65rem;font-weight:600;
                             padding:0.1rem 0.5rem;border-radius:0.125rem;">
                    {row['account']}
                </span>
            </td>
            <td style="padding:0.75rem;text-align:right;font-size:0.8rem;color:{amt_color};
                       font-weight:600;">${abs(row['amount']):,.2f}</td>
        </tr>"""

    st.html(f"""
    <div style="background:#ffffff;border-radius:0.5rem;overflow:hidden;
                border:1px solid rgba(194,201,187,0.2);margin-bottom:1.5rem;">
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#f3f3f3;">
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Date</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Payee</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Account</th>
                    <th style="padding:0.75rem;text-align:right;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Amount</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """)

    # Processing accuracy
    accuracy = 98.2
    st.html(f"""
    <div style="margin-bottom:1.5rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;
                    margin-bottom:0.5rem;">
            <span style="font-size:0.65rem;font-weight:700;text-transform:uppercase;
                         letter-spacing:0.1em;color:#636262;">Estimated Processing Accuracy</span>
            <span style="font-size:1rem;font-weight:700;color:#154212;">{accuracy}%</span>
        </div>
        <div class="mm-accuracy-bar">
            <div class="mm-accuracy-fill" style="width:{accuracy}%;"></div>
        </div>
    </div>
    """)

    if st.button("💾 Save Template", key="cc_save", type="primary", use_container_width=True):
        name = (st.session_state.get("cc_tmpl_name") or "").strip() or "Credit card template"
        if use_sample_data():
            st.warning(
                "Demo mode (USE_SAMPLE_DATA=true): the template is not stored in PostgreSQL. "
                "Set USE_SAMPLE_DATA=false in app/.env to save to the database."
            )
            st.success("Credit card template saved (demo). Onboarding complete!")
        else:
            column_map = {
                k: st.session_state.get(f"tpl_cc_{k}")
                for k in ("transaction_type", "payee", "amount", "account", "description")
            }
            save_credit_card_template_to_db(name, column_map)
            st.success("Credit card template saved to the database. Onboarding complete!")
        st.switch_page("pages/1_Dashboard.py")

