import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.sample_data import BANK_PREVIEW_ROWS

st.set_page_config(
    page_title="Bank Statement Template | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("onboarding")
render_topbar()



# ── Header ────────────────────────────────────────────────────────────────────
st.html("""
<div style="font-size:0.65rem;color:#636262;font-weight:700;text-transform:uppercase;
            letter-spacing:0.1em;margin-bottom:0.5rem;">
    Configuration › Template Studio
</div>
<h1 class="mm-page-title" style="font-size:2rem;margin-bottom:0.25rem;">
    Moth and Money <strong style="color:#154212;">V5</strong>
</h1>
<p class="mm-page-description" style="margin-bottom:2.5rem;">
    Design a persistent blueprint for your bank statements. Map column data once and maintain
    consistent financial clarity for your digital atelier.
</p>
""")

col_left, col_right = st.columns([1, 1.2], gap="large")

# ── Left: Template Identity + Upload + Column Mapping ─────────────────────────
with col_left:
    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:0.95rem;
               margin-bottom:0.25rem;">Template Identity</h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1rem;">
        Provide a descriptive name for your template to reuse it across monthly
        reconciled statements.
    </p>
    """)

    st.html('<label class="mm-settings-label">Template Name</label>')
    template_name = st.text_input("bank_tmpl_name", placeholder="e.g. Chase Business Checking",
                                   label_visibility="collapsed")

    st.html("<div style='height:1.5rem'></div>")

    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:0.95rem;
               margin-bottom:0.25rem;">Upload Preview</h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1rem;">
        Upload a sample .csv file to identify available columns for the mapping process.
    </p>
    """)

    uploaded = st.file_uploader(
        "Select a sample statement",
        type=["csv"],
        help="Accepts CSV files. Top up to 10MB.",
        label_visibility="collapsed",
    )
    if uploaded:
        st.success(f"Loaded: {uploaded.name}")

    st.html("<div style='height:1.5rem'></div>")

    # ── Column Mapping ────────────────────────────────────────────────────────
    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:0.95rem;
               margin-bottom:0.5rem;">Column Mapping</h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1.25rem;">
        Select the corresponding columns from your file to match the Atelier's system requirements.
    </p>
    """)

    mapping_fields = [
        ("📅", "Date",               ["Transaction Date", "Date", "Post Date", "Value Date"]),
        ("🔄", "Transaction Type",   ["Type", "Transaction Type", "Dr/Cr", "Debit/Credit"]),
        ("👤", "Payee",              ["Description", "Payee", "Merchant", "Narrative"]),
        ("💰", "Amount",             ["Amount (USD)", "Amount", "Value", "Net Amount"]),
        ("📋", "Chart of Account",   ["Select Column", "Account Code", "GL Code", "Category"]),
        ("📝", "Description",        ["Select Column", "Note", "Memo", "Reference"]),
    ]

    for emoji, field, options in mapping_fields:
        col_icon, col_label, col_select = st.columns([0.3, 1.2, 2], gap="small")
        with col_icon:
            st.html(f"<div style='padding-top:0.6rem;font-size:1.1rem;'>{emoji}</div>")
        with col_label:
            st.html(f"<div style='padding-top:0.7rem;font-size:0.8rem;font-weight:600;"
                        f"color:#1a1c1c;'>{field}</div>")
        with col_select:
            st.selectbox(f"bank_map_{field}", options, label_visibility="collapsed")

    # ── Payee Intelligence (inline) ───────────────────────────────────────────
    st.html("<div style='height:1rem'></div>")
    with st.expander("✨ Payee Intelligence — Auto-categorize vendors", expanded=False):
        st.caption(
            "After uploading a sample file, the system will suggest COA assignments "
            "for recognized payees. Confirm or override each suggestion."
        )
        payee_rules = [
            ("Paper Supply Co",    "5200 - Material Supplies",  1.00),
            ("Studio Rent",        "5100 - Studio Rent",        1.00),
            ("Delta Airlines",     "5700 - Travel & Dining",    0.82),
            ("Amazon",             "5500 - Software & Subs",    0.74),
        ]
        for payee, coa, conf in payee_rules:
            pc, cc = st.columns([2, 2], gap="small")
            with pc:
                st.html(f"<div style='padding:0.5rem 0;font-size:0.8rem;font-weight:600;'>"
                            f"{payee}</div>")
            with cc:
                st.selectbox(f"pi_{payee}", [coa, "5100", "5200", "5300", "4100"],
                             label_visibility="collapsed")

# ── Right: Live Preview ───────────────────────────────────────────────────────
with col_right:
    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:0.95rem;
               margin-bottom:0.5rem;">Live Preview</h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1.25rem;">
        Verification of the first 3 rows of your statement using the current mapping.
    </p>
    """)

    preview_rows_html = ""
    for row in BANK_PREVIEW_ROWS:
        type_color = "#154212" if row["type"] == "CREDIT" else "#71151d"
        type_bg    = "#bcf0ae" if row["type"] == "CREDIT" else "#ffdad8"
        amt_color  = "#154212" if row["amount"] > 0 else "#71151d"

        preview_rows_html += f"""
        <tr style="background:#ffffff;">
            <td style="padding:0.75rem;font-size:0.75rem;color:#636262;">{row['date']}</td>
            <td style="padding:0.75rem;">
                <span style="background:{type_bg};color:{type_color};font-size:0.6rem;
                             font-weight:700;padding:0.125rem 0.5rem;border-radius:0.75rem;">
                    {row['type']}
                </span>
            </td>
            <td style="padding:0.75rem;font-size:0.8rem;font-weight:600;">{row['payee']}</td>
            <td style="padding:0.75rem;text-align:right;font-size:0.8rem;color:{amt_color};
                       font-weight:600;">${abs(row['amount']):,.2f}</td>
            <td style="padding:0.75rem;font-size:0.75rem;color:#636262;">{row['coa']}</td>
        </tr>"""

    st.html(f"""
    <div style="background:#ffffff;border-radius:0.5rem;overflow:hidden;
                border:1px solid rgba(194,201,187,0.2);">
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#f3f3f3;">
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Date</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Type</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Payee</th>
                    <th style="padding:0.75rem;text-align:right;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Amount</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">COA</th>
                </tr>
            </thead>
            <tbody>{preview_rows_html}</tbody>
        </table>
    </div>
    """)

st.html("<div style='height:2rem'></div>")

# ── Actions ───────────────────────────────────────────────────────────────────
col_cancel, col_spacer, col_save = st.columns([1, 3, 1], gap="small")
with col_cancel:
    if st.button("Cancel", key="bank_cancel"):
        st.switch_page("pages/2_Onboarding.py")
with col_save:
    if st.button("💾 Save Template", key="bank_save", type="primary"):
        st.success("Bank statement template saved successfully.")
        st.switch_page("pages/5_Credit_Card_Config.py")

