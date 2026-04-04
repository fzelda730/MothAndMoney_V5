import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.providers import bank_accounts, dashboard_stats, db_ready, tax_provision

st.set_page_config(
    page_title="Dashboard | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("dashboard")
render_topbar()

if not db_ready():
    st.stop()

DASHBOARD_STATS = dashboard_stats()
BANK_ACCOUNTS = bank_accounts()
TAX_PROVISION = tax_provision()

# ── Main content ──────────────────────────────────────────────────────────────

# Page titles
st.html("""
<div style="margin-left:3rem; margin-bottom:1rem;">
    <h1 class="mm-page-title">Moth and Money Ledger For Creatives</h1>
</div>
<div style="margin-left:3rem; margin-bottom:3rem;">
    <h2 class="mm-page-subtitle">The Studio Ledger</h2>
    <p class="mm-page-description">
        Tracking the flow of value between the physical creation and the digital marketplace.
        Your atelier's health at a glance.
    </p>
</div>
""")

# ── Bento summary grid ────────────────────────────────────────────────────────
col_hero, col_income = st.columns([2, 1], gap="large")

with col_hero:
    trend = DASHBOARD_STATS["portfolio_trend"]
    liquidity = DASHBOARD_STATS["available_liquidity"]
    commissions = DASHBOARD_STATS["pending_commissions"]
    portfolio = DASHBOARD_STATS["total_portfolio_value"]
    st.html(f"""
    <div class="mm-card" style="position:relative;overflow:hidden;min-height:180px;">
        <div style="position:relative;z-index:1;">
            <span class="mm-stat-label">Total Portfolio Value</span>
            <div style="display:flex;align-items:baseline;gap:1rem;margin-bottom:2rem;">
                <span class="mm-stat-value">${portfolio:,.0f}</span>
                <span class="mm-trend-up">
                    <span class="material-symbols-outlined" style="font-size:0.9rem;">trending_up</span>
                    {trend}%
                </span>
            </div>
            <div style="display:flex;gap:2rem;">
                <div>
                    <span style="display:block;font-size:0.7rem;color:#636262;margin-bottom:0.25rem;">
                        Available Liquidity
                    </span>
                    <span style="font-size:1.2rem;font-weight:600;">${liquidity:,.2f}</span>
                </div>
                <div style="border-left:1px solid rgba(194,201,187,0.3);padding-left:2rem;">
                    <span style="display:block;font-size:0.7rem;color:#636262;margin-bottom:0.25rem;">
                        Pending Commissions
                    </span>
                    <span style="font-size:1.2rem;font-weight:600;">${commissions:,.2f}</span>
                </div>
            </div>
        </div>
        <div style="position:absolute;top:0;right:0;width:16rem;height:100%;
                    background:linear-gradient(to left,rgba(188,240,174,0.12),transparent);
                    pointer-events:none;"></div>
    </div>
    """)

with col_income:
    income = DASHBOARD_STATS["studio_income"]
    income_label = DASHBOARD_STATS["studio_income_label"]
    st.html(f"""
    <div class="mm-card-primary" style="min-height:180px;display:flex;flex-direction:column;
                                        justify-content:space-between;">
        <div>
            <span class="material-symbols-outlined" style="font-size:2rem;margin-bottom:1rem;
                  display:block;color:#9dd090;">payments</span>
            <h3 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1.1rem;
                       color:#9dd090;margin:0;">Studio Income</h3>
        </div>
        <div>
            <span style="font-size:2rem;font-weight:800;font-family:'Manrope',sans-serif;
                         color:#ffffff;">${income:,.0f}</span>
            <p style="font-size:0.7rem;opacity:0.8;margin-top:0.25rem;color:#9dd090;">
                {income_label}
            </p>
        </div>
    </div>
    """)

st.html("<div style='height:1.5rem'></div>")

col_costs, col_action = st.columns([1, 2], gap="large")

with col_costs:
    costs = DASHBOARD_STATS["material_costs"]
    costs_label = DASHBOARD_STATS["material_costs_label"]
    st.html(f"""
    <div class="mm-card-gray" style="min-height:160px;display:flex;flex-direction:column;
                                      justify-content:space-between;">
        <div>
            <span class="material-symbols-outlined"
                  style="font-size:2rem;color:#71151d;margin-bottom:1rem;display:block;">
                shopping_bag
            </span>
            <h3 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1.1rem;
                       margin:0;">Material Costs</h3>
        </div>
        <div>
            <span style="font-size:2rem;font-weight:800;font-family:'Manrope',sans-serif;">
                ${costs:,.0f}
            </span>
            <p style="font-size:0.7rem;color:#636262;margin-top:0.25rem;">{costs_label}</p>
        </div>
    </div>
    """)

with col_action:
    st.html("""
    <div class="mm-card-glass">
        <div class="mm-card-glass-inner"
             style="display:flex;align-items:center;justify-content:space-between;
                    min-height:160px;">
            <div style="display:flex;align-items:center;gap:1.5rem;">
                <div style="width:4rem;height:4rem;background:#eeeeee;border-radius:50%;
                             display:flex;align-items:center;justify-content:center;">
                    <span class="material-symbols-outlined" style="font-size:1.5rem;">
                        upload_file
                    </span>
                </div>
                <div>
                    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;
                               font-size:1rem;margin:0 0 0.25rem 0;">Process Sales Data</h4>
                    <p style="font-size:0.8rem;color:#636262;margin:0;">
                        Import CSV from Shopify or Etsy
                    </p>
                </div>
            </div>
            <button class="mm-btn-outline">Launch Importer</button>
        </div>
    </div>
    """)

st.html("<div style='height:3rem'></div>")

# ── Financial Accounts table ──────────────────────────────────────────────────
st.html("""
<div class="mm-section-header">
    <h3 class="mm-section-title">Financial Accounts</h3>
    <span style="font-size:0.875rem;font-weight:500;color:#154212;cursor:pointer;">
        Manage Accounts
    </span>
</div>
""")

# Build table HTML
rows_html = ""
for acct in BANK_ACCOUNTS:
    beg = acct["beginning_balance"]
    deb = acct["total_debits"]
    crd = acct["total_credits"]
    end = acct["ending_balance"]

    deb_str = f'<span class="mm-debit">-${abs(deb):,.2f}</span>' if deb and deb < 0 else \
              f'<span class="mm-muted">${deb:,.2f}</span>'
    crd_str = f'<span class="mm-credit">+${crd:,.2f}</span>' if crd and crd > 0 else \
              f'<span class="mm-muted">${crd:,.2f}</span>'
    end_color = "#154212" if end >= 0 else "#71151d"

    rows_html += f"""
    <tr>
        <td style="padding:1rem 1.5rem;background:#ffffff;border-left:4px solid {acct['accent']};
                   border-radius:2px 0 0 2px;">
            <div class="mm-account-name">
                <span class="material-symbols-outlined"
                      style="color:{acct['icon_color']};">{acct['icon']}</span>
                {acct['account_name']}
            </div>
        </td>
        <td style="padding:1rem 1.5rem;text-align:right;background:#ffffff;
                   color:#636262;font-weight:500;">${beg:,.2f}</td>
        <td style="padding:1rem 1.5rem;text-align:right;background:#ffffff;">{deb_str}</td>
        <td style="padding:1rem 1.5rem;text-align:right;background:#ffffff;">{crd_str}</td>
        <td style="padding:1rem 1.5rem;text-align:right;background:#ffffff;
                   font-weight:700;color:{end_color};border-radius:0 2px 2px 0;">
            ${end:,.2f}
        </td>
    </tr>
    <tr><td colspan="5" style="height:0.5rem;background:transparent;"></td></tr>
    """

st.html(f"""
<div style="overflow-x:auto;margin-right:4rem;">
    <table class="mm-accounts-table">
        <thead>
            <tr>
                <th style="text-align:left;">Account Name</th>
                <th>Beginning Balance</th>
                <th>Total Debits</th>
                <th>Total Credits</th>
                <th>Ending Balance</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
</div>
""")

st.html("<div style='height:4rem'></div>")

# ── Footer insight section ────────────────────────────────────────────────────
col_tax, col_art = st.columns([5, 7], gap="large")

with col_tax:
    qs = TAX_PROVISION["quarterly_sales"]
    ra = TAX_PROVISION["reserve_amount"]
    st.html(f"""
    <div class="mm-tax-note">
        <h4>Tax Provision Note</h4>
        <p>
            Based on your current quarterly sales of
            <strong style="color:#1a1c1c;">${qs:,.0f}</strong>, we recommend setting aside
            <strong style="color:#154212;">${ra:,.0f}</strong> for end-of-quarter liabilities.
        </p>
        <button class="mm-btn-ghost" style="margin-top:1.5rem;font-size:0.7rem;
                letter-spacing:0.1em;text-transform:uppercase;display:flex;align-items:center;
                gap:0.5rem;">
            Move to Reserve
            <span class="material-symbols-outlined" style="font-size:0.875rem;">arrow_forward</span>
        </button>
    </div>
    """)

with col_art:
    st.html("""
    <div style="position:relative;width:100%;max-width:24rem;aspect-ratio:16/9;
                border-radius:0.5rem;overflow:hidden;margin-left:auto;
                background:linear-gradient(135deg,#2d5a27,#a1d494,#1a1c1c);">
        <div style="position:absolute;inset:0;display:flex;flex-direction:column;
                    justify-content:flex-end;padding:1.5rem;
                    background:linear-gradient(to top,rgba(26,28,28,0.6),transparent);">
            <p style="font-size:0.6rem;text-transform:uppercase;letter-spacing:0.2em;
                      color:rgba(255,255,255,0.7);margin-bottom:0.25rem;">
                Latest Collection Status
            </p>
            <h5 style="font-family:'Manrope',sans-serif;font-size:1.25rem;font-weight:700;
                       color:#ffffff;margin:0;">Ephemeral Series: 80% Sold</h5>
        </div>
    </div>
    """)

st.html("<div style='height:4rem'></div>")

# ── Footer banner ─────────────────────────────────────────────────────────────
st.html("""
<div style="border-top:1px solid rgba(194,201,187,0.2);padding-top:2rem;margin-right:4rem;">
    <div style="width:100%;height:10rem;border-radius:0.5rem;overflow:hidden;margin-bottom:2rem;
                background:linear-gradient(135deg,#154212 0%,#2d5a27 50%,#a1d494 100%);
                display:flex;align-items:center;justify-content:center;">
        <span style="font-family:'Manrope',sans-serif;font-size:1.5rem;font-weight:800;
                     color:rgba(255,255,255,0.3);letter-spacing:-0.02em;">
            Creative Ledger Architecture
        </span>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:0 0.5rem 2rem;">
        <div style="display:flex;align-items:center;gap:1rem;">
            <span style="font-weight:700;color:#1a1c1c;font-size:0.75rem;">Moth and Money V4</span>
            <span style="width:4px;height:4px;background:#c2c9bb;border-radius:50%;
                         display:inline-block;"></span>
            <span style="color:#636262;font-size:0.75rem;">© 2024 The Digital Atelier</span>
        </div>
        <div style="display:flex;gap:2rem;">
            <a href="#" style="color:#636262;font-size:0.75rem;text-decoration:none;">Privacy Policy</a>
            <a href="#" style="color:#636262;font-size:0.75rem;text-decoration:none;">Terms of Service</a>
            <a href="#" style="color:#636262;font-size:0.75rem;text-decoration:none;">Documentation</a>
        </div>
    </div>
</div>
""")

