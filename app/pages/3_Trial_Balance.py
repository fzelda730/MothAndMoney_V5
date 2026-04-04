import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.providers import db_ready, discard_pending_trial_balance, trial_balance_import
from db.connection import use_sample_data

st.set_page_config(
    page_title="Trial Balance | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

COL_MAP_FIELDS = {
    "Bank Account": ["Account_No", "BankAccount", "Account", "Ref"],
    "Chart of Account": ["COA_Code", "AccountCode", "GL_Code", "Category"],
    "Chart of Account Description": [
        "COA_Description",
        "Account_Name",
        "AccountName",
        "Description",
        "GL_Name",
        "Category_Description",
    ],
    "Debits": ["Debit_Val", "Debit", "DR", "Amount_DR"],
    "Credits": ["Credit_Val", "Credit", "CR", "Amount_CR"],
}


def _empty_tb_totals() -> dict:
    return {
        "total_debits": 0.0,
        "total_credits": 0.0,
        "is_balanced": False,
        "variance": 0.0,
    }


load_css()
render_sidebar("onboarding")
render_topbar()

if not db_ready():
    st.stop()

if not use_sample_data():
    st.session_state.pop("tb_import_cleared", None)

if st.session_state.pop("tb_discard_done", False):
    st.success(st.session_state.pop("tb_discard_msg", "Import discarded."))

if st.session_state.get("tb_import_cleared") and use_sample_data():
    TRIAL_BALANCE_IMPORT_PREVIEW = []
    TRIAL_BALANCE_TOTALS = _empty_tb_totals()
else:
    TRIAL_BALANCE_IMPORT_PREVIEW, TRIAL_BALANCE_TOTALS = trial_balance_import()

# ── Breadcrumb ────────────────────────────────────────────────────────────────
st.html("""
<div style="font-size:0.75rem;color:#636262;margin-bottom:1.5rem;
            display:flex;align-items:center;gap:0.5rem;">
    <span style="font-weight:700;">STEP 1 OF 3</span>
    <span>•</span>
    <span>Trial Balance Initialization</span>
</div>
<h1 style="font-family:'Manrope',sans-serif;font-size:2.5rem;font-weight:800;
           margin:0 0 0.75rem;letter-spacing:-0.02em;">
    Import your financial <em style="color:#154212;">DNA.</em>
</h1>
<p style="color:#636262;max-width:36rem;line-height:1.6;margin-bottom:2.5rem;">
    Upload your current trial balance to sync the Atelier with your existing records.
    We'll handle the architectural mapping.
</p>
""")

if st.session_state.get("tb_discard_confirm"):
    st.warning(
        "Discard this import? Pending trial balance rows will be removed from the database "
        "(confirmed entries are kept). Your reference name, file selection, and column mapping "
        "will be reset."
    )
    c_yes, c_no = st.columns(2)
    with c_yes:
        if st.button("Yes, discard", key="tb_yes_discard", type="primary"):
            n = discard_pending_trial_balance()
            st.session_state["tb_discard_confirm"] = False
            st.session_state["tb_uploader_nonce"] = st.session_state.get("tb_uploader_nonce", 0) + 1
            st.session_state.pop("tb_ref_name", None)
            for field in COL_MAP_FIELDS:
                st.session_state.pop(f"tb_map_{field}", None)
            if use_sample_data():
                st.session_state["tb_import_cleared"] = True
            st.session_state.pop("tb_file_name", None)
            if use_sample_data():
                st.session_state["tb_discard_msg"] = "Demo import cleared. Form reset."
            elif n:
                st.session_state["tb_discard_msg"] = f"Discarded {n} pending row(s). Form reset."
            else:
                st.session_state["tb_discard_msg"] = (
                    "No pending rows in the database. Form reset."
                )
            st.session_state["tb_discard_done"] = True
            st.rerun()
    with c_no:
        if st.button("Cancel", key="tb_cancel_discard"):
            st.session_state["tb_discard_confirm"] = False
            st.rerun()
    st.html("<div style='height:1rem'></div>")

col_left, col_right = st.columns([1, 1.5], gap="large")

# ── Left: Upload & Column Mapping ─────────────────────────────────────────────
with col_left:
    st.html('<label class="mm-settings-label">Balance Reference Name</label>')
    ref_name = st.text_input(
        "ref_name",
        placeholder="e.g. FY24 Opening Balance",
        label_visibility="collapsed",
        key="tb_ref_name",
    )
    st.caption("This name will be used to identify this entry in your Ledger audit trail.")

    st.html("<div style='height:1rem'></div>")

    uploaded = st.file_uploader(
        "Drop .csv file here",
        type=["csv"],
        help="Ensure your file includes bank accounts, COA numbers, and clear debit/credit columns.",
        label_visibility="visible",
        key=f"tb_upload_{st.session_state.get('tb_uploader_nonce', 0)}",
    )

    if uploaded is not None:
        st.session_state["tb_import_cleared"] = False
        st.session_state["tb_file_name"] = uploaded.name
        st.success(f"File loaded: {uploaded.name}")

    st.html("<div style='height:1.5rem'></div>")

    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1rem;
               margin-bottom:1.25rem;">Column Mapping</h4>
    """)

    for field, options in COL_MAP_FIELDS.items():
        st.html(f'<label class="mm-settings-label">{field}</label>')
        st.selectbox(f"map_{field}", options, label_visibility="collapsed", key=f"tb_map_{field}")
        st.html("<div style='height:0.25rem'></div>")

# ── Right: Import Preview ─────────────────────────────────────────────────────
with col_right:
    total_deb = TRIAL_BALANCE_TOTALS["total_debits"]
    total_crd = TRIAL_BALANCE_TOTALS["total_credits"]
    is_balanced = TRIAL_BALANCE_TOTALS["is_balanced"]
    n_preview = len(TRIAL_BALANCE_IMPORT_PREVIEW)
    can_confirm = is_balanced and n_preview > 0

    balanced_badge = (
        '<span style="background:#bcf0ae;color:#154212;font-size:0.65rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.1em;padding:0.25rem 0.75rem;'
        'border-radius:0.75rem;">● Balanced</span>'
        if is_balanced else
        '<span style="background:#ffdad8;color:#71151d;font-size:0.65rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.1em;padding:0.25rem 0.75rem;'
        'border-radius:0.75rem;">● Unbalanced</span>'
    )

    _fn = st.session_state.get("tb_file_name") or "your CSV"
    if n_preview == 0:
        preview_caption = "No rows loaded yet. Upload a CSV or load data into the database."
    else:
        preview_caption = f"Displaying {n_preview} entries from {_fn}"

    st.html(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                margin-bottom:0.75rem;">
        <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1.1rem;margin:0;">
            Import Preview
        </h4>
        {balanced_badge}
    </div>
    <p style="font-size:0.7rem;color:#636262;margin-bottom:1rem;">
        {preview_caption}
    </p>
    """)

    rows_html = ""
    for row in TRIAL_BALANCE_IMPORT_PREVIEW:
        deb_str = f"${row['debits']:,.2f}" if row["debits"] else "—"
        crd_str = f"${row['credits']:,.2f}" if row["credits"] else "—"

        if row["error"]:
            row_style = "background:#fff0f0;"
            bank_style = "color:#ba1a1a;font-weight:700;"
            coa_style = "color:#ba1a1a;"
        else:
            row_style = "background:#ffffff;"
            bank_style = "font-size:0.8rem;"
            coa_style = "color:#636262;font-size:0.8rem;"

        rows_html += f"""
        <tr style="{row_style}">
            <td style="padding:0.75rem 0.75rem;{bank_style}font-size:0.75rem;">
                {row['bank_account']}
            </td>
            <td style="padding:0.75rem 0.75rem;{coa_style}">{row['coa']}</td>
            <td style="padding:0.75rem 0.75rem;text-align:right;font-size:0.8rem;">
                {deb_str}
            </td>
            <td style="padding:0.75rem 0.75rem;text-align:right;font-size:0.8rem;">
                {crd_str}
            </td>
        </tr>"""

    st.html(f"""
    <div style="background:#ffffff;border-radius:0.5rem;overflow:hidden;
                border:1px solid rgba(194,201,187,0.2);">
        <table style="width:100%;border-collapse:collapse;font-size:0.8rem;">
            <thead>
                <tr style="background:#f3f3f3;">
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                        Bank Account
                    </th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                        COA Number
                    </th>
                    <th style="padding:0.75rem;text-align:right;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                        Debits
                    </th>
                    <th style="padding:0.75rem;text-align:right;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                        Credits
                    </th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """)

    # Balance totals
    st.html("<div style='height:1rem'></div>")
    st.html(f"""
    <div style="background:#f3f3f3;border-radius:0.125rem;padding:1.25rem 1.5rem;
                display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:0.65rem;font-weight:700;text-transform:uppercase;
                     letter-spacing:0.1em;color:#636262;">Balance Totals</span>
        <div style="display:flex;gap:3rem;">
            <div style="text-align:right;">
                <div style="font-size:0.6rem;color:#636262;font-weight:700;
                            text-transform:uppercase;margin-bottom:0.25rem;">Total Debits</div>
                <div style="font-size:1.25rem;font-weight:700;font-family:'Manrope',sans-serif;">
                    ${total_deb:,.2f}
                </div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.6rem;color:#636262;font-weight:700;
                            text-transform:uppercase;margin-bottom:0.25rem;">Total Credits</div>
                <div style="font-size:1.25rem;font-weight:700;font-family:'Manrope',sans-serif;">
                    ${total_crd:,.2f}
                </div>
            </div>
        </div>
    </div>
    """)

    st.html("<div style='height:1rem'></div>")

    if is_balanced and n_preview > 0:
        st.html("""
        <div style="display:flex;align-items:center;gap:0.75rem;padding:1rem;
                    background:#f0fdf4;border-radius:0.25rem;margin-bottom:1rem;">
            <span class="material-symbols-outlined" style="color:#154212;">check_circle</span>
            <div>
                <div style="font-weight:700;font-size:0.875rem;color:#154212;">
                    Trial Balance is Balanced
                </div>
                <div style="font-size:0.7rem;color:#636262;">
                    Variance $0.00 — Ready for ledger entry!
                </div>
            </div>
        </div>
        """)

    col_discard, col_confirm = st.columns([1, 2], gap="small")
    with col_discard:
        if st.button("Discard", key="discard_tb"):
            st.session_state["tb_discard_confirm"] = True
            st.rerun()
    with col_confirm:
        if st.button(
            "Confirm & Save Entry →",
            key="confirm_tb",
            type="primary",
            disabled=not can_confirm,
        ):
            st.success("Trial balance confirmed and saved.")
            st.switch_page("pages/4_Bank_Statement_Template.py")

# ── Accounting standards ───────────────────────────────────────────────────────
st.html("""
<div style="margin-top:3rem;display:flex;gap:3rem;align-items:center;
            padding:2rem;background:#f9f9f9;border-radius:0.5rem;">
    <div style="flex:1;">
        <p style="font-size:0.7rem;font-style:italic;color:#636262;line-height:1.6;margin:0;">
            <span style="font-size:0.6rem;font-weight:800;text-transform:uppercase;
                         letter-spacing:0.1em;color:#636262;display:block;margin-bottom:0.5rem;">
                Accounting Standards
            </span>
            "A Trial Balance is the pulse of your atelier. By ensuring every debit meets its
            credit, we create a symmetry that reflects the true health of your creative enterprise."
        </p>
    </div>
    <div style="flex:1;text-align:right;">
        <p style="font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;
                  color:#636262;">
            Encrypted 256-bit Secure Transfer<br/>
            Compliant with Digital Atelier Financial Protocol V5
        </p>
    </div>
</div>
""")
