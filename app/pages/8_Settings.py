import base64
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

MAX_LOGO_BYTES = 2 * 1024 * 1024


def _file_to_logo_data_url(uploaded) -> str:
    raw = uploaded.getvalue()
    if len(raw) > MAX_LOGO_BYTES:
        raise ValueError("Logo must be 2 MB or smaller.")
    ct = (uploaded.type or "image/png").lower()
    if ct not in ("image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"):
        ct = "image/png"
    if ct == "image/jpg":
        ct = "image/jpeg"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{ct};base64,{b64}"


def _preview_logo_image(logo_url: str) -> None:
    """Show current logo from DB (data URL or http URL)."""
    if not logo_url:
        return
    if logo_url.startswith("data:") and "," in logo_url:
        try:
            st.image(base64.b64decode(logo_url.split(",", 1)[1]), width=128)
        except Exception:
            return
    else:
        st.image(logo_url, width=128)

from components.sidebar import load_css, render_sidebar
from components.topbar import render_settings_topbar
from data.providers import bank_accounts, db_ready, save_studio_profile_to_db, studio_profile
from db.connection import use_sample_data

st.set_page_config(
    page_title="Settings | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("settings")
render_settings_topbar("Global Settings & Configuration")

if not db_ready():
    st.stop()

if st.session_state.pop("settings_saved_flash", False):
    st.success("Settings saved.")

STUDIO = studio_profile()
BANK_ACCOUNTS = bank_accounts()

_CURRENCY_OPTIONS = ["USD — US Dollar", "EUR — Euro", "GBP — British Pound"]
_FISCAL_OPTIONS = ["January", "April", "July", "October"]
_THEME_OPTIONS = ["Light", "Dark", "System"]


def _currency_index(code: str) -> int:
    return {"USD": 0, "EUR": 1, "GBP": 2}.get((code or "USD").upper(), 0)


def _currency_code_from_label(label: str) -> str:
    if "EUR" in label:
        return "EUR"
    if "GBP" in label:
        return "GBP"
    return "USD"


def _fiscal_index(val: str) -> int:
    if val in _FISCAL_OPTIONS:
        return _FISCAL_OPTIONS.index(val)
    return 0


def _theme_index(pref: str) -> int:
    m = {"light": 0, "dark": 1, "system": 2}
    return m.get((pref or "light").lower(), 0)


def _theme_to_preference(label: str) -> str:
    return {"Light": "light", "Dark": "dark", "System": "system"}.get(label, "light")


col_connect, _ = st.columns([2, 1])
with col_connect:
    if st.button(
        "+ Connect New",
        key="connect_new",
        help="Launch Onboarding to connect a new bank account",
    ):
        st.switch_page("pages/2_Onboarding.py")

st.html("<div style='height:0.75rem'></div>")

with st.form("settings_form"):
    col_profile, col_financial = st.columns([2, 1], gap="large")

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
            st.html('<label class="mm-settings-label">Logo</label>')
            _current_logo = (STUDIO.get("logo_url") or "").strip()
            logo_file = st.file_uploader(
                "logo_uploader",
                type=["png", "jpg", "jpeg", "webp", "gif"],
                label_visibility="collapsed",
                help="PNG, JPG, WebP, or GIF. Max 2 MB.",
            )
            remove_logo = st.checkbox("Remove logo", value=False, key="settings_remove_logo")
            if logo_file is not None:
                st.image(logo_file.getvalue(), width=128)
            elif remove_logo:
                st.caption("Logo will be cleared when you save.")
                st.html("""
                <div style="width:8rem;height:8rem;border-radius:0.5rem;background:#eeeeee;
                            display:flex;flex-direction:column;align-items:center;justify-content:center;
                            border:2px dashed rgba(194,201,187,0.4);">
                    <span class="material-symbols-outlined" style="color:#72796e;font-size:1.5rem;">hide_image</span>
                </div>
                """)
            elif _current_logo:
                _preview_logo_image(_current_logo)
            else:
                st.html("""
                <div style="width:8rem;height:8rem;border-radius:0.5rem;background:#eeeeee;
                            display:flex;flex-direction:column;align-items:center;justify-content:center;
                            border:2px dashed rgba(194,201,187,0.4);">
                    <span class="material-symbols-outlined" style="color:#72796e;font-size:1.5rem;">upload</span>
                    <span style="font-size:0.6rem;font-weight:700;text-transform:uppercase;
                                 letter-spacing:0.1em;color:#72796e;margin-top:0.5rem;">No logo</span>
                </div>
                """)

        with col_fields:
            st.html('<label class="mm-settings-label">Artist Name</label>')
            artist_name = st.text_input(
                "artist_name_hidden",
                value=STUDIO["artist_name"],
                label_visibility="collapsed",
            )
            st.html('<label class="mm-settings-label">Title</label>')
            artist_title = st.text_input(
                "artist_title_hidden",
                value=STUDIO.get("artist_title", "Creative Director"),
                label_visibility="collapsed",
            )
            st.html('<label class="mm-settings-label">Studio Name</label>')
            studio_name = st.text_input(
                "studio_name_hidden",
                value=STUDIO["studio_name"],
                label_visibility="collapsed",
            )

        st.html('<label class="mm-settings-label" style="margin-top:1rem;">Bio / Statement</label>')
        bio = st.text_area(
            "bio_hidden",
            value=STUDIO["bio"],
            height=100,
            label_visibility="collapsed",
        )

        st.html("</div>")

        st.html("""
        <div class="mm-card" style="margin-bottom:2rem;">
            <div style="display:flex;justify-content:space-between;align-items:center;
                        margin-bottom:1.5rem;">
                <h3 style="font-family:'Manrope',sans-serif;font-size:1.2rem;font-weight:700;
                           margin:0;">Connected Accounts</h3>
            </div>
        """)

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

        st.html("</div>")

    with col_financial:
        st.html("""
        <div class="mm-card-low" style="margin-bottom:1.5rem;">
            <h3 style="font-family:'Manrope',sans-serif;font-size:1.1rem;font-weight:700;
                       margin:0 0 1.5rem 0;">Financial Configurations</h3>
        """)

        st.html('<label class="mm-settings-label">Base Currency</label>')
        currency = st.selectbox(
            "currency_hidden",
            _CURRENCY_OPTIONS,
            index=_currency_index(STUDIO.get("base_currency", "USD")),
            label_visibility="collapsed",
        )

        st.html('<label class="mm-settings-label">Fiscal Year Start</label>')
        fiscal_year = st.selectbox(
            "fiscal_hidden",
            _FISCAL_OPTIONS,
            index=_fiscal_index(STUDIO.get("fiscal_year_start", "January")),
            label_visibility="collapsed",
        )

        st.html('<label class="mm-settings-label">Tax ID</label>')
        tax_id = st.text_input(
            "taxid_hidden",
            value=STUDIO["tax_id"],
            label_visibility="collapsed",
        )

        st.html('<label class="mm-settings-label">Default Tax Rate (%)</label>')
        tax_rate = st.number_input(
            "taxrate_hidden",
            value=float(STUDIO["default_tax_rate"]),
            min_value=0.0,
            max_value=100.0,
            step=0.5,
            label_visibility="collapsed",
        )

        accrual_on = st.toggle(
            "Cash vs Accrual (Currently: Cash)",
            value=False,
            help="Accrual accounting is not available at this time.",
        )
        if accrual_on:
            st.info("Accrual accounting is not available at this time.", icon="ℹ️")

        st.html("</div>")

        st.html("""
        <div class="mm-card-low" style="margin-bottom:1.5rem;">
            <h4 class="mm-settings-label" style="margin-bottom:1rem;">Account &amp; Security</h4>
        """)

        st.html('<label class="mm-settings-label">Email</label>')
        email = st.text_input(
            "email_hidden",
            value=STUDIO.get("email", ""),
            label_visibility="collapsed",
        )

        st.html("</div>")

        st.html("""
        <div class="mm-card-low">
            <h4 class="mm-settings-label" style="margin-bottom:1rem;">Application Prefs</h4>
            <p class="mm-settings-label">Interface Theme</p>
        """)

        theme = st.radio(
            "theme_hidden",
            _THEME_OPTIONS,
            index=_theme_index(STUDIO.get("theme_preference", "light")),
            horizontal=True,
            label_visibility="collapsed",
        )

        compact_ui = st.toggle(
            "Compact UI — show more rows at once",
            value=bool(STUDIO.get("compact_ui", False)),
        )

        st.html("</div>")

    submitted = st.form_submit_button("Save changes", type="primary", use_container_width=True)

if submitted:
    if use_sample_data():
        st.warning(
            "Demo mode is on (USE_SAMPLE_DATA=true). Set USE_SAMPLE_DATA=false in app/.env "
            "and ensure PostgreSQL is configured to save settings to the database."
        )
    else:
        try:
            if logo_file is not None:
                _logo_url = _file_to_logo_data_url(logo_file)
            elif remove_logo:
                _logo_url = ""
            else:
                _logo_url = (STUDIO.get("logo_url") or "").strip()
            save_studio_profile_to_db(
                artist_name=artist_name.strip(),
                artist_title=artist_title.strip(),
                studio_name=studio_name.strip(),
                bio=bio,
                logo_url=_logo_url,
                email=email.strip(),
                tax_id=tax_id.strip(),
                base_currency=_currency_code_from_label(currency),
                fiscal_year_start=fiscal_year,
                default_tax_rate=float(tax_rate),
                accounting_method="cash",
                theme_preference=_theme_to_preference(theme),
                compact_ui=compact_ui,
            )
            st.session_state["settings_saved_flash"] = True
            st.rerun()
        except Exception as e:
            st.error(str(e))

st.html("<div style='height:1rem'></div>")
col_ex, col_arc = st.columns([2, 1])
with col_ex:
    c1, c2 = st.columns(2, gap="small")
    with c1:
        st.button(
            "↓ Export All Data (.csv)",
            key="export_all",
            help="Export all transactions, accounts, and COA to CSV",
        )
    with c2:
        st.button(
            "Archive Studio",
            key="archive_studio",
            type="secondary",
            help="Create a full backup of your database and archive this studio",
        )

with col_arc:
    st.button("Change Password 🔒", key="change_pwd")

st.toggle(
    "Two-Factor Auth",
    value=False,
    key="two_fa",
    help="Two-factor authentication (future feature)",
)

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
