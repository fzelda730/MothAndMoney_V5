"""
MOTH AND MONEY — CENTRAL STYLE SHEET
ui/styles.py

Formal:  Defines the application colour palette and injects aggressive CSS
         overrides so the Moth and Money palette wins over Streamlit defaults.
Human:   One place to change the look of the whole app — with !important
         so Streamlit's own styles can't override ours.
"""

from pathlib import Path

import streamlit as st

COLOUR_TEAL   = "#008080"
COLOUR_YELLOW = "#FFD700"
COLOUR_WHITE  = "#FFFFFF"

_PROJECT_ROOT_DIRECTORY = Path(__file__).resolve().parent.parent
_HEADER_IMAGE_PATH      = _PROJECT_ROOT_DIRECTORY / "assets" / "M&M5_Header.jpg"


def render_header() -> None:
    """
    Formal:  Renders the official Moth and Money header image in the sidebar,
             anchoring brand identity across every page of the application.
    Human:   Puts the logo at the top of the sidebar so it's always visible,
             no matter which page you're on.
    """
    if not _HEADER_IMAGE_PATH.exists():
        st.sidebar.warning(
            "Header image not found. "
            "Expected it at: assets/M&M5_Header.png"
        )
        return
    st.sidebar.image(str(_HEADER_IMAGE_PATH), width="stretch")


def apply_custom_styles() -> None:
    """
    Formal:  Injects global CSS with !important overrides targeting the sidebar,
             metric card labels, metric card containers, and dataframe headers.
    Human:   Forces the Teal, Yellow, and White palette to show up — even
             when Streamlit tries to use its own default colours.
    """
    st.markdown(f"""
    <style>
        /* Sidebar — force white on both wrapper and content pane */
        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"] {{
            background-color: {COLOUR_WHITE} !important;
        }}

        /* Page headers — force teal */
        h1, h2, h3 {{
            color: {COLOUR_TEAL} !important;
        }}

        /* Metric cards — gold top border + card shadow */
        [data-testid="metric-container"] {{
            border-top: 5px solid {COLOUR_YELLOW} !important;
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}

        /* Metric label text — force teal */
        [data-testid="metric-container"] label {{
            color: {COLOUR_TEAL} !important;
        }}

        /* Metric value text — force teal */
        [data-testid="metric-container"] [data-testid="stMetricValue"] {{
            color: {COLOUR_TEAL} !important;
        }}

        /* Dataframe column headers — force teal */
        [data-testid="stDataFrame"] th {{
            color: {COLOUR_TEAL} !important;
        }}
    </style>
    """, unsafe_allow_html=True)
