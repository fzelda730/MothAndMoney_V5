import html
from urllib.parse import urlparse, urlunparse

import streamlit as st
from pathlib import Path


def _studio_for_sidebar() -> dict:
    """Studio profile for display; falls back to sample data if DB is unavailable."""
    try:
        from data.providers import studio_profile

        return studio_profile()
    except Exception:
        from data.sample_data import STUDIO

        return STUDIO


def _sidebar_bio_html(bio: str, max_chars: int = 220) -> str:
    """Escape bio for HTML; truncate long text for sidebar."""
    raw = (bio or "").strip()
    if not raw:
        return ""
    if len(raw) > max_chars:
        raw = raw[: max_chars - 1].rstrip() + "…"
    return html.escape(raw).replace("\n", "<br>")


def _streamlit_page_url(url_pathname: str) -> str:
    """
    Absolute URL for a multipage script pathname (e.g. New_Entry for pages/10_New_Entry.py).
    Used with st.link_button so the link opens in a new tab with a fresh session.
    """
    try:
        cur = st.context.url
    except Exception:
        cur = None
    if not cur:
        return f"/{url_pathname}"
    u = urlparse(cur)
    stripped = u.path.strip("/")
    if not stripped:
        new_path = f"/{url_pathname}"
    else:
        parts = stripped.split("/")
        parts[-1] = url_pathname
        new_path = "/" + "/".join(parts)
    return urlunparse((u.scheme, u.netloc, new_path, "", "", ""))


def _initials(display_name: str) -> str:
    parts = (display_name or "").strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    if parts and len(parts[0]) >= 2:
        return parts[0][:2].upper()
    if parts:
        return (parts[0][0] + "?").upper()
    return "?"


def load_css() -> None:
    css_path = Path(__file__).parent.parent / "assets" / "styles.css"
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_sidebar(_active_page: str = "") -> None:
    """
    Renders the shared sidebar navigation using st.page_link() for all nav items.
    Streamlit automatically adds aria-current="page" to the active link,
    which the CSS uses to style the active state.

    _active_page is kept for API compatibility but is no longer used.
    """
    with st.sidebar:
        # Brand
        st.html("""
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
        <div class="mm-brand">
            <h1>Moth and Money V4</h1>
            <p>The Digital Atelier</p>
        </div>
        """)

        # Main navigation — always render all links; Streamlit marks the
        # active page with aria-current="page" so CSS handles highlighting.
        st.page_link("pages/1_Dashboard.py",  label="Dashboard",  icon="🏠")
        st.page_link("pages/2_Onboarding.py", label="Onboarding", icon="📋")
        st.page_link("pages/6_Ledger.py",     label="Ledger",     icon="📖")
        st.page_link("pages/7_Reports.py",    label="Reports",    icon="📊")

        # New Entry — opens in a new tab (st.link_button; new Streamlit session per tab)
        st.markdown('<div class="mm-new-entry-sidebar-wrap">', unsafe_allow_html=True)
        st.link_button(
            "New Entry",
            _streamlit_page_url("New_Entry"),
            type="primary",
            width="stretch",
            help="Chart of account, journal entry, or register transaction — opens in a new browser tab",
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.html("""<div class="mm-sidebar-divider" style="margin-top:1rem;"></div>""")

        # Bottom navigation
        st.page_link("pages/8_Settings.py", label="Settings", icon="⚙️")

        # Support — no target page yet, render as plain text link
        st.html("""
        <div class="mm-nav-link" style="cursor:default;opacity:0.5;">
            <span class="material-symbols-outlined">help</span>
            <span>Support</span>
        </div>
        """)

        # User profile: artist_name, artist_title, studio_name, bio (studio_profile / sample)
        _sp = _studio_for_sidebar()
        _name = html.escape(_sp.get("artist_name") or "Your Name")
        _title_raw = (_sp.get("artist_title") or "").strip()
        _title_block = (
            f'<div class="role">{html.escape(_title_raw)}</div>' if _title_raw else ""
        )
        _studio = html.escape(_sp.get("studio_name") or "Your Studio")
        _bio = _sidebar_bio_html(_sp.get("bio") or "")
        _ini = html.escape(_initials(_sp.get("artist_name") or ""))
        _bio_block = f'<div class="bio">{_bio}</div>' if _bio else ""
        _logo = (_sp.get("logo_url") or "").strip()
        _avatar_html = (
            f'<img src="{html.escape(_logo, quote=True)}" alt="" '
            'style="width:2rem;height:2rem;border-radius:50%;object-fit:cover;'
            'flex-shrink:0;background:#eeeeee;" />'
            if _logo
            and (
                _logo.startswith("data:image/")
                or _logo.startswith("http://")
                or _logo.startswith("https://")
            )
            else f"""<div class="mm-user-avatar" style="width:2rem;height:2rem;border-radius:50%;
                        background:#a1d494;display:flex;align-items:center;justify-content:center;
                        flex-shrink:0;font-weight:700;font-size:0.75rem;color:#154212;">{_ini}</div>"""
        )
        st.html(f"""
        <div class="mm-user-profile">
            {_avatar_html}
            <div class="mm-user-profile-text">
                <div class="name">{_name}</div>
                {_title_block}
                <div class="studio">{_studio}</div>
                {_bio_block}
            </div>
        </div>
        """)
