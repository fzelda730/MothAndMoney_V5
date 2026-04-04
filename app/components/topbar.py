import streamlit as st


def render_topbar(search_placeholder: str = "Search entries or art pieces...") -> None:
    """Renders the fixed glassmorphism top bar."""
    st.html(f"""
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    <div class="mm-topbar">
        <div class="mm-topbar-search">
            <span class="material-symbols-outlined" style="font-size:1.125rem;color:#636262;">search</span>
            <span style="font-size:0.875rem;color:rgba(99,98,98,0.5);">{search_placeholder}</span>
        </div>
        <div class="mm-topbar-actions">
            <button style="background:none;border:none;cursor:pointer;position:relative;color:#154212;padding:0;">
                <span class="material-symbols-outlined">notifications</span>
                <span style="position:absolute;top:-2px;right:-2px;width:8px;height:8px;
                             background:#71151d;border-radius:50%;display:block;"></span>
            </button>
            <button style="background:none;border:none;cursor:pointer;color:#154212;padding:0;">
                <span class="material-symbols-outlined">account_circle</span>
            </button>
        </div>
    </div>
    """)


def render_settings_topbar(subtitle: str = "Global Settings & Configuration") -> None:
    """Renders the settings-style top bar (no search, has profile avatar)."""
    st.html(f"""
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    <div class="mm-topbar" style="padding: 0 3rem;">
        <div>
            <div style="font-family:'Manrope',sans-serif;font-size:1.5rem;font-weight:800;
                        color:#1a1c1c;letter-spacing:-0.02em;">
                Moth and Money Ledger For Creatives
            </div>
            <div style="font-size:0.8rem;color:#636262;font-weight:500;">{subtitle}</div>
        </div>
        <div style="display:flex;align-items:center;gap:1rem;">
            <button style="width:2.5rem;height:2.5rem;border-radius:50%;border:none;
                           background:transparent;cursor:pointer;display:flex;
                           align-items:center;justify-content:center;">
                <span class="material-symbols-outlined" style="color:#1a1c1c;">notifications</span>
            </button>
            <div style="width:2.5rem;height:2.5rem;border-radius:50%;background:#a1d494;
                        display:flex;align-items:center;justify-content:center;
                        font-weight:700;font-size:0.75rem;color:#154212;overflow:hidden;">
                JV
            </div>
        </div>
    </div>
    """)
