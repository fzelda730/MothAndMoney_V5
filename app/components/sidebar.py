import streamlit as st
from pathlib import Path


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

        # New Entry button
        st.html("""
        <div style="padding: 0 1rem; margin-top: 0.5rem;">
            <button class="mm-new-entry-btn">
                <span class="material-symbols-outlined" style="font-size:1rem;">add</span>
                New Entry
            </button>
        </div>
        <div class="mm-sidebar-divider" style="margin-top:1rem;"></div>
        """)

        # Bottom navigation
        st.page_link("pages/8_Settings.py", label="Settings", icon="⚙️")

        # Support — no target page yet, render as plain text link
        st.html("""
        <div class="mm-nav-link" style="cursor:default;opacity:0.5;">
            <span class="material-symbols-outlined">help</span>
            <span>Support</span>
        </div>
        """)

        # User profile
        st.html("""
        <div class="mm-user-profile">
            <div style="width:2rem;height:2rem;border-radius:50%;background:#a1d494;
                        display:flex;align-items:center;justify-content:center;
                        font-weight:700;font-size:0.75rem;color:#154212;">JV</div>
            <div>
                <div class="name">Julian Voss</div>
                <div class="role">Creative Director</div>
            </div>
        </div>
        """)
