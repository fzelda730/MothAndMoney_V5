import streamlit as st
import sys
from pathlib import Path
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.sample_data import (
    PL_INCOME, PL_EXPENSES, PL_SUMMARY, QUARTERLY_PERFORMANCE,
    BANK_ACCOUNTS, BALANCE_SHEET, CHART_OF_ACCOUNTS, TRIAL_BALANCE_REPORT
)

st.set_page_config(
    page_title="Reports | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("reports")
render_topbar("Search data...")



# ── Account selector ──────────────────────────────────────────────────────────
account_options = ["All Accounts"] + [
    f"{a['account_name']} ****{a['masked']}"
    for a in BANK_ACCOUNTS if a["account_type"] != "cash"
]

st.html('<label class="mm-settings-label">Select Account</label>')
selected_account = st.selectbox("report_account", account_options,
                                 label_visibility="collapsed")

st.html("<div style='height:1rem'></div>")

# ── Report tabs ───────────────────────────────────────────────────────────────
tab_pl, tab_bs, tab_gl, tab_tb = st.tabs([
    "Profit and Loss", "Balance Sheet", "General Ledger", "Trial Balance"
])

# ────────────────────────────────────────────────────────────────────────────────
# TAB 1: Profit and Loss
# ────────────────────────────────────────────────────────────────────────────────
with tab_pl:
    col_header, col_exports = st.columns([3, 1], gap="large")
    with col_header:
        st.html(f"""
        <p style="color:#154212;font-size:0.65rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.15em;margin-bottom:0.5rem;">Financial Statement</p>
        <h2 style="font-family:'Manrope',sans-serif;font-size:2.5rem;font-weight:800;
                   letter-spacing:-0.03em;margin:0 0 0.5rem;">Profit and Loss</h2>
        <p style="color:#636262;font-style:italic;opacity:0.8;font-size:0.95rem;">
            {PL_SUMMARY['fiscal_year']}
        </p>
        """)
    with col_exports:
        st.html("<div style='height:2rem'></div>")
        col_pdf, col_csv = st.columns(2, gap="small")
        with col_pdf:
            st.button("📄 Export PDF", key="pl_pdf")
        with col_csv:
            st.button("📊 Export CSV", key="pl_csv", type="primary")

    st.html("<div style='height:1.5rem'></div>")

    col_stats, col_table = st.columns([2, 3], gap="large")

    with col_stats:
        rev = PL_SUMMARY["gross_revenue"]
        exp = PL_SUMMARY["operating_expenses"]
        net = PL_SUMMARY["net_profit"]
        vs_ly = PL_SUMMARY["revenue_vs_ly"]
        note = PL_SUMMARY["net_profit_note"]

        st.html(f"""
        <div class="mm-report-stat-card" style="margin-bottom:1.5rem;">
            <span class="mm-stat-label">Gross Revenue</span>
            <div>
                <div style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:700;
                            color:#154212;">${rev:,.2f}</div>
                <div style="font-size:0.75rem;color:#2d5a27;margin-top:0.5rem;
                             display:flex;align-items:center;gap:0.25rem;">
                    <span class="material-symbols-outlined" style="font-size:0.875rem;">
                        trending_up
                    </span>
                    +{vs_ly}% vs LY
                </div>
            </div>
        </div>

        <div class="mm-card-low" style="margin-bottom:1.5rem;min-height:12rem;
                                         display:flex;flex-direction:column;
                                         justify-content:space-between;">
            <span class="mm-stat-label">Operating Expenses</span>
            <div>
                <div style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:700;">
                    ${exp:,.2f}
                </div>
                <div style="font-size:0.75rem;color:#636262;margin-top:0.5rem;
                             display:flex;align-items:center;gap:0.25rem;">
                    <span class="material-symbols-outlined" style="font-size:0.875rem;">remove</span>
                    On track with budget
                </div>
            </div>
        </div>

        <div class="mm-report-net-card">
            <div style="position:relative;z-index:1;">
                <span class="mm-stat-label" style="color:rgba(255,255,255,0.8);">Net Profit</span>
                <div style="font-family:'Manrope',sans-serif;font-size:2.5rem;font-weight:800;
                            color:#ffffff;margin-top:1rem;">${net:,.2f}</div>
            </div>
            <div style="background:rgba(45,90,39,0.4);backdrop-filter:blur(8px);
                        border-radius:0.5rem;padding:1rem;position:relative;z-index:1;">
                <p style="font-size:0.75rem;font-style:italic;opacity:0.9;color:#ffffff;
                           margin:0;">"{note}"</p>
            </div>
            <div style="position:absolute;right:-3rem;bottom:-3rem;width:12rem;height:12rem;
                        background:rgba(161,212,148,0.15);border-radius:50%;
                        filter:blur(40px);"></div>
        </div>
        """)

    with col_table:
        # Income table
        st.html("""
        <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1.1rem;
                   margin-bottom:1.5rem;">Income Details</h4>
        """)

        income_rows = ""
        for row in PL_INCOME:
            deb_str = f"${row['debit']:,.2f}" if row["debit"] else "—"
            crd_str = f"${row['credit']:,.2f}" if row["credit"] else "—"
            income_rows += f"""
            <tr>
                <td style="padding:1.25rem 0;border-bottom:1px solid rgba(194,201,187,0.1);
                           font-weight:500;">{row['account']}</td>
                <td style="padding:1.25rem 0;text-align:right;color:#636262;
                           border-bottom:1px solid rgba(194,201,187,0.1);">{deb_str}</td>
                <td style="padding:1.25rem 0;text-align:right;
                           border-bottom:1px solid rgba(194,201,187,0.1);">{crd_str}</td>
                <td style="padding:1.25rem 0;text-align:right;font-weight:600;
                           border-bottom:1px solid rgba(194,201,187,0.1);">
                    ${row['total']:,.2f}
                </td>
            </tr>"""

        total_income = sum(r["total"] for r in PL_INCOME)
        income_rows += f"""
        <tr style="background:rgba(238,238,238,0.3);">
            <td style="padding:1.5rem 0;font-weight:700;">Total Operating Income</td>
            <td style="padding:1.5rem 0;text-align:right;color:#636262;">—</td>
            <td style="padding:1.5rem 0;text-align:right;color:#636262;">—</td>
            <td style="padding:1.5rem 0;text-align:right;font-weight:700;color:#154212;">
                ${total_income:,.2f}
            </td>
        </tr>"""

        st.html(f"""
        <div class="mm-report-table">
            <table>
                <thead>
                    <tr>
                        <th style="text-align:left;">Account Name</th>
                        <th>Debit</th>
                        <th>Credit</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>{income_rows}</tbody>
            </table>
        """)

        # Expense table
        st.html("""
        <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1.1rem;
                   margin:3rem 0 1.5rem;">Expense Details</h4>
        """)

        expense_rows = ""
        for row in PL_EXPENSES:
            deb_str = f"${row['debit']:,.2f}" if row["debit"] else "—"
            expense_rows += f"""
            <tr>
                <td style="padding:1.25rem 0;border-bottom:1px solid rgba(194,201,187,0.1);
                           font-weight:500;">{row['account']}</td>
                <td style="padding:1.25rem 0;text-align:right;
                           border-bottom:1px solid rgba(194,201,187,0.1);">{deb_str}</td>
                <td style="padding:1.25rem 0;text-align:right;color:#636262;
                           border-bottom:1px solid rgba(194,201,187,0.1);">—</td>
                <td style="padding:1.25rem 0;text-align:right;font-weight:600;
                           border-bottom:1px solid rgba(194,201,187,0.1);">
                    ${row['total']:,.2f}
                </td>
            </tr>"""

        total_expenses = sum(r["total"] for r in PL_EXPENSES)
        expense_rows += f"""
        <tr style="background:rgba(238,238,238,0.3);">
            <td style="padding:1.5rem 0;font-weight:700;">Total Operating Expenses</td>
            <td style="padding:1.5rem 0;text-align:right;font-weight:700;">
                ${total_expenses:,.2f}
            </td>
            <td style="padding:1.5rem 0;text-align:right;color:#636262;">—</td>
            <td style="padding:1.5rem 0;text-align:right;font-weight:700;">
                ${total_expenses:,.2f}
            </td>
        </tr>"""

        st.html(f"""
            <table>
                <tbody>{expense_rows}</tbody>
            </table>

            <div style="margin-top:3rem;padding-top:1.5rem;
                        border-top:1px solid rgba(194,201,187,0.2);
                        display:flex;justify-content:space-between;align-items:flex-end;">
                <div>
                    <p style="font-size:0.6rem;font-weight:700;text-transform:uppercase;
                               letter-spacing:0.15em;color:#636262;margin-bottom:0.25rem;">
                        Generated On
                    </p>
                    <p style="font-size:0.8rem;font-weight:500;">{PL_SUMMARY['generated_on']}</p>
                </div>
                <div style="text-align:right;">
                    <p style="font-size:0.6rem;font-weight:700;text-transform:uppercase;
                               letter-spacing:0.15em;color:#636262;margin-bottom:0.25rem;">
                        Net Ordinary Income
                    </p>
                    <p style="font-family:'Manrope',sans-serif;font-size:1.5rem;font-weight:700;
                               color:#154212;">${PL_SUMMARY['net_profit']:,.2f}</p>
                </div>
            </div>
        </div>
        """)

    st.html("<div style='height:3rem'></div>")

    # ── Quarterly Performance chart ───────────────────────────────────────────
    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1.4rem;
               margin-bottom:1.5rem;">Quarterly Performance</h4>
    """)

    quarters = [q["quarter"] for q in QUARTERLY_PERFORMANCE]
    revenues  = [q["revenue"]  for q in QUARTERLY_PERFORMANCE]
    projected = [q["projected"] for q in QUARTERLY_PERFORMANCE]

    colors = ["#a1d494" if not p else "#c2c9bb" for p in projected]

    fig = go.Figure(go.Bar(
        x=quarters,
        y=revenues,
        marker_color=colors,
        text=[f"${r:,.0f}" for r in revenues],
        textposition="outside",
        textfont=dict(family="Inter", size=12, color="#1a1c1c"),
    ))

    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        height=220,
        font=dict(family="Inter"),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=11, color="#636262"),
            linecolor="rgba(194,201,187,0.2)",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(194,201,187,0.15)",
            tickformat="$,.0f",
            tickfont=dict(size=10, color="#636262"),
            zeroline=False,
        ),
        bargap=0.4,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ────────────────────────────────────────────────────────────────────────────────
# TAB 2: Balance Sheet (simplified cash-basis)
# ────────────────────────────────────────────────────────────────────────────────
with tab_bs:
    st.html("""
    <div style="display:inline-flex;align-items:center;gap:0.5rem;background:#bcf0ae;
                color:#154212;font-size:0.65rem;font-weight:700;padding:0.25rem 0.75rem;
                border-radius:0.75rem;margin-bottom:1.5rem;">
        <span class="material-symbols-outlined" style="font-size:0.875rem;">info</span>
        Simplified Cash-Basis View
    </div>
    <h2 style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:800;
               letter-spacing:-0.02em;margin:0 0 0.5rem;">Balance Sheet</h2>
    <p style="color:#636262;font-style:italic;margin-bottom:2rem;">
        Cash-basis accounting shows assets and liabilities based on actual cash flows only.
    </p>
    """)

    col_bs_assets, col_bs_liab = st.columns(2, gap="large")

    with col_bs_assets:
        st.html("""
        <div class="mm-report-table">
            <h4 style="font-family:'Manrope',sans-serif;font-weight:700;margin-bottom:1.5rem;">
                Assets
            </h4>
        """)
        total_assets = sum(a["amount"] for a in BALANCE_SHEET["assets"])
        asset_rows = ""
        for a in BALANCE_SHEET["assets"]:
            asset_rows += f"""
            <tr>
                <td style="padding:1rem 0;border-bottom:1px solid rgba(194,201,187,0.1);
                           font-weight:500;">{a['account']}</td>
                <td style="padding:1rem 0;text-align:right;
                           border-bottom:1px solid rgba(194,201,187,0.1);">
                    ${a['amount']:,.2f}
                </td>
            </tr>"""
        st.html(f"""
            <table style="width:100%;border-collapse:collapse;font-size:0.875rem;">
                <tbody>
                    {asset_rows}
                    <tr>
                        <td style="padding:1.25rem 0;font-weight:700;">Total Assets</td>
                        <td style="padding:1.25rem 0;text-align:right;font-weight:700;
                                   color:#154212;">${total_assets:,.2f}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """)

    with col_bs_liab:
        st.html("""
        <div class="mm-report-table">
            <h4 style="font-family:'Manrope',sans-serif;font-weight:700;margin-bottom:1.5rem;">
                Liabilities
            </h4>
        """)
        total_liab = sum(l["amount"] for l in BALANCE_SHEET["liabilities"])
        liab_rows = ""
        for l in BALANCE_SHEET["liabilities"]:
            liab_rows += f"""
            <tr>
                <td style="padding:1rem 0;border-bottom:1px solid rgba(194,201,187,0.1);
                           font-weight:500;">{l['account']}</td>
                <td style="padding:1rem 0;text-align:right;
                           border-bottom:1px solid rgba(194,201,187,0.1);">
                    ${l['amount']:,.2f}
                </td>
            </tr>"""
        net_position = total_assets - total_liab
        st.html(f"""
            <table style="width:100%;border-collapse:collapse;font-size:0.875rem;">
                <tbody>
                    {liab_rows}
                    <tr>
                        <td style="padding:1.25rem 0;font-weight:700;">Total Liabilities</td>
                        <td style="padding:1.25rem 0;text-align:right;font-weight:700;
                                   color:#71151d;">${total_liab:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding:1.25rem 0;font-weight:700;
                                   border-top:2px solid rgba(194,201,187,0.3);">
                            Net Position (Assets – Liabilities)
                        </td>
                        <td style="padding:1.25rem 0;text-align:right;font-weight:700;
                                   color:#154212;font-size:1.1rem;
                                   border-top:2px solid rgba(194,201,187,0.3);">
                            ${net_position:,.2f}
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        """)

# ────────────────────────────────────────────────────────────────────────────────
# TAB 3: General Ledger (Chart of Accounts with balances)
# ────────────────────────────────────────────────────────────────────────────────
with tab_gl:
    st.html("""
    <h2 style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:800;
               letter-spacing:-0.02em;margin:0 0 0.5rem;">General Ledger</h2>
    <p style="color:#636262;margin-bottom:2rem;">
        Complete Chart of Accounts with current period balances.
    </p>
    """)

    current_type = None
    for acct in CHART_OF_ACCOUNTS:
        if acct["type"] != current_type:
            current_type = acct["type"]
            type_color = {
                "Asset": "#154212", "Liability": "#71151d",
                "Equity": "#2d5a27", "Income": "#154212", "Expense": "#636262"
            }.get(current_type, "#1a1c1c")
            st.html(f"""
            <div style="margin-top:1.5rem;margin-bottom:0.75rem;padding-bottom:0.5rem;
                        border-bottom:1px solid rgba(194,201,187,0.2);">
                <span style="font-size:0.65rem;font-weight:800;text-transform:uppercase;
                             letter-spacing:0.15em;color:{type_color};">{current_type}</span>
            </div>
            """)

        st.html(f"""
        <div style="display:flex;justify-content:space-between;padding:0.6rem 0.5rem;
                    border-radius:0.125rem;transition:background 0.2s;">
            <div style="display:flex;gap:1.5rem;align-items:center;">
                <span style="font-family:'Courier New',monospace;font-size:0.75rem;
                             color:#636262;min-width:3rem;">{acct['number']}</span>
                <span style="font-size:0.875rem;font-weight:500;">{acct['name']}</span>
                <span style="font-size:0.65rem;color:#636262;background:#eeeeee;
                             padding:0.1rem 0.5rem;border-radius:0.75rem;">
                    {acct['subtype']}
                </span>
            </div>
            <span style="font-size:0.75rem;color:#636262;">—</span>
        </div>
        """)

# ────────────────────────────────────────────────────────────────────────────────
# TAB 4: Trial Balance
# ────────────────────────────────────────────────────────────────────────────────
with tab_tb:
    st.html("""
    <h2 style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:800;
               letter-spacing:-0.02em;margin:0 0 0.5rem;">Trial Balance</h2>
    <p style="color:#636262;margin-bottom:2rem;">
        Opening balances as established during onboarding.
    </p>
    """)

    tb_rows = ""
    total_deb = 0
    total_crd = 0
    for row in TRIAL_BALANCE_REPORT:
        deb_str = f"${row['debits']:,.2f}" if row["debits"] else "—"
        crd_str = f"${row['credits']:,.2f}" if row["credits"] else "—"
        if row["debits"]:
            total_deb += row["debits"]
        if row["credits"]:
            total_crd += row["credits"]
        tb_rows += f"""
        <tr style="background:#ffffff;">
            <td style="padding:1rem;font-family:'Courier New',monospace;font-size:0.75rem;
                       color:#636262;">{row['bank_account']}</td>
            <td style="padding:1rem;font-size:0.8rem;color:#636262;">{row['coa']}</td>
            <td style="padding:1rem;text-align:right;font-size:0.875rem;">{deb_str}</td>
            <td style="padding:1rem;text-align:right;font-size:0.875rem;">{crd_str}</td>
        </tr>
        <tr><td colspan="4" style="height:0.25rem;background:transparent;"></td></tr>"""

    st.html(f"""
    <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:separate;border-spacing:0 0.25rem;">
            <thead>
                <tr>
                    <th style="padding:0.75rem 1rem;text-align:left;font-size:0.65rem;
                               font-weight:700;text-transform:uppercase;letter-spacing:0.1em;
                               color:#636262;">Bank Account</th>
                    <th style="padding:0.75rem 1rem;text-align:left;font-size:0.65rem;
                               font-weight:700;text-transform:uppercase;letter-spacing:0.1em;
                               color:#636262;">COA Number</th>
                    <th style="padding:0.75rem 1rem;text-align:right;font-size:0.65rem;
                               font-weight:700;text-transform:uppercase;letter-spacing:0.1em;
                               color:#636262;">Debits</th>
                    <th style="padding:0.75rem 1rem;text-align:right;font-size:0.65rem;
                               font-weight:700;text-transform:uppercase;letter-spacing:0.1em;
                               color:#636262;">Credits</th>
                </tr>
            </thead>
            <tbody>{tb_rows}</tbody>
        </table>

        <div style="background:#f3f3f3;border-radius:0.125rem;padding:1.25rem 1.5rem;
                    display:flex;justify-content:space-between;margin-top:0.5rem;">
            <span style="font-size:0.65rem;font-weight:700;text-transform:uppercase;
                         letter-spacing:0.1em;color:#636262;">Balance Totals</span>
            <div style="display:flex;gap:3rem;">
                <div style="text-align:right;">
                    <div style="font-size:0.6rem;color:#636262;font-weight:700;
                                text-transform:uppercase;margin-bottom:0.25rem;">Total Debits</div>
                    <div style="font-size:1.1rem;font-weight:700;font-family:'Manrope',sans-serif;">
                        ${total_deb:,.2f}
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:0.6rem;color:#636262;font-weight:700;
                                text-transform:uppercase;margin-bottom:0.25rem;">Total Credits</div>
                    <div style="font-size:1.1rem;font-weight:700;font-family:'Manrope',sans-serif;">
                        ${total_crd:,.2f}
                    </div>
                </div>
            </div>
        </div>
    </div>
    """)

# ── Decorative footer ─────────────────────────────────────────────────────────
st.html("""
<div style="margin-top:4rem;width:100%;height:8rem;border-radius:0.5rem;overflow:hidden;
            background:linear-gradient(135deg,#154212,#2d5a27 60%,#a1d494);margin-bottom:1rem;">
</div>
<p style="text-align:center;font-size:0.6rem;font-weight:700;text-transform:uppercase;
          letter-spacing:0.2em;color:rgba(99,98,98,0.4);">
    THE DIGITAL ATELIER © 2024 • PRIVATE &amp; CONFIDENTIAL
</p>
""")

