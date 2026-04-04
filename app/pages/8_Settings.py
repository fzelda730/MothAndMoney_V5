import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_settings_topbar
from data.sample_data import STUDIO, BANK_ACCOUNTS

st.set_page_config(
    page_title="Settings | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("settings")
render_settings_topbar("Global Settings & Configuration")



col_profile, col_financial = st.columns([2, 1], gap="large")

# ── Studio & Artist Profile ───────────────────────────────────────────────────
with col_profile:
    st.html("""
    <div class="mm-card" style="margin-bottom:2rem;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;
                    margin-bottom:2rem;">
            <div>
                <h3 style="font-family:'Manrope',sans-serif;font-size:1.4rem;font-weight:700;
                           margin:0 0 0.25rem 0;">Studio &amp; Artist Profile</h3>
                <p style="color:#636262;font-size:0.85rem;margin:0;">
                    Define how your studio appears in exports and headers.
                </p>
            </div>
            <span class="material-symbols-outlined"
                  style="color:#2d5a27;opacity:0.4;font-size:2rem;">brush</span>
        </div>
    """)

    col_logo, col_fields = st.columns([1, 3], gap="medium")
    with col_logo:
        st.html("""
        <div style="width:8rem;height:8rem;border-radius:0.5rem;background:#eeeeee;
                    display:flex;flex-direction:column;align-items:center;justify-content:center;
                    border:2px dashed rgba(194,201,187,0.4);cursor:pointer;">
            <span class="material-symbols-outlined" style="color:#72796e;font-size:1.5rem;">upload</span>
            <span style="font-size:0.6rem;font-weight:700;text-transform:uppercase;
                         letter-spacing:0.1em;color:#72796e;margin-top:0.5rem;">Upload Logo</span>
        </div>
        """)

    with col_fields:
        st.html('<label class="mm-settings-label">Artist Name</label>')
        artist_name = st.text_input("artist_name_hidden", value=STUDIO["artist_name"],
                                    label_visibility="collapsed")
        st.html('<label class="mm-settings-label">Studio Name</label>')
        studio_name = st.text_input("studio_name_hidden", value=STUDIO["studio_name"],
                                    label_visibility="collapsed")

    st.html('<label class="mm-settings-label" style="margin-top:1rem;">Bio / Statement</label>')
    bio = st.text_area("bio_hidden", value=STUDIO["bio"], height=100,
                        label_visibility="collapsed")

    st.html("</div>")

    # ── Connected Accounts ────────────────────────────────────────────────────
    st.html("""
    <div class="mm-card" style="margin-bottom:2rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;
                    margin-bottom:1.5rem;">
            <h3 style="font-family:'Manrope',sans-serif;font-size:1.2rem;font-weight:700;
                       margin:0;">Connected Accounts</h3>
    """)

    if st.button("+ Connect New", key="connect_new",
                 help="Launch Onboarding to connect a new bank account"):
        st.switch_page("pages/2_Onboarding.py")

    st.html("</div>")

    # Render bank accounts
    for acct in BANK_ACCOUNTS:
        if acct["account_type"] == "cash":
            continue
        masked = acct["masked"]
        bank = acct["bank_name"]
        st.html(f"""
        <div class="mm-connected-account">
            <div style="display:flex;align-items:center;gap:1rem;">
                <div class="mm-account-icon">
                    <span class="material-symbols-outlined"
                          style="color:{acct['icon_color']};">{acct['icon']}</span>
                </div>
                <div>
                    <p style="font-size:0.875rem;font-weight:700;margin:0;">
                        {acct['account_name']}
                    </p>
                    <p style="font-size:0.65rem;color:#636262;margin:0;">
                        {bank} •••• {masked}
                    </p>
                </div>
            </div>
            <div style="display:flex;gap:0.5rem;opacity:0;transition:opacity 0.2s;"
                 class="account-actions">
                <button style="background:none;border:none;cursor:pointer;padding:0.5rem;">
                    <span class="material-symbols-outlined" style="font-size:1.125rem;">edit</span>
                </button>
                <button style="background:none;border:none;cursor:pointer;padding:0.5rem;
                               color:#ba1a1a;">
                    <span class="material-symbols-outlined" style="font-size:1.125rem;">delete</span>
                </button>
            </div>
        </div>
        """)

    st.html("""
        <div class="mm-divider"></div>
        <div style="display:flex;gap:1rem;margin-top:1rem;">
    """)

    col_export, col_archive = st.columns(2, gap="small")
    with col_export:
        st.button("↓ Export All Data (.csv)", key="export_all",
                  help="Export all transactions, accounts, and COA to CSV")
    with col_archive:
        st.button("Archive Studio", key="archive_studio",
                  type="secondary",
                  help="Create a full backup of your database and archive this studio")

    st.html("</div></div>")

# ── Financial Configurations ──────────────────────────────────────────────────
with col_financial:
    st.html("""
    <div class="mm-card-low" style="margin-bottom:1.5rem;">
        <h3 style="font-family:'Manrope',sans-serif;font-size:1.1rem;font-weight:700;
                   margin:0 0 1.5rem 0;">Financial Configurations</h3>
    """)

    st.html('<label class="mm-settings-label">Base Currency</label>')
    currency = st.selectbox("currency_hidden",
                            ["USD — US Dollar", "EUR — Euro", "GBP — British Pound"],
                            label_visibility="collapsed")

    st.html('<label class="mm-settings-label">Fiscal Year Start</label>')
    fiscal_year = st.selectbox("fiscal_hidden",
                               ["January", "April", "July", "October"],
                               label_visibility="collapsed")

    st.html('<label class="mm-settings-label">Tax ID</label>')
    tax_id = st.text_input("taxid_hidden", value=STUDIO["tax_id"],
                            label_visibility="collapsed")

    st.html('<label class="mm-settings-label">Default Tax Rate (%)</label>')
    tax_rate = st.number_input("taxrate_hidden", value=STUDIO["default_tax_rate"],
                               min_value=0.0, max_value=100.0, step=0.5,
                               label_visibility="collapsed")

    accrual_on = st.toggle("Cash vs Accrual (Currently: Cash)",
                           value=False,
                           help="Accrual accounting is not available at this time.")
    if accrual_on:
        st.info("Accrual accounting is not available at this time.", icon="ℹ️")

    st.html("</div>")

    # ── Account & Security ────────────────────────────────────────────────────
    st.html("""
    <div class="mm-card-low" style="margin-bottom:1.5rem;">
        <h4 class="mm-settings-label" style="margin-bottom:1rem;">Account &amp; Security</h4>
    """)

    st.html("""
    <p class="mm-settings-label">Email</p>
    <p style="font-size:0.875rem;font-weight:500;margin-bottom:1rem;">julian@theatelier.com</p>
    """)

    st.button("Change Password 🔒", key="change_pwd")

    two_fa = st.toggle("Two-Factor Auth", value=False,
                       help="Two-factor authentication (future feature)")

    st.html("</div>")

    # ── Application Prefs ─────────────────────────────────────────────────────
    st.html("""
    <div class="mm-card-low">
        <h4 class="mm-settings-label" style="margin-bottom:1rem;">Application Prefs</h4>
        <p class="mm-settings-label">Interface Theme</p>
    """)

    theme = st.radio("theme_hidden", ["Light", "Dark", "System"],
                     horizontal=True, label_visibility="collapsed")

    compact_ui = st.toggle("Compact UI — show more rows at once", value=False)

    st.html("</div>")

# ── Footer ────────────────────────────────────────────────────────────────────
st.html("""
<div style="margin-top:4rem;border-top:1px solid rgba(194,201,187,0.2);
            padding-top:3rem;position:relative;">
    <div style="position:absolute;top:-0.75rem;left:50%;transform:translateX(-50%);
                padding:0 1rem;background:#f9f9f9;font-size:0.6rem;font-weight:800;
                text-transform:uppercase;letter-spacing:0.3em;
                color:rgba(99,98,98,0.4);">
        Est. MMXXIII
    </div>
    <div style="width:100%;height:6rem;border-radius:0.5rem;overflow:hidden;
                background:linear-gradient(135deg,#154212,#2d5a27,#a1d494);
                display:flex;align-items:center;justify-content:center;margin-bottom:2rem;">
        <span style="font-family:'Manrope',sans-serif;font-size:1.75rem;font-weight:800;
                     color:rgba(255,255,255,0.25);letter-spacing:-0.02em;">
            Creative Ledger Architecture
        </span>
    </div>
    <p style="text-align:center;font-size:0.75rem;color:#636262;max-width:36rem;
              margin:0 auto 1.5rem;">
        Financial clarity for the modern artist. Moth and Money protects your process
        so you can focus on the product.
    </p>
    <div style="display:flex;justify-content:center;gap:2rem;">
        <a href="#" style="color:rgba(99,98,98,0.6);font-size:0.65rem;font-weight:700;
                           text-transform:uppercase;letter-spacing:0.1em;text-decoration:none;">
            Privacy Charter
        </a>
        <a href="#" style="color:rgba(99,98,98,0.6);font-size:0.65rem;font-weight:700;
                           text-transform:uppercase;letter-spacing:0.1em;text-decoration:none;">
            Terms of Service
        </a>
        <a href="#" style="color:rgba(99,98,98,0.6);font-size:0.65rem;font-weight:700;
                           text-transform:uppercase;letter-spacing:0.1em;text-decoration:none;">
            API Docs
        </a>
    </div>
</div>
""")

