import csv
import html
import sys
from io import StringIO
from pathlib import Path
from datetime import date, datetime

import streamlit as st
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.sample_data import (
    PL_INCOME,
    PL_EXPENSES,
    PL_SUMMARY,
    QUARTERLY_PERFORMANCE,
    BALANCE_SHEET,
    REPORTS_FISCAL_YEAR_START,
    REPORTS_FISCAL_YEAR_END,
    SAMPLE_ACCOUNT_DETAIL,
)
from data.providers import (
    bank_accounts,
    chart_of_accounts,
    db_ready,
    general_ledger_report,
    trial_balance_report,
)
from db.connection import use_sample_data


def _bank_id_for_report_label(label: str, accounts: list[Any]) -> Optional[str]:
    if label == "All Accounts":
        return None
    for a in accounts:
        if f"{a['account_name']} ****{a['masked']}" == label:
            return a["id"]
    return None


def _normalize_period(d0, d1):
    if d0 > d1:
        return d1, d0
    return d0, d1


def _gl_account_type_banner(coatype: str) -> str:
    m = {
        "asset": "ASSET",
        "liability": "LIABILITY",
        "equity": "EQUITY",
        "income": "INCOME",
        "expense": "EXPENSE",
    }
    key = (coatype or "").strip().lower()
    return f"{m.get(key, 'CHART')} ACCOUNT"


def _gl_format_line_date(date_str: str) -> str:
    try:
        d = datetime.fromisoformat(str(date_str)[:10]).date()
        return d.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return str(date_str)


def _gl_payee_description(payee: str, description: str) -> str:
    p, d = (payee or "").strip(), (description or "").strip()
    if p and d:
        return f"{p} — {d}"
    return p or d or "—"


def _gl_filter_visible_blocks(blocks: list[dict]) -> list[dict]:
    """Keep only COAs with beginning balance or period lines (used when a single bank book is selected)."""
    out = []
    for b in blocks:
        beg = float(b.get("beginning_balance") or 0)
        lines = b.get("lines") or []
        if abs(beg) > 1e-9 or len(lines) > 0:
            out.append(b)
    return out


def _gl_rows_with_opening(block: dict, period_start: date) -> list[dict]:
    """Detail rows: opening balance at start of period, then period transactions."""
    beg = float(block.get("beginning_balance") or 0)
    lines = list(block.get("lines") or [])
    opening = {
        "date": period_start.isoformat(),
        "payee": "",
        "description": "Opening balance",
        "debit": None,
        "credit": None,
        "balance": beg,
        "is_opening": True,
    }
    return [opening] + lines


def _gl_report_to_csv(blocks: list[dict], period_start: date) -> str:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["Account #", "Account name", "Type", "Date", "Payee / description", "Debit", "Credit", "Running"]
    )
    for b in blocks:
        num = b.get("coa_number") or ""
        name = b.get("coa_name") or ""
        typ = _gl_account_type_banner(b.get("coa_type") or "")
        for ln in _gl_rows_with_opening(b, period_start):
            ds = ln.get("date") or ""
            if ln.get("is_opening"):
                pd = "Opening balance"
            else:
                pd = _gl_payee_description(ln.get("payee") or "", ln.get("description") or "")
            deb = ln.get("debit")
            crd = ln.get("credit")
            w.writerow(
                [
                    num,
                    name,
                    typ,
                    ds,
                    pd,
                    f"{deb:.2f}" if deb else "",
                    f"{crd:.2f}" if crd else "",
                    f"{float(ln.get('balance') or 0):.2f}",
                ]
            )
    return buf.getvalue()


def reports_proration_factor(period_start, period_end):
    """Share of FY 2024 overlapping the selected range (for demo P&L scaling)."""
    period_start, period_end = _normalize_period(period_start, period_end)
    fy_s, fy_e = REPORTS_FISCAL_YEAR_START, REPORTS_FISCAL_YEAR_END
    fy_days = (fy_e - fy_s).days + 1
    ov_s = max(period_start, fy_s)
    ov_e = min(period_end, fy_e)
    if ov_s > ov_e:
        return 0.0, 0
    overlap_days = (ov_e - ov_s).days + 1
    return overlap_days / fy_days, overlap_days


def format_period_header(d0, d1):
    d0, d1 = _normalize_period(d0, d1)
    return f"{d0.strftime('%b %d, %Y')} – {d1.strftime('%b %d, %Y')}"


def quarterly_rows_for_period(period_start, period_end):
    out = []
    for q in QUARTERLY_PERFORMANCE:
        ps, pe = q["period_start"], q["period_end"]
        if ps <= period_end and pe >= period_start:
            out.append(q)
    return out


def scale_amount(x, factor):
    if x is None:
        return None
    return round(x * factor, 2)


def filter_detail_lines(account_number, period_start, period_end):
    period_start, period_end = _normalize_period(period_start, period_end)
    rows = [
        r for r in SAMPLE_ACCOUNT_DETAIL
        if r["account_number"] == account_number
        and period_start <= r["date"] <= period_end
    ]
    return sorted(rows, key=lambda r: r["date"])


def render_account_drilldown(period_start, period_end, key_prefix, title="Account activity"):
    nums = sorted({a["number"] for a in CHART_OF_ACCOUNTS}, key=lambda x: int(x))
    labels = ["— Select account # —"] + [f"{n} — {next(a['name'] for a in CHART_OF_ACCOUNTS if a['number'] == n)}" for n in nums]
    choice = st.selectbox(title, labels, key=f"{key_prefix}_acct")
    if choice == labels[0]:
        return
    acct_num = choice.split(" — ", 1)[0].strip()
    lines = filter_detail_lines(acct_num, period_start, period_end)
    if not lines:
        st.caption("No sample detail lines in this period for this account.")
        return
    df = pd.DataFrame(
        {
            "Date": [r["date"].strftime("%Y-%m-%d") for r in lines],
            "Payee": [r["payee"] for r in lines],
            "Memo": [r["memo"] for r in lines],
            "Debit": [r["debit"] for r in lines],
            "Credit": [r["credit"] for r in lines],
        }
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

st.set_page_config(
    page_title="Reports | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("reports")
render_topbar("Search data...")

if not db_ready():
    st.stop()

BANK_ACCOUNTS = bank_accounts()
CHART_OF_ACCOUNTS = chart_of_accounts()
TRIAL_BALANCE_REPORT = trial_balance_report()

st.html("<div style='height:0.75rem'></div>")

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
# TAB 3: General Ledger (layout per GLReport_screen.png; uses app sidebar, not mock sidebar)
# ────────────────────────────────────────────────────────────────────────────────
with tab_gl:
    if "gl_report_snapshot" not in st.session_state:
        st.session_state.gl_report_snapshot = None

    st.html("""
    <div style="margin-bottom:1.75rem;">
        <p style="font-size:0.65rem;font-weight:700;letter-spacing:0.15em;color:#154212;
                  margin:0 0 0.35rem 0;text-transform:uppercase;">Reports</p>
        <h1 style="font-family:'Manrope',sans-serif;font-size:2.25rem;font-weight:800;
                   letter-spacing:-0.03em;margin:0 0 0.35rem 0;color:#1a1c1c;">
            General Ledger Report
        </h1>
        <p style="font-family:'Manrope',sans-serif;font-size:1rem;font-weight:600;
                  color:#2d5a27;margin:0 0 0.5rem 0;">
            Moth and Money Ledger For Creatives
        </p>
        <p style="font-size:0.9rem;color:#636262;margin:0;max-width:42rem;line-height:1.5;">
            A clear, period view of chart-of-accounts activity: beginning balance, each line, and ending balance.
            Net balance uses debit minus credit. Account filters use lexicographic order—zero-pad numbers when needed.
        </p>
    </div>
    """)

    st.caption(
        "Set the GL period with **START DATE** and **END DATE**, filter by bank book or chart account range "
        "(optional expander), then **GENERATE REPORT**."
    )
    if use_sample_data():
        st.info(
            "Demo mode uses sample transactions dated **2024**. A 2025 or 2026 range may show no lines until you "
            "set **USE_SAMPLE_DATA=false** and load real data in PostgreSQL."
        )

    gl_account_options = ["All Accounts"] + [
        f"{a['account_name']} ****{a['masked']}"
        for a in BANK_ACCOUNTS
        if a["account_type"] != "cash"
    ]

    with st.form("gl_report_form"):
        f1, f2, f3, f4 = st.columns([1.1, 1.1, 2.2, 1], gap="medium")
        with f1:
            gl_d0 = st.date_input(
                "START DATE",
                value=REPORTS_FISCAL_YEAR_START,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="gl_form_start",
            )
        with f2:
            gl_d1 = st.date_input(
                "END DATE",
                value=REPORTS_FISCAL_YEAR_END,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="gl_form_end",
            )
        with f3:
            gl_bank_pick = st.selectbox(
                "ACCOUNT FILTER",
                options=gl_account_options,
                key="gl_form_bank",
            )
        with f4:
            st.html("<div style='height:0.25rem'></div>")
            gl_submit = st.form_submit_button("GENERATE REPORT", type="primary", use_container_width=True)

        with st.expander("Advanced: chart account number range (optional)", expanded=False):
            a1, a2 = st.columns(2)
            with a1:
                gl_coa_from = st.text_input(
                    "Account # from",
                    placeholder="e.g. 4000",
                    key="gl_form_coa_from",
                )
            with a2:
                gl_coa_to = st.text_input(
                    "Account # to",
                    placeholder="e.g. 4999",
                    key="gl_form_coa_to",
                )

    if gl_submit:
        gl_start, gl_end = _normalize_period(gl_d0, gl_d1)
        gl_bid = _bank_id_for_report_label(gl_bank_pick, BANK_ACCOUNTS)
        cf = (gl_coa_from or "").strip() or None
        ct = (gl_coa_to or "").strip() or None
        raw_rows = general_ledger_report(gl_start, gl_end, cf, ct, gl_bid)
        if gl_bank_pick == "All Accounts":
            visible = raw_rows
        else:
            visible = _gl_filter_visible_blocks(raw_rows)
        st.session_state.gl_report_snapshot = {
            "rows": visible,
            "period_start": gl_start,
            "period_end": gl_end,
            "bank_label": gl_bank_pick,
        }

    snap = st.session_state.gl_report_snapshot

    if not CHART_OF_ACCOUNTS:
        st.info(
            "No chart of accounts yet. Complete onboarding or add accounts under **New entry**."
        )
    elif snap is None:
        st.caption("Choose dates and account scope, then click **GENERATE REPORT**.")
    elif not snap["rows"]:
        st.info(
            "No activity in this period for the selected filters. Try a wider date range or **All Accounts**."
        )
    else:
        dl_col, _, dl_btn = st.columns([1, 4, 1])
        with dl_btn:
            csv_data = _gl_report_to_csv(snap["rows"], snap["period_start"])
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name="general_ledger_report.csv",
                mime="text/csv",
                key="gl_download_csv",
                type="primary",
                use_container_width=True,
            )

        ps, pe = snap["period_start"], snap["period_end"]
        ps_s = ps.strftime("%b %d, %Y")
        pe_s = pe.strftime("%b %d, %Y")
        ps_h = html.escape(ps_s)
        pe_h = html.escape(pe_s)
        st.caption(
            f"Report range: beginning date {ps_s}, ending date {pe_s}. Bank scope: {snap['bank_label']}. "
            "Beginning balance (PostgreSQL) = trial balance lines for this chart account (same as Reports ▸ "
            "Trial Balance: pending and confirmed; debit minus credit; all books when **All Accounts**) plus "
            "posted transactions (pending/cleared/flagged) with dates before the beginning date. "
            "Period activity includes every transaction from the beginning date through the ending date, inclusive. "
            "Ending balance equals beginning balance plus debits minus credits for that range. "
            "Do not duplicate the same opening in trial balance and as dated transactions."
        )

        for block in snap["rows"]:
            num = html.escape(str(block.get("coa_number") or ""))
            name = html.escape(str(block.get("coa_name") or ""))
            typ = _gl_account_type_banner(block.get("coa_type") or "")
            beg = float(block.get("beginning_balance") or 0)
            end = float(block.get("ending_balance") or 0)
            disp_lines = _gl_rows_with_opening(block, ps)

            st.html(f"""
            <div style="margin-top:2rem;padding-top:1.5rem;border-top:1px solid rgba(194,201,187,0.25);">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1.5rem;
                            flex-wrap:wrap;">
                    <div>
                        <div style="font-family:'Manrope',sans-serif;font-size:1.2rem;font-weight:700;
                                    color:#1a1c1c;">
                            <span style="font-family:'Courier New',monospace;font-size:1rem;color:#154212;">
                                {num}
                            </span>
                            <span style="margin-left:0.5rem;">— {name}</span>
                        </div>
                        <div style="margin-top:0.35rem;font-size:0.75rem;color:#636262;line-height:1.4;">
                            Period: <strong>{ps_h}</strong> through <strong>{pe_h}</strong>
                        </div>
                        <div style="margin-top:0.4rem;font-size:0.62rem;font-weight:700;letter-spacing:0.14em;
                                    color:#636262;">{html.escape(typ)}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.12em;color:#636262;">
                            BEGINNING BALANCE
                        </div>
                        <div style="font-size:0.7rem;color:#636262;margin-top:0.15rem;">As of {ps_h}</div>
                        <div style="font-family:'Manrope',sans-serif;font-size:1.15rem;font-weight:700;
                                    color:#1a1c1c;margin-top:0.2rem;">${beg:,.2f}</div>
                    </div>
                </div>
            </div>
            """)

            thead = """
                <thead>
                    <tr>
                        <th style="text-align:left;padding:0.75rem 0.5rem 0.75rem 0;font-size:0.62rem;
                                   font-weight:700;letter-spacing:0.12em;color:#636262;">DATE</th>
                        <th style="text-align:left;padding:0.75rem 0.5rem;font-size:0.62rem;font-weight:700;
                                   letter-spacing:0.12em;color:#636262;">PAYEE / DESCRIPTION</th>
                        <th style="text-align:right;padding:0.75rem 0.5rem;font-size:0.62rem;font-weight:700;
                                   letter-spacing:0.12em;color:#636262;">DEBITS</th>
                        <th style="text-align:right;padding:0.75rem 0.5rem;font-size:0.62rem;font-weight:700;
                                   letter-spacing:0.12em;color:#636262;">CREDITS</th>
                        <th style="text-align:right;padding:0.75rem 0 0.75rem 0.5rem;font-size:0.62rem;
                                   font-weight:700;letter-spacing:0.12em;color:#636262;">RUNNING</th>
                    </tr>
                </thead>
                """
            rows_html = ""
            for ln in disp_lines:
                is_open = bool(ln.get("is_opening"))
                if is_open:
                    ds = ps.strftime("%b %d, %Y")
                    pd = html.escape("Opening balance")
                    row_bg = "background:rgba(21,66,18,0.06);"
                else:
                    ds = _gl_format_line_date(str(ln.get("date") or ""))
                    pd = html.escape(_gl_payee_description(ln.get("payee") or "", ln.get("description") or ""))
                    row_bg = ""
                deb = ln.get("debit")
                crd = ln.get("credit")
                bal = float(ln.get("balance") or 0)
                deb_s = (
                    f'<span style="font-weight:700;color:#154212;">${deb:,.2f}</span>'
                    if deb
                    else '<span style="color:#636262;">—</span>'
                )
                crd_s = (
                    f'<span style="font-weight:700;color:#71151d;">${crd:,.2f}</span>'
                    if crd
                    else '<span style="color:#636262;">—</span>'
                )
                rows_html += f"""
                    <tr style="{row_bg}">
                        <td style="padding:0.85rem 0.5rem 0.85rem 0;font-size:0.875rem;color:#1a1c1c;
                                   vertical-align:top;">{html.escape(ds)}</td>
                        <td style="padding:0.85rem 0.5rem;font-size:0.875rem;color:#1a1c1c;vertical-align:top;
                                   font-style:{'italic' if is_open else 'normal'};">{pd}</td>
                        <td style="padding:0.85rem 0.5rem;text-align:right;vertical-align:top;">{deb_s}</td>
                        <td style="padding:0.85rem 0.5rem;text-align:right;vertical-align:top;">{crd_s}</td>
                        <td style="padding:0.85rem 0 0.85rem 0.5rem;text-align:right;font-size:0.875rem;
                                   font-weight:600;color:#1a1c1c;vertical-align:top;">${bal:,.2f}</td>
                    </tr>
                    """
            st.html(f"""
                <div style="overflow-x:auto;margin-top:0.75rem;">
                    <table style="width:100%;border-collapse:collapse;font-family:'Inter',sans-serif;">
                        {thead}
                        <tbody>{rows_html}</tbody>
                    </table>
                </div>
                """)

            st.html(f"""
            <div style="display:flex;justify-content:flex-end;margin-top:0.75rem;padding-top:0.75rem;">
                <div style="text-align:right;">
                    <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.12em;color:#636262;">
                        ENDING BALANCE
                    </div>
                    <div style="font-size:0.7rem;color:#636262;margin-top:0.15rem;">As of {pe_h}</div>
                    <div style="font-family:'Manrope',sans-serif;font-size:1.05rem;font-weight:700;
                                color:#154212;margin-top:0.2rem;">${end:,.2f}</div>
                </div>
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
            <td style="padding:1rem;font-size:0.8rem;color:#636262;">{row['coa']}</td>
            <td style="padding:1rem;text-align:right;font-size:0.875rem;">{deb_str}</td>
            <td style="padding:1rem;text-align:right;font-size:0.875rem;">{crd_str}</td>
        </tr>
        <tr><td colspan="3" style="height:0.25rem;background:transparent;"></td></tr>"""

    st.html(f"""
    <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:separate;border-spacing:0 0.25rem;">
            <thead>
                <tr>
                    <th style="padding:0.75rem 1rem;text-align:left;font-size:0.65rem;
                               font-weight:700;text-transform:uppercase;letter-spacing:0.1em;
                               color:#636262;">Chart of accounts</th>
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

