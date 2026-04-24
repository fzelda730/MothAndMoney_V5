import csv
import html
import sys
from io import StringIO
from pathlib import Path
from datetime import date, datetime

import streamlit as st
from typing import Any, Optional
from uuid import UUID

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.sample_data import SAMPLE_ACCOUNT_DETAIL
from data.providers import (
    balance_sheet_report,
    bank_accounts,
    chart_of_accounts,
    coa_activity_report,
    db_ready,
    general_ledger_report,
    journal_entries_report,
    personal_spending_report,
    profit_loss_report,
    trial_balance_gl_report,
)
from db.connection import use_sample_data


def _bank_id_for_report_label(label: str, accounts: list[Any]) -> Optional[str]:
    if label == "All Accounts":
        return None
    for a in accounts:
        if f"{a['account_name']} ****{a['masked']}" == label:
            return a["id"]
    return None


def _journal_book_id_for_report_label(label: str, journal_accounts: list[Any]) -> Optional[str]:
    if label == "All journal books":
        return None
    for a in journal_accounts:
        if f"{a['account_name']} ****{a['masked']}" == label:
            return a["id"]
    return None


def _normalize_period(d0, d1):
    if d0 > d1:
        return d1, d0
    return d0, d1


def _coa_number_from_gl_range_label(label: str) -> Optional[str]:
    """Map General Ledger range dropdown label to account number, or None for sentinels."""
    s = (label or "").strip()
    if not s or s.startswith("—"):
        return None
    return s.split(" — ", 1)[0].strip() or None


def _default_report_period() -> tuple[date, date]:
    """Jan 1–Dec 31 of the current calendar year (Reports date picker defaults)."""
    y = date.today().year
    return date(y, 1, 1), date(y, 12, 31)


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


def _journal_entries_report_csv(entries: list[dict[str, Any]]) -> str:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "Entry date",
            "Journal book",
            "Reference",
            "Memo",
            "Posting group id",
            "Account #",
            "Account name",
            "Debit",
            "Credit",
            "Entry total debit",
            "Entry total credit",
        ]
    )
    for e in entries:
        ed = e.get("entry_date")
        ds = ed.isoformat() if hasattr(ed, "isoformat") else str(ed or "")
        jbn = e.get("journal_book_name") or ""
        ref = e.get("reference") or ""
        memo = (e.get("memo") or "") or ""
        gid = e.get("posting_group_id") or ""
        td = float(e.get("total_debit") or 0)
        tc = float(e.get("total_credit") or 0)
        lines = e.get("lines") or []
        for i, ln in enumerate(lines):
            w.writerow(
                [
                    ds if i == 0 else "",
                    jbn if i == 0 else "",
                    ref if i == 0 else "",
                    memo if i == 0 else "",
                    gid if i == 0 else "",
                    ln.get("coa_number") or "",
                    ln.get("coa_name") or "",
                    f"{float(ln.get('debit') or 0):.2f}",
                    f"{float(ln.get('credit') or 0):.2f}",
                    f"{td:.2f}" if i == 0 else "",
                    f"{tc:.2f}" if i == 0 else "",
                ]
            )
    return buf.getvalue()


def _journal_lines_display_rows(lines: Any) -> list[dict[str, Any]]:
    """Build plain float/str rows for st.dataframe (Arrow-safe; skips bad line dicts)."""
    out: list[dict[str, Any]] = []
    if not isinstance(lines, (list, tuple)):
        return out
    for ln in lines:
        if not isinstance(ln, dict):
            continue
        num = str(ln.get("coa_number") or "").strip()
        name = str(ln.get("coa_name") or "").strip()
        if num and name:
            acct = f"{num} — {name}"
        elif num or name:
            acct = num or name
        else:
            acct = "—"
        try:
            deb = float(ln.get("debit") or 0)
        except (TypeError, ValueError):
            deb = 0.0
        try:
            crd = float(ln.get("credit") or 0)
        except (TypeError, ValueError):
            crd = 0.0
        out.append({"Account": acct, "Debit": deb, "Credit": crd})
    return out


def _pl_report_csv(data: dict[str, Any]) -> str:
    """CSV for Profit & Loss snapshot (income and expense sections)."""
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "Section",
            "Account #",
            "Account name",
            "Period debit",
            "Period credit",
            "Net (revenue or expense)",
        ]
    )
    for row in data.get("income", []):
        w.writerow(
            [
                "Income",
                row.get("coa_number") or "",
                row.get("coa_name") or "",
                f"{float(row.get('period_debit') or 0):.2f}",
                f"{float(row.get('period_credit') or 0):.2f}",
                f"{float(row.get('amount_display') or 0):.2f}",
            ]
        )
    for row in data.get("expenses", []):
        w.writerow(
            [
                "Expense",
                row.get("coa_number") or "",
                row.get("coa_name") or "",
                f"{float(row.get('period_debit') or 0):.2f}",
                f"{float(row.get('period_credit') or 0):.2f}",
                f"{float(row.get('amount_display') or 0):.2f}",
            ]
        )
    tot = data.get("totals") or {}
    w.writerow(
        [
            "Totals",
            "",
            "Total income",
            "",
            "",
            f"{float(tot.get('total_income') or 0):.2f}",
        ]
    )
    w.writerow(
        [
            "",
            "",
            "Total expenses",
            "",
            "",
            f"{float(tot.get('total_expenses') or 0):.2f}",
        ]
    )
    w.writerow(
        [
            "",
            "",
            "Net income",
            "",
            "",
            f"{float(tot.get('net_income') or 0):.2f}",
        ]
    )
    return buf.getvalue()


def _tb_report_csv(data: dict[str, Any]) -> str:
    """CSV for GL-based trial balance snapshot."""
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["Account #", "Account name", "Type", "Debit", "Credit"])
    for r in data.get("rows", []):
        w.writerow(
            [
                r.get("coa_number") or "",
                r.get("coa_name") or "",
                r.get("coa_type") or "",
                f"{float(r.get('debits') or 0):.2f}",
                f"{float(r.get('credits') or 0):.2f}",
            ]
        )
    tot = data.get("totals") or {}
    w.writerow(
        [
            "",
            "",
            "Totals",
            f"{float(tot.get('total_debits') or 0):.2f}",
            f"{float(tot.get('total_credits') or 0):.2f}",
        ]
    )
    w.writerow(
        [
            "",
            "",
            "Variance (debits − credits)",
            f"{float(tot.get('variance') or 0):.2f}",
            "",
        ]
    )
    return buf.getvalue()


def _personal_spending_summary_csv(data: dict[str, Any]) -> str:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["Account #", "Account name", "Net (debit − credit)", "Percent of total"])
    gt = float(data.get("grand_total") or 0)
    for row in data.get("categories", []):
        w.writerow(
            [
                row.get("coa_number") or "",
                row.get("coa_name") or "",
                f"{float(row.get('net') or 0):.2f}",
                f"{float(row.get('pct') or 0):.2f}%",
            ]
        )
    w.writerow(["", "Total", f"{gt:.2f}", "100.00%" if abs(gt) > 1e-9 else "—"])
    return buf.getvalue()


def _personal_spending_detail_csv(data: dict[str, Any]) -> str:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "Date",
            "Account #",
            "Account name",
            "Payee",
            "Description",
            "Debit",
            "Credit",
            "Net",
        ]
    )
    for row in data.get("detail", []):
        deb = row.get("debit")
        crd = row.get("credit")
        w.writerow(
            [
                str(row.get("date") or "")[:10],
                row.get("coa_number") or "",
                row.get("coa_name") or "",
                row.get("payee") or "",
                row.get("description") or "",
                f"{float(deb):.2f}" if deb else "",
                f"{float(crd):.2f}" if crd else "",
                f"{float(row.get('net') or 0):.2f}",
            ]
        )
    return buf.getvalue()


def _personal_spending_monthly_csv(data: dict[str, Any]) -> str:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["Month", "Account #", "Net"])
    for block in data.get("by_month", []):
        label = block.get("label") or block.get("month_key") or ""
        for num, amt in sorted((block.get("by_coa") or {}).items()):
            w.writerow([label, num, f"{float(amt):.2f}"])
        w.writerow([label, "— month total —", f"{float(block.get('total') or 0):.2f}"])
    return buf.getvalue()


def reports_proration_factor(period_start, period_end):
    """Share of the calendar year of period_start overlapping the selected range (demo P&L scaling)."""
    period_start, period_end = _normalize_period(period_start, period_end)
    y = period_start.year
    fy_s, fy_e = date(y, 1, 1), date(y, 12, 31)
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


def _render_reports_back_to_top() -> None:
    """Scroll the Reports view to the top. Uses iframe document + scrollIntoView; extend selectors if Streamlit DOM changes."""
    st.html("""
<div style="display:flex;justify-content:center;margin-top:2rem;margin-bottom:0.5rem;">
<button type="button"
        onclick="(function(){var d=document;var t=d.getElementById('reports-page-top');if(t){t.scrollIntoView({behavior:'smooth',block:'start'});}var q=['[data-testid=&quot;stAppViewContainer&quot;]','[data-testid=&quot;stMain&quot;]','section.main','.main'];for(var i=0;i&lt;q.length;i++){var e=d.querySelector(q[i]);if(e){try{e.scrollTo({top:0,behavior:'smooth'});}catch(x){e.scrollTop=0;}break;}}var se=d.scrollingElement;if(se){try{se.scrollTo({top:0,behavior:'smooth'});}catch(x){se.scrollTop=0;}}try{d.documentElement.scrollTo({top:0,behavior:'smooth'});}catch(x){}try{window.scrollTo({top:0,behavior:'smooth'});}catch(x){}try{if(window.parent!==window){window.parent.scrollTo({top:0,behavior:'smooth'});}}catch(x){}})();"
        style="font-family:'Manrope',sans-serif;font-size:0.875rem;font-weight:600;
               color:#154212;background:#ffffff;border:1px solid rgba(21,66,18,0.35);
               border-radius:0.5rem;padding:0.5rem 1.25rem;cursor:pointer;
               display:inline-flex;align-items:center;gap:0.35rem;">
    <span class="material-symbols-outlined" style="font-size:1.1rem;">vertical_align_top</span>
    Back to top
</button>
</div>
""")


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

st.html("<div id='reports-page-top'></div>")
st.html("<div style='height:0.75rem'></div>")

# `st.tabs` does not keep the active tab on rerun; a keyed selectbox does (e.g. after Generate report).
_REPORT_CHOICES: tuple[str, ...] = (
    "Profit and Loss",
    "Balance Sheet",
    "General Ledger",
    "Activity",
    "Trial Balance",
    "Journal entries",
    "Personal spending",
)
c1, c2 = st.columns([1, 4], gap="medium")
with c1:
    st.caption("**Report**")
with c2:
    st.selectbox(
        "Report",
        options=list(_REPORT_CHOICES),
        key="reports_nav_tab",
        label_visibility="collapsed",
    )
_report_sel: str = st.session_state.get("reports_nav_tab") or _REPORT_CHOICES[0]

# ── Report sections (one selected via `reports_nav_tab` selectbox) ────────────

# ────────────────────────────────────────────────────────────────────────────────
# TAB 1: Profit and Loss (from GL: income & expense COAs, period activity)
# ────────────────────────────────────────────────────────────────────────────────
if _report_sel == "Profit and Loss":
    if "pl_report_snapshot" not in st.session_state:
        st.session_state.pl_report_snapshot = None

    pl_account_options = ["All Accounts"] + [
        f"{a['account_name']} ****{a['masked']}"
        for a in BANK_ACCOUNTS
        if a["account_type"] != "cash"
    ]

    st.html("""
    <p style="color:#154212;font-size:0.65rem;font-weight:700;text-transform:uppercase;
              letter-spacing:0.15em;margin-bottom:0.5rem;">Financial Statement</p>
    <h2 style="font-family:'Manrope',sans-serif;font-size:2.5rem;font-weight:800;
               letter-spacing:-0.03em;margin:0 0 0.5rem;">Profit and Loss</h2>
    <p style="color:#636262;font-style:italic;margin-bottom:1rem;">
        Period activity from the General Ledger: revenue (credit − debit) and expenses (debit − credit)
        for each income and expense chart account.
    </p>
    """)

    with st.form("pl_report_form"):
        pl_def_s, pl_def_e = _default_report_period()
        pf1, pf2, pf3, pf4 = st.columns([1.1, 1.1, 2.2, 1], gap="medium")
        with pf1:
            pl_d0 = st.date_input(
                "FROM DATE",
                value=pl_def_s,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="pl_form_start",
            )
        with pf2:
            pl_d1 = st.date_input(
                "TO DATE",
                value=pl_def_e,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="pl_form_end",
            )
        with pf3:
            pl_bank_pick = st.selectbox(
                "ACCOUNT FILTER",
                options=pl_account_options,
                key="pl_form_bank",
            )
        with pf4:
            st.html("<div style='height:0.25rem'></div>")
            pl_submit = st.form_submit_button(
                "GENERATE REPORT", type="primary", use_container_width=True
            )

    if use_sample_data():
        st.info(
            "Demo mode uses sample transactions dated **2024**. Pick a 2024 range or set "
            "**USE_SAMPLE_DATA=false** for PostgreSQL."
        )

    if pl_submit:
        pl_start, pl_end = _normalize_period(pl_d0, pl_d1)
        pl_bid = _bank_id_for_report_label(pl_bank_pick, BANK_ACCOUNTS)
        snap = profit_loss_report(pl_start, pl_end, pl_bid)
        st.session_state.pl_report_snapshot = {
            "data": snap,
            "period_start": pl_start,
            "period_end": pl_end,
            "bank_label": pl_bank_pick,
        }

    pl_snap = st.session_state.pl_report_snapshot

    rev = exp = net = 0.0
    if pl_snap:
        tot = pl_snap["data"]["totals"]
        rev = float(tot["total_income"])
        exp = float(tot["total_expenses"])
        net = float(tot["net_income"])

    net_label = "Net Profit" if net >= 0 else "Net Loss"
    net_note = (
        "Income and expense accounts only; asset/liability/equity use Balance Sheet."
        if pl_snap
        else "Generate a report to see totals."
    )

    if not CHART_OF_ACCOUNTS:
        st.info(
            "No chart of accounts yet. Complete onboarding or add accounts under **New entry**."
        )
    elif pl_snap is None:
        st.caption(
            "Choose **from** and **to** dates and account scope, then click **GENERATE REPORT**. "
            "Amounts are period activity (not point-in-time balances)."
        )
    else:
        ps, pe = pl_snap["period_start"], pl_snap["period_end"]
        ph = html.escape(format_period_header(ps, pe))
        bl = html.escape(str(pl_snap["bank_label"]))
        gen_on = html.escape(date.today().strftime("%b %d, %Y"))

        col_dl, col_spacer = st.columns([1, 4])
        with col_dl:
            csv_bytes = _pl_report_csv(pl_snap["data"])
            st.download_button(
                label="Download CSV",
                data=csv_bytes,
                file_name="profit_and_loss_report.csv",
                mime="text/csv",
                key="pl_download_csv",
                type="primary",
                use_container_width=True,
            )

        st.markdown(f"**Period:** {ph}  \n**Bank scope:** {bl}")

        st.caption(
            "Per-account **Debit** and **Credit** are totals for the period only. "
            "**Net** for income is credit − debit; for expenses, debit − credit."
        )

        col_stats, col_table = st.columns([2, 3], gap="large")

        with col_stats:
            net_bg = (
                "linear-gradient(135deg,#2d5a27 0%,#154212 100%)"
                if net >= 0
                else "linear-gradient(135deg,#5c2a2a 0%,#71151d 100%)"
            )
            st.html(f"""
            <div class="mm-report-stat-card" style="margin-bottom:1.5rem;">
                <span class="mm-stat-label">Total Revenue</span>
                <div>
                    <div style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:700;
                                color:#154212;">${rev:,.2f}</div>
                </div>
            </div>
            <div class="mm-card-low" style="margin-bottom:1.5rem;min-height:8rem;
                                             display:flex;flex-direction:column;
                                             justify-content:space-between;">
                <span class="mm-stat-label">Total Expenses</span>
                <div>
                    <div style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:700;">
                        ${exp:,.2f}</div>
                </div>
            </div>
            <div class="mm-report-net-card" style="background:{net_bg};">
                <div style="position:relative;z-index:1;">
                    <span class="mm-stat-label" style="color:rgba(255,255,255,0.85);">
                        {html.escape(net_label)}</span>
                    <div style="font-family:'Manrope',sans-serif;font-size:2.5rem;font-weight:800;
                                color:#ffffff;margin-top:1rem;">${abs(net):,.2f}</div>
                </div>
                <div style="background:rgba(0,0,0,0.15);backdrop-filter:blur(8px);
                            border-radius:0.5rem;padding:1rem;position:relative;z-index:1;">
                    <p style="font-size:0.75rem;font-style:italic;opacity:0.95;color:#ffffff;
                               margin:0;">{html.escape(net_note)}</p>
                </div>
                <div style="position:absolute;right:-3rem;bottom:-3rem;width:12rem;height:12rem;
                            background:rgba(255,255,255,0.08);border-radius:50%;
                            filter:blur(40px);"></div>
            </div>
            """)

        def _pl_row_html(r: dict) -> str:
            num = html.escape(str(r.get("coa_number") or ""))
            name = html.escape(str(r.get("coa_name") or ""))
            label = f"{num} — {name}" if num else name
            pd = float(r.get("period_debit") or 0)
            pc = float(r.get("period_credit") or 0)
            am = float(r.get("amount_display") or 0)
            ds = f"${pd:,.2f}" if abs(pd) > 1e-9 else "—"
            cs = f"${pc:,.2f}" if abs(pc) > 1e-9 else "—"
            return f"""
                <tr>
                    <td style="padding:1.25rem 0;border-bottom:1px solid rgba(194,201,187,0.1);
                               font-weight:500;">{label}</td>
                    <td style="padding:1.25rem 0;text-align:right;color:#636262;
                               border-bottom:1px solid rgba(194,201,187,0.1);">{ds}</td>
                    <td style="padding:1.25rem 0;text-align:right;
                               border-bottom:1px solid rgba(194,201,187,0.1);">{cs}</td>
                    <td style="padding:1.25rem 0;text-align:right;font-weight:600;
                               border-bottom:1px solid rgba(194,201,187,0.1);">
                        ${am:,.2f}</td>
                </tr>"""

        with col_table:
            pdata = pl_snap["data"]
            income_rows = pdata["income"]
            expense_rows = pdata["expenses"]
            total_income = float(pdata["totals"]["total_income"])
            total_expenses = float(pdata["totals"]["total_expenses"])

            inc_html = "".join(_pl_row_html(r) for r in income_rows)
            inc_html += f"""
            <tr style="background:rgba(238,238,238,0.3);">
                <td style="padding:1.5rem 0;font-weight:700;">Total Revenue</td>
                <td style="padding:1.5rem 0;text-align:right;color:#636262;">—</td>
                <td style="padding:1.5rem 0;text-align:right;color:#636262;">—</td>
                <td style="padding:1.5rem 0;text-align:right;font-weight:700;color:#154212;">
                    ${total_income:,.2f}</td>
            </tr>"""

            st.html(f"""
            <div class="mm-report-table">
                <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1.1rem;
                           margin-bottom:1.5rem;">Income</h4>
                <table style="width:100%;border-collapse:collapse;font-size:0.875rem;">
                    <thead>
                        <tr>
                            <th style="text-align:left;padding:0.5rem 0;font-size:0.62rem;font-weight:700;
                                       letter-spacing:0.1em;color:#636262;">ACCOUNT</th>
                            <th style="text-align:right;padding:0.5rem 0.5rem;font-size:0.62rem;font-weight:700;
                                       letter-spacing:0.1em;color:#636262;">DEBIT</th>
                            <th style="text-align:right;padding:0.5rem 0.5rem;font-size:0.62rem;font-weight:700;
                                       letter-spacing:0.1em;color:#636262;">CREDIT</th>
                            <th style="text-align:right;padding:0.5rem 0;font-size:0.62rem;font-weight:700;
                                       letter-spacing:0.1em;color:#636262;">NET</th>
                        </tr>
                    </thead>
                    <tbody>{inc_html}</tbody>
                </table>
            </div>
            """)

            exp_html = "".join(_pl_row_html(r) for r in expense_rows)
            exp_html += f"""
            <tr style="background:rgba(238,238,238,0.3);">
                <td style="padding:1.5rem 0;font-weight:700;">Total Expenses</td>
                <td style="padding:1.5rem 0;text-align:right;color:#636262;">—</td>
                <td style="padding:1.5rem 0;text-align:right;color:#636262;">—</td>
                <td style="padding:1.5rem 0;text-align:right;font-weight:700;">
                    ${total_expenses:,.2f}</td>
            </tr>"""

            st.html(f"""
            <div class="mm-report-table" style="margin-top:2.5rem;">
                <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1.1rem;
                           margin-bottom:1.5rem;">Expenses</h4>
                <table style="width:100%;border-collapse:collapse;font-size:0.875rem;">
                    <thead>
                        <tr>
                            <th style="text-align:left;padding:0.5rem 0;font-size:0.62rem;font-weight:700;
                                       letter-spacing:0.1em;color:#636262;">ACCOUNT</th>
                            <th style="text-align:right;padding:0.5rem 0.5rem;font-size:0.62rem;font-weight:700;
                                       letter-spacing:0.1em;color:#636262;">DEBIT</th>
                            <th style="text-align:right;padding:0.5rem 0.5rem;font-size:0.62rem;font-weight:700;
                                       letter-spacing:0.1em;color:#636262;">CREDIT</th>
                            <th style="text-align:right;padding:0.5rem 0;font-size:0.62rem;font-weight:700;
                                       letter-spacing:0.1em;color:#636262;">NET</th>
                        </tr>
                    </thead>
                    <tbody>{exp_html}</tbody>
                </table>
            </div>
            """)

            net_ord = net
            net_color2 = "#154212" if net_ord >= 0 else "#71151d"
            st.html(f"""
            <div class="mm-report-table" style="margin-top:2.5rem;">
                <div style="margin-top:1rem;padding-top:1.5rem;
                            border-top:1px solid rgba(194,201,187,0.2);
                            display:flex;justify-content:space-between;align-items:flex-end;">
                    <div>
                        <p style="font-size:0.6rem;font-weight:700;text-transform:uppercase;
                                   letter-spacing:0.15em;color:#636262;margin-bottom:0.25rem;">
                            Generated</p>
                        <p style="font-size:0.8rem;font-weight:500;">{gen_on}</p>
                    </div>
                    <div style="text-align:right;">
                        <p style="font-size:0.6rem;font-weight:700;text-transform:uppercase;
                                   letter-spacing:0.15em;color:#636262;margin-bottom:0.25rem;">
                            Net Ordinary Income</p>
                        <p style="font-family:'Manrope',sans-serif;font-size:1.5rem;font-weight:700;
                                   color:{net_color2};">${net_ord:,.2f}</p>
                    </div>
                </div>
            </div>
            """)

            if not income_rows and not expense_rows:
                st.info(
                    "No income or expense accounts with activity in this range. "
                    "Try a wider period or **All Accounts**."
                )

    st.html("<div style='height:2rem'></div>")
    _render_reports_back_to_top()


# ────────────────────────────────────────────────────────────────────────────────
# TAB 2: Balance Sheet (from GL / chart: asset, liability, equity)
# ────────────────────────────────────────────────────────────────────────────────
if _report_sel == "Balance Sheet":
    if "bs_report_snapshot" not in st.session_state:
        st.session_state.bs_report_snapshot = None

    st.html("""
    <div style="display:inline-flex;align-items:center;gap:0.5rem;background:#bcf0ae;
                color:#154212;font-size:0.65rem;font-weight:700;padding:0.25rem 0.75rem;
                border-radius:0.75rem;margin-bottom:1.5rem;">
        <span class="material-symbols-outlined" style="font-size:0.875rem;">info</span>
        Chart accounts (assets, liabilities, equity)
    </div>
    <h2 style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:800;
               letter-spacing:-0.02em;margin:0 0 0.5rem;">Balance Sheet</h2>
    <p style="color:#636262;font-style:italic;margin-bottom:1rem;">
        Same balances as General Ledger: trial balance net for each account plus posted transactions.
        Income and expense accounts are omitted here (use Profit and Loss).
    </p>
    """)

    bs_account_options = ["All Accounts"] + [
        f"{a['account_name']} ****{a['masked']}"
        for a in BANK_ACCOUNTS
        if a["account_type"] != "cash"
    ]

    with st.form("bs_report_form"):
        bs_def_s, bs_def_e = _default_report_period()
        bf1, bf2, bf3, bf4 = st.columns([1.1, 1.1, 2.2, 1], gap="medium")
        with bf1:
            bs_d0 = st.date_input(
                "FROM DATE",
                value=bs_def_s,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="bs_form_start",
            )
        with bf2:
            bs_d1 = st.date_input(
                "TO DATE",
                value=bs_def_e,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="bs_form_end",
            )
        with bf3:
            bs_bank_pick = st.selectbox(
                "ACCOUNT FILTER",
                options=bs_account_options,
                key="bs_form_bank",
            )
        with bf4:
            st.html("<div style='height:0.25rem'></div>")
            bs_submit = st.form_submit_button(
                "GENERATE REPORT", type="primary", use_container_width=True
            )

    if use_sample_data():
        st.info(
            "Demo mode uses sample transactions dated **2024**. Pick a 2024 range or set "
            "**USE_SAMPLE_DATA=false** for PostgreSQL."
        )

    if bs_submit:
        bs_start, bs_end = _normalize_period(bs_d0, bs_d1)
        bs_bid = _bank_id_for_report_label(bs_bank_pick, BANK_ACCOUNTS)
        snap = balance_sheet_report(bs_start, bs_end, bs_bid)
        st.session_state.bs_report_snapshot = {
            "data": snap,
            "period_start": bs_start,
            "period_end": bs_end,
            "bank_label": bs_bank_pick,
        }

    bs_snap = st.session_state.bs_report_snapshot

    if not CHART_OF_ACCOUNTS:
        st.info(
            "No chart of accounts yet. Complete onboarding or add accounts under **New entry**."
        )
    elif bs_snap is None:
        st.caption(
            "Choose **from** and **to** dates and account scope, then click **GENERATE REPORT**. "
            "Beginning and ending match the General Ledger for that range."
        )
    else:
        snap = bs_snap["data"]
        tot = snap["totals"]
        ps, pe = bs_snap["period_start"], bs_snap["period_end"]
        ph = html.escape(format_period_header(ps, pe))
        bl = html.escape(str(bs_snap["bank_label"]))

        st.markdown(f"**Period:** {ph}  \n**Bank scope:** {bl}")

        st.caption(
            "Beginning = balance at the start of the range; ending = balance at the end. "
            "Liabilities and equity show credit balances as positive. "
            "**Check:** Assets − (Liabilities + Equity) should be near zero when the books tie out."
        )

        vb, ve = float(tot["variance_beginning"]), float(tot["variance_ending"])
        if abs(vb) > 0.02 or abs(ve) > 0.02:
            st.warning(
                f"Balance sheet check line is **${vb:,.2f}** (beginning) and **${ve:,.2f}** (ending). "
                "Large differences often mean uncategorized transactions, unclosed P&amp;L, or mixed books."
            )

        def _bs_section_html(title: str, rows: list, tb: float, te: float) -> str:
            thead = """
                <thead>
                    <tr>
                        <th style="text-align:left;padding:0.5rem 0;font-size:0.62rem;font-weight:700;
                                   letter-spacing:0.1em;color:#636262;">ACCOUNT</th>
                        <th style="text-align:right;padding:0.5rem 0.5rem;font-size:0.62rem;font-weight:700;
                                   letter-spacing:0.1em;color:#636262;">BEGINNING</th>
                        <th style="text-align:right;padding:0.5rem 0;font-size:0.62rem;font-weight:700;
                                   letter-spacing:0.1em;color:#636262;">ENDING</th>
                    </tr>
                </thead>
            """
            body = ""
            for r in rows:
                num = html.escape(str(r.get("coa_number") or ""))
                name = html.escape(str(r.get("coa_name") or ""))
                label = f"{num} — {name}" if num else name
                b0 = float(r["beginning_display"])
                b1 = float(r["ending_display"])
                body += f"""
                <tr>
                    <td style="padding:0.65rem 0;border-bottom:1px solid rgba(194,201,187,0.12);
                               font-weight:500;">{label}</td>
                    <td style="padding:0.65rem 0.5rem;text-align:right;border-bottom:1px solid rgba(194,201,187,0.12);">
                        ${b0:,.2f}</td>
                    <td style="padding:0.65rem 0;text-align:right;border-bottom:1px solid rgba(194,201,187,0.12);">
                        ${b1:,.2f}</td>
                </tr>"""
            tbv = float(tb)
            tev = float(te)
            body += f"""
                <tr>
                    <td style="padding:0.85rem 0;font-weight:700;">Total {html.escape(title)}</td>
                    <td style="padding:0.85rem 0.5rem;text-align:right;font-weight:700;color:#154212;">
                        ${tbv:,.2f}</td>
                    <td style="padding:0.85rem 0;text-align:right;font-weight:700;color:#154212;">
                        ${tev:,.2f}</td>
                </tr>"""
            return f"""
            <div class="mm-report-table" style="margin-bottom:1.75rem;">
                <h4 style="font-family:'Manrope',sans-serif;font-weight:700;margin-bottom:0.75rem;">
                    {html.escape(title)}
                </h4>
                <table style="width:100%;border-collapse:collapse;font-size:0.875rem;">
                    {thead}
                    <tbody>{body}</tbody>
                </table>
            </div>
            """

        assets = snap["assets"]
        liabilities = snap["liabilities"]
        equity = snap["equity"]
        if not assets and not liabilities and not equity:
            st.info(
                "No asset, liability, or equity accounts appear in the general ledger for this scope. "
                "Try **All Accounts** or add chart lines of those types."
            )
        else:
            st.html(
                _bs_section_html(
                    "Assets",
                    assets,
                    tot["assets_beginning"],
                    tot["assets_ending"],
                )
            )
            st.html(
                _bs_section_html(
                    "Liabilities",
                    liabilities,
                    tot["liabilities_beginning"],
                    tot["liabilities_ending"],
                )
            )
            st.html(
                _bs_section_html(
                    "Equity",
                    equity,
                    tot["equity_beginning"],
                    tot["equity_ending"],
                )
            )

        st.html(f"""
        <div class="mm-report-table" style="margin-top:0.5rem;padding-top:1rem;
                    border-top:2px solid rgba(194,201,187,0.35);">
            <table style="width:100%;border-collapse:collapse;font-size:0.875rem;">
                <tbody>
                    <tr>
                        <td style="padding:0.5rem 0;font-weight:700;">
                            Check: Assets − (Liabilities + Equity)</td>
                        <td style="padding:0.5rem 0.5rem;text-align:right;font-weight:700;color:#636262;">
                            ${vb:,.2f}</td>
                        <td style="padding:0.5rem 0;text-align:right;font-weight:700;color:#636262;">
                            ${ve:,.2f}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """)

    _render_reports_back_to_top()


# ────────────────────────────────────────────────────────────────────────────────
# TAB 3: General Ledger (layout per GLReport_screen.png; uses app sidebar, not mock sidebar)
# ────────────────────────────────────────────────────────────────────────────────
if _report_sel == "General Ledger":
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
        "(optional expander), then **GENERATE REPORT**. "
        "**Account filter** is the book each **transaction** row is posted to: a Chase register, the **Journal** book, etc. "
        "Journal lines only appear when that filter is **All Accounts** or the journal. "
        "The first **Opening balance** line is a calculated roll-forward, not a line from **Journal entry** or imports."
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

    _gl_num_sorted = sorted(
        {a["number"] for a in CHART_OF_ACCOUNTS},
        key=lambda x: int(x) if str(x).isdigit() else 0,
    )
    _gl_coa_line_labels = [
        f"{n} — {next(a['name'] for a in CHART_OF_ACCOUNTS if a['number'] == n)}"
        for n in _gl_num_sorted
    ]
    gl_coa_from_options = [
        "— No minimum (all accounts from the start) —"
    ] + _gl_coa_line_labels
    gl_coa_to_options = [
        "— No maximum (all accounts to the end) —"
    ] + _gl_coa_line_labels

    with st.form("gl_report_form"):
        gl_def_s, gl_def_e = _default_report_period()
        f1, f2, f3, f4 = st.columns([1.1, 1.1, 2.2, 1], gap="medium")
        with f1:
            gl_d0 = st.date_input(
                "START DATE",
                value=gl_def_s,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="gl_form_start",
            )
        with f2:
            gl_d1 = st.date_input(
                "END DATE",
                value=gl_def_e,
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

        with st.expander("Advanced: chart account range (optional)", expanded=False):
            st.caption(
                "Limit the report to a range of **chart** accounts (by account number). "
                "Range is lexicographic—use consistent zero-padding in your COA if needed."
            )
            a1, a2 = st.columns(2)
            with a1:
                gl_coa_from_pick = st.selectbox(
                    "From account",
                    options=gl_coa_from_options,
                    key="gl_form_coa_from_dd",
                )
            with a2:
                gl_coa_to_pick = st.selectbox(
                    "To account",
                    options=gl_coa_to_options,
                    key="gl_form_coa_to_dd",
                )

    if gl_submit:
        gl_start, gl_end = _normalize_period(gl_d0, gl_d1)
        gl_bid = _bank_id_for_report_label(gl_bank_pick, BANK_ACCOUNTS)
        cf = _coa_number_from_gl_range_label(gl_coa_from_pick)
        ct = _coa_number_from_gl_range_label(gl_coa_to_pick)
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

    _render_reports_back_to_top()


# ────────────────────────────────────────────────────────────────────────────────
# TAB 4: Activity (all transaction lines per COA, every source)
# ────────────────────────────────────────────────────────────────────────────────
def _coa_id_list_from_multiselect_labels(
    selected: list[str], chart: list[Any]
) -> list[str]:
    m = {f"{a['number']} — {a['name']}": (a.get("id") or "").strip() for a in chart}
    return [m[lb] for lb in (selected or []) if lb in m and m[lb]]


def _activity_ledger_coa_notes(
    coa_id_list: list[str], chart: list[dict], bank_accounts: list[dict]
) -> str | None:
    """
    Explain why register manual lines may be missing for a COA: manual entry cannot
    use the same chart line as that register’s linked Ledger (cash) account.
    """

    def _uuid_key(s: str) -> str:
        t = (s or "").strip()
        if not t:
            return ""
        try:
            return str(UUID(t))
        except ValueError:
            return t

    cby = {_uuid_key(c.get("id") or ""): c for c in (chart or []) if _uuid_key(c.get("id") or "")}
    parts: list[str] = []
    for cid in coa_id_list or []:
        ck = _uuid_key((cid or "").strip())
        if not ck or ck not in cby:
            continue
        regs: list[str] = []
        for a in bank_accounts or []:
            if (a.get("account_type") or "").lower() in ("journal",):
                continue
            if _uuid_key((a.get("ledger_coa_id") or "")) != ck:
                continue
            an = (a.get("account_name") or "").strip() or "Register"
            mk = (a.get("masked") or "").strip() or "—"
            regs.append(f"{an} ****{mk}")
        if not regs:
            continue
        n = (cby[ck].get("number") or "").strip() or "—"
        nm = (cby[ck].get("name") or "").strip() or ""
        parts.append(
            f"**{n} — {nm}** is the **Ledger (bank/cash) line** for {', '.join(regs)}. "
            "A **register manual** line must classify to a **different** account than this—see **New entry**—"
            "so the manual’s **chart line** (and `source` **manual_register**) is usually an expense, income, or "
            "other account, not this Ledger line. **Journal entries** are not subject to that rule, so a JE can "
            f"still list **{n}** in this report."
        )
    if not parts:
        return None
    return "\n\n".join(parts)


def _activity_report_csv(rows: list[dict[str, Any]]) -> str:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "Date",
            "COA #",
            "COA name",
            "Source",
            "Status",
            "Register",
            "Masked",
            "Bank",
            "Payee",
            "Description",
            "Debit",
            "Credit",
            "Posting group",
            "Transaction id",
            "Import batch",
            "Created at",
        ]
    )
    for r in rows:
        w.writerow(
            [
                r.get("date") or "",
                r.get("coa_number") or "",
                r.get("coa_name") or "",
                r.get("source") or "",
                r.get("status") or "",
                r.get("register_name") or "",
                r.get("register_masked") or "",
                r.get("bank_name") or "",
                r.get("payee") or "",
                (r.get("description") or "") or "",
                f"{r.get('debit', 0):.2f}" if r.get("debit") else "",
                f"{r.get('credit', 0):.2f}" if r.get("credit") else "",
                r.get("posting_group_id") or "",
                r.get("id") or "",
                r.get("import_batch_id") or "",
                (r.get("created_at") or "") if not r.get("is_opening") else "",
            ]
        )
    return buf.getvalue()


if _report_sel == "Activity":
    st.html("""
    <h2 style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:800;
               letter-spacing:-0.02em;margin:0 0 0.5rem;">Activity (by chart account)</h2>
    <p style="color:#636262;margin-bottom:1rem;max-width:48rem;">
        Choose a <strong>date range</strong> and which <strong>chart of accounts (COA)</strong> to include.
        The report lists <strong>every posting</strong> that hits those lines—<strong>all</strong> bank/card
        registers, cash, and the <strong>Journal</strong> book—so nothing is missing because of a book filter.
        Each row still shows <em>which</em> book it was posted in.
        You get a computed <strong>opening balance</strong> (same as General Ledger, all books)
        then <strong>period</strong> lines: imports, manual, journal, and the rest, by date.
    </p>
    """)
    st.caption(
        "Opening = trial balance (pending and confirmed) plus posted activity before the range; "
        "period = dated activity in the range. "
        "Lines with `source` trial_balance_opening that mirror imported TB are omitted from the period list to "
        "match the General Ledger; their effect is in opening. "
        "Wide **Entire chart** ranges can be large: use **Download CSV** or a narrower period for testing."
    )
    if use_sample_data():
        st.info(
            "Demo mode has no activity query. Set **USE_SAMPLE_DATA=false** in app/.env to list rows from "
            "PostgreSQL."
        )

    ar_coa_labels = [
        f"{a['number']} — {a['name']}"
        for a in sorted(
            CHART_OF_ACCOUNTS,
            key=lambda x: (int(x["number"]) if str(x.get("number") or "").isdigit() else 0, (x.get("number") or "")),
        )
    ]

    with st.form("activity_report_form"):
        ar_s, ar_e = _default_report_period()
        ar_c1, ar_c2, ar_c3 = st.columns([1.1, 1.1, 1], gap="medium")
        with ar_c1:
            ar_d0 = st.date_input(
                "FROM DATE",
                value=ar_s,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="ar_form_start",
            )
        with ar_c2:
            ar_d1 = st.date_input(
                "TO DATE",
                value=ar_e,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="ar_form_end",
            )
        with ar_c3:
            st.html("<div style='height:0.25rem'></div>")
            ar_submit = st.form_submit_button(
                "GENERATE REPORT", type="primary", use_container_width=True
            )
        ar_entire, ar_uncat = st.columns(2, gap="medium")
        with ar_entire:
            ar_all_chart = st.checkbox(
                "Entire chart (all active COA lines in range)",
                value=False,
                help="All classified COA lines in the date range; chart multiselect below is ignored.",
                key="ar_form_all_chart",
            )
        with ar_uncat:
            ar_inc_uncat = st.checkbox(
                "Include uncategorized (no COA on the line)",
                value=False,
                help="Also list lines with no chart account. Wide ranges can be large.",
                key="ar_form_uncategorized",
            )
        ar_coa = st.multiselect(
            "CHART ACCOUNTS (when not using entire chart)",
            options=ar_coa_labels,
            help="Every posting that classifies to any of these account lines, across all books (not a register filter).",
            key="ar_form_coa",
        )

    if ar_submit:
        if use_sample_data():
            st.warning(
                "Set **USE_SAMPLE_DATA=false** in app/.env to run the Activity report against PostgreSQL."
            )
        else:
            ar_p0, ar_p1 = _normalize_period(ar_d0, ar_d1)
            cids = _coa_id_list_from_multiselect_labels(ar_coa, CHART_OF_ACCOUNTS)
            if not ar_all_chart and not cids:
                st.error(
                    "Turn on **Entire chart** or select at least one chart account. "
                    "**Include uncategorized** adds unclassified lines in addition to that scope."
                )
            else:
                act_rows = coa_activity_report(
                    ar_p0,
                    ar_p1,
                    cids,
                    all_chart_accounts=ar_all_chart,
                    include_uncategorized=ar_inc_uncat,
                )
                st.markdown(
                    f"**{len(act_rows)}** row(s) (opening + period lines) in this scope."
                )
                st.caption(
                    "Dated **before** the **From** date: included in the **Opening balance** only (no line in the table). "
                    "Expand the **From** date to see those transactions as rows."
                )
                _nid = (
                    [(a.get("id") or "").strip() for a in CHART_OF_ACCOUNTS if (a.get("id") or "").strip()]
                    if ar_all_chart
                    else cids
                )
                _ledger_msg = _activity_ledger_coa_notes(_nid, CHART_OF_ACCOUNTS, BANK_ACCOUNTS)
                if _ledger_msg:
                    st.info(_ledger_msg)
                if act_rows:
                    show = []
                    for r in act_rows:
                        raw_desc = (r.get("description") or "")
                        ddesc = raw_desc if r.get("is_opening") else raw_desc[:200]
                        show.append(
                            {
                                "Date": r.get("date"),
                                "COA": f"{r.get('coa_number', '')} — {r.get('coa_name', '')}",
                                "Source": r.get("source"),
                                "Status": (r.get("status") or "")
                                if not r.get("is_opening")
                                else "",
                                "Register": r.get("register_name"),
                                "****": r.get("register_masked"),
                                "Type": r.get("register_type"),
                                "Bank": r.get("bank_name"),
                                "Payee": r.get("payee")
                                if not r.get("is_opening")
                                else "",
                                "Description": ddesc,
                                "Debit": r.get("debit")
                                if r.get("debit")
                                else None,
                                "Credit": r.get("credit")
                                if r.get("credit")
                                else None,
                                "Posting group": r.get("posting_group_id")
                                or "",
                                "Import batch": (r.get("import_batch_id") or "")
                                if not r.get("is_opening")
                                else "",
                                "Created at": (r.get("created_at") or "")
                                if not r.get("is_opening")
                                else "",
                            }
                        )
                    st.dataframe(
                        pd.DataFrame(show),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.download_button(
                        "Download CSV",
                        data=_activity_report_csv(act_rows),
                        file_name="activity_report.csv",
                        mime="text/csv",
                        key="ar_download_csv",
                    )
                else:
                    st.info("No lines in this period and filters.")

    st.html("<div style='height:1.5rem'></div>")
    _render_reports_back_to_top()


# ────────────────────────────────────────────────────────────────────────────────
# TAB 5: Trial Balance (GL ending balances for range, Debit/Credit columns)
# ────────────────────────────────────────────────────────────────────────────────
if _report_sel == "Trial Balance":
    if "tb_report_snapshot" not in st.session_state:
        st.session_state.tb_report_snapshot = None

    tb_account_options = ["All Accounts"] + [
        f"{a['account_name']} ****{a['masked']}"
        for a in BANK_ACCOUNTS
        if a["account_type"] != "cash"
    ]

    st.html("""
    <h2 style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:800;
               letter-spacing:-0.02em;margin:0 0 0.5rem;">Trial Balance</h2>
    <p style="color:#636262;margin-bottom:1rem;">
        Ending balance per chart account for the selected range (same as General Ledger).
        Net debit balance appears in <strong>Debits</strong>; net credit in <strong>Credits</strong>.
        Totals should match when the books balance.
    </p>
    """)

    with st.form("tb_report_form"):
        tb_def_s, tb_def_e = _default_report_period()
        tf1, tf2, tf3, tf4 = st.columns([1.1, 1.1, 2.2, 1], gap="medium")
        with tf1:
            tb_d0 = st.date_input(
                "FROM DATE",
                value=tb_def_s,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="tb_form_start",
            )
        with tf2:
            tb_d1 = st.date_input(
                "TO DATE",
                value=tb_def_e,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="tb_form_end",
            )
        with tf3:
            tb_bank_pick = st.selectbox(
                "ACCOUNT FILTER",
                options=tb_account_options,
                key="tb_form_bank",
            )
        with tf4:
            st.html("<div style='height:0.25rem'></div>")
            tb_submit = st.form_submit_button(
                "GENERATE REPORT", type="primary", use_container_width=True
            )

    if use_sample_data():
        st.info(
            "Demo mode uses sample transactions dated **2024**. Pick a 2024 range or set "
            "**USE_SAMPLE_DATA=false** for PostgreSQL."
        )

    if tb_submit:
        tb_start, tb_end = _normalize_period(tb_d0, tb_d1)
        tb_bid = _bank_id_for_report_label(tb_bank_pick, BANK_ACCOUNTS)
        snap = trial_balance_gl_report(tb_start, tb_end, tb_bid)
        st.session_state.tb_report_snapshot = {
            "data": snap,
            "period_start": tb_start,
            "period_end": tb_end,
            "bank_label": tb_bank_pick,
        }

    tb_snap = st.session_state.tb_report_snapshot

    if not CHART_OF_ACCOUNTS:
        st.info(
            "No chart of accounts yet. Complete onboarding or add accounts under **New entry**."
        )
    elif tb_snap is None:
        st.caption(
            "Choose **from** and **to** dates and account scope, then click **GENERATE REPORT**. "
            "Balances are as of the **end date** of the range (GL ending balance)."
        )
    else:
        ps, pe = tb_snap["period_start"], tb_snap["period_end"]
        ph = html.escape(format_period_header(ps, pe))
        bl = html.escape(str(tb_snap["bank_label"]))
        data = tb_snap["data"]
        tot = data["totals"]
        var_v = float(tot.get("variance") or 0)

        col_dl, _ = st.columns([1, 4])
        with col_dl:
            st.download_button(
                label="Download CSV",
                data=_tb_report_csv(data),
                file_name="trial_balance_report.csv",
                mime="text/csv",
                key="tb_download_csv",
                type="primary",
                use_container_width=True,
            )

        st.markdown(f"**Period:** {ph}  \n**Bank scope:** {bl}")

        st.caption(
            "Each row is the **ending** debit−credit balance for that account after trial balance "
            "lines and posted transactions through the end date (same rules as General Ledger)."
        )

        if abs(var_v) > 0.02:
            st.warning(
                f"Debit and credit column totals differ by **${var_v:,.2f}**. "
                "Investigate uncategorized lines, rounding, or incomplete posting."
            )

        tb_rows = ""
        total_deb = float(tot["total_debits"])
        total_crd = float(tot["total_credits"])
        for row in data["rows"]:
            deb = float(row.get("debits") or 0)
            crd = float(row.get("credits") or 0)
            deb_str = f"${deb:,.2f}"
            crd_str = f"${crd:,.2f}"
            coa_h = html.escape(str(row.get("coa") or ""))
            tb_rows += f"""
        <tr style="background:#ffffff;">
            <td style="padding:1rem;font-size:0.8rem;color:#636262;">{coa_h}</td>
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

    st.html("<div style='height:1.5rem'></div>")
    _render_reports_back_to_top()


# ────────────────────────────────────────────────────────────────────────────────
# TAB 6: Journal entries (manual journals by date range)
# ────────────────────────────────────────────────────────────────────────────────
if _report_sel == "Journal entries":
    if "je_report_snapshot" not in st.session_state:
        st.session_state.je_report_snapshot = None

    journal_books = [
        a
        for a in BANK_ACCOUNTS
        if (a.get("account_type") or "").strip().lower() == "journal"
    ]
    journal_books.sort(key=lambda x: (x.get("account_name") or "").lower())
    je_book_options = ["All journal books"] + [
        f"{a['account_name']} ****{a['masked']}" for a in journal_books
    ]

    st.html("""
    <p style="color:#154212;font-size:0.65rem;font-weight:700;text-transform:uppercase;
              letter-spacing:0.15em;margin-bottom:0.5rem;">Register</p>
    <h2 style="font-family:'Manrope',sans-serif;font-size:2.5rem;font-weight:800;
               letter-spacing:-0.03em;margin:0 0 0.5rem;">Journal entries</h2>
    <p style="color:#636262;font-style:italic;margin-bottom:1rem;">
        Manual journal postings grouped by entry (reference and lines). Filter by date and optional journal book.
    </p>
    """)

    with st.form("je_report_form"):
        je_def_s, je_def_e = _default_report_period()
        jf1, jf2, jf3, jf4 = st.columns([1.1, 1.1, 2.2, 1], gap="medium")
        with jf1:
            je_d0 = st.date_input(
                "FROM DATE",
                value=je_def_s,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="je_form_start",
            )
        with jf2:
            je_d1 = st.date_input(
                "TO DATE",
                value=je_def_e,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="je_form_end",
            )
        with jf3:
            je_book_pick = st.selectbox(
                "JOURNAL BOOK",
                options=je_book_options,
                key="je_form_book",
                disabled=len(je_book_options) <= 1,
            )
        with jf4:
            st.html("<div style='height:0.25rem'></div>")
            je_submit = st.form_submit_button(
                "GENERATE REPORT", type="primary", use_container_width=True
            )

    if use_sample_data():
        st.info(
            "Demo mode has no manual journal entries. Set **USE_SAMPLE_DATA=false** to "
            "see journals from PostgreSQL."
        )
    elif not journal_books:
        st.info(
            "No **Journal** register yet. Add one under **Bank & card accounts**, then post "
            "entries from **New entry**."
        )

    if je_submit and not use_sample_data():
        je_start, je_end = _normalize_period(je_d0, je_d1)
        je_bid = _journal_book_id_for_report_label(je_book_pick, journal_books)
        entries = journal_entries_report(je_start, je_end, je_bid)
        st.session_state.je_report_snapshot = {
            "entries": entries,
            "period_start": je_start,
            "period_end": je_end,
            "book_label": je_book_pick,
        }

    je_snap = st.session_state.je_report_snapshot

    if use_sample_data():
        pass
    elif je_snap is None:
        st.caption(
            "Choose **from** and **to** dates and an optional journal book, then click **GENERATE REPORT**."
        )
    else:
        ps, pe = je_snap["period_start"], je_snap["period_end"]
        ph = html.escape(format_period_header(ps, pe))
        bl = html.escape(str(je_snap["book_label"]))
        entries = je_snap["entries"] or []

        col_dl, _ = st.columns([1, 4])
        with col_dl:
            st.download_button(
                label="Download CSV",
                data=_journal_entries_report_csv(entries),
                file_name="journal_entries_report.csv",
                mime="text/csv",
                key="je_download_csv",
                type="primary",
                use_container_width=True,
            )

        st.markdown(f"**Period:** {ph}  \n**Journal book:** {bl}")

        if not entries:
            st.info("No journal entries in this period for the selected book.")
        else:
            st.caption(f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")
            for je_i, e in enumerate(entries):
                ed = e.get("entry_date")
                ds = (
                    ed.strftime("%b %d, %Y")
                    if hasattr(ed, "strftime")
                    else str(ed or "")
                )
                ref_raw = e.get("reference")
                ref = (
                    str(ref_raw).strip()
                    if ref_raw is not None
                    else ""
                ) or "(no reference)"
                # Unique label per row (Streamlit expander identity + duplicate refs on same day)
                exp_title = f"Entry {je_i + 1}: {ds} — {ref}"
                with st.expander(exp_title, expanded=False):
                    memo = e.get("memo")
                    if memo:
                        st.caption(str(memo))
                    st.caption(
                        f"Book: {e.get('journal_book_name') or '—'} · "
                        f"Posting group: {e.get('posting_group_id') or '—'}"
                    )
                    line_rows = _journal_lines_display_rows(e.get("lines"))
                    if not line_rows:
                        st.caption("No line detail for this entry.")
                    else:
                        display_rows = [
                            {
                                "Account": str(r["Account"]),
                                "Debit": float(r["Debit"]),
                                "Credit": float(r["Credit"]),
                            }
                            for r in line_rows
                        ]
                        st.dataframe(
                            display_rows,
                            use_container_width=True,
                            hide_index=True,
                        )
                    td, tc = float(e.get("total_debit") or 0), float(
                        e.get("total_credit") or 0
                    )
                    st.caption(f"Totals — Debit ${td:,.2f} · Credit ${tc:,.2f}")

    st.html("<div style='height:1.5rem'></div>")
    _render_reports_back_to_top()


# ────────────────────────────────────────────────────────────────────────────────
# TAB 7: Personal spending (owner draw / personal COAs by period)
# ────────────────────────────────────────────────────────────────────────────────
if _report_sel == "Personal spending":
    if "personal_report_snapshot" not in st.session_state:
        st.session_state.personal_report_snapshot = None

    personal_account_options = ["All Accounts"] + [
        f"{a['account_name']} ****{a['masked']}"
        for a in BANK_ACCOUNTS
        if a["account_type"] != "cash"
    ]

    coa_for_personal = [
        a
        for a in CHART_OF_ACCOUNTS
        if a.get("type") in ("Equity", "Expense")
    ]
    coa_for_personal.sort(key=lambda a: a["number"])
    coa_labels = [f"{a['number']} — {a['name']}" for a in coa_for_personal]
    default_personal = [
        lbl
        for lbl in coa_labels
        if "draw" in lbl.lower() or "personal" in lbl.lower()
    ]

    st.html("""
    <h2 style="font-family:'Manrope',sans-serif;font-size:2rem;font-weight:800;
               letter-spacing:-0.02em;margin:0 0 0.5rem;">Personal spending</h2>
    <p style="color:#636262;margin-bottom:1rem;max-width:44rem;line-height:1.5;">
        Owner draws and other personal buckets: pick <strong>Equity</strong> and/or
        <strong>Expense</strong> chart accounts (for example <em>3110</em> legacy,
        <em>3111</em> Food, <em>3112</em> Animals). Totals use the same General Ledger
        rules: net per line is <strong>debit − credit</strong> for the period.
    </p>
    """)

    with st.form("personal_report_form"):
        ps_def_s, ps_def_e = _default_report_period()
        ps1, ps2, ps3 = st.columns([1.1, 1.1, 2.2], gap="medium")
        with ps1:
            per_d0 = st.date_input(
                "FROM DATE",
                value=ps_def_s,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="personal_form_start",
            )
        with ps2:
            per_d1 = st.date_input(
                "TO DATE",
                value=ps_def_e,
                min_value=date(2020, 1, 1),
                max_value=date(2035, 12, 31),
                key="personal_form_end",
            )
        with ps3:
            per_bank_pick = st.selectbox(
                "ACCOUNT FILTER",
                options=personal_account_options,
                key="personal_form_bank",
            )
        per_coa_pick = st.multiselect(
            "CHART ACCOUNTS (categories)",
            options=coa_labels,
            default=default_personal[:12] if default_personal else [],
            help="Each account is one category in the breakdown. Include 3110 and 3111+ for a full picture.",
            key="personal_form_coa",
        )
        per_submit = st.form_submit_button(
            "GENERATE REPORT", type="primary", use_container_width=True
        )

    if use_sample_data():
        st.info(
            "Demo mode uses sample transactions dated **2024**. Pick a 2024 range or set "
            "**USE_SAMPLE_DATA=false** for PostgreSQL."
        )

    if per_submit:
        per_start, per_end = _normalize_period(per_d0, per_d1)
        per_bid = _bank_id_for_report_label(per_bank_pick, BANK_ACCOUNTS)
        nums = []
        for lbl in per_coa_pick:
            nums.append(lbl.split(" — ", 1)[0].strip())
        snap = personal_spending_report(per_start, per_end, per_bid, nums)
        st.session_state.personal_report_snapshot = {
            "data": snap,
            "period_start": per_start,
            "period_end": per_end,
            "bank_label": per_bank_pick,
            "coa_labels": list(per_coa_pick),
        }

    pr_snap = st.session_state.personal_report_snapshot

    if not CHART_OF_ACCOUNTS:
        st.info(
            "No chart of accounts yet. Complete onboarding or add accounts under **New entry**."
        )
    elif pr_snap is None:
        st.caption(
            "Choose a date range, bank scope, and at least one chart account, then "
            "**GENERATE REPORT**."
        )
    elif not pr_snap["coa_labels"]:
        st.warning("Select at least one chart account to run this report.")
    else:
        pdata = pr_snap["data"]
        ps, pe = pr_snap["period_start"], pr_snap["period_end"]
        ph = html.escape(format_period_header(ps, pe))
        bl = html.escape(str(pr_snap["bank_label"]))
        gt = float(pdata.get("grand_total") or 0)

        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                label="Summary CSV",
                data=_personal_spending_summary_csv(pdata),
                file_name="personal_spending_summary.csv",
                mime="text/csv",
                key="personal_dl_summary",
                type="primary",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                label="Detail CSV",
                data=_personal_spending_detail_csv(pdata),
                file_name="personal_spending_detail.csv",
                mime="text/csv",
                key="personal_dl_detail",
                use_container_width=True,
            )
        with dl3:
            st.download_button(
                label="Monthly CSV",
                data=_personal_spending_monthly_csv(pdata),
                file_name="personal_spending_by_month.csv",
                mime="text/csv",
                key="personal_dl_monthly",
                use_container_width=True,
            )

        st.markdown(f"**Period:** {ph}  \n**Bank scope:** {bl}")
        st.html(f"""
        <div class="mm-report-stat-card" style="margin:1rem 0 1.5rem 0;">
            <span class="mm-stat-label">Total (selected accounts)</span>
            <div style="font-family:'Manrope',sans-serif;font-size:1.75rem;font-weight:700;
                        color:#154212;">${gt:,.2f}</div>
        </div>
        """)

        st.caption(
            "**Percent** is each account’s share of the total net for the selected accounts only."
        )

        cat_rows = ""
        for row in pdata.get("categories", []):
            num = html.escape(str(row.get("coa_number") or ""))
            name = html.escape(str(row.get("coa_name") or ""))
            net = float(row.get("net") or 0)
            pct = float(row.get("pct") or 0)
            label = f"{num} — {name}" if num else name
            cat_rows += f"""
            <tr>
                <td style="padding:0.75rem 0;border-bottom:1px solid rgba(194,201,187,0.12);
                           font-weight:500;">{label}</td>
                <td style="padding:0.75rem 0.5rem;text-align:right;border-bottom:1px solid rgba(194,201,187,0.12);">
                    ${net:,.2f}</td>
                <td style="padding:0.75rem 0;text-align:right;border-bottom:1px solid rgba(194,201,187,0.12);">
                    {pct:.1f}%</td>
            </tr>"""

        st.html(f"""
        <div class="mm-report-table" style="margin-bottom:1.5rem;">
            <h4 style="font-family:'Manrope',sans-serif;font-weight:700;margin-bottom:0.75rem;">
                By category</h4>
            <table style="width:100%;border-collapse:collapse;font-size:0.875rem;">
                <thead>
                    <tr>
                        <th style="text-align:left;padding:0.5rem 0;font-size:0.62rem;font-weight:700;
                                   letter-spacing:0.1em;color:#636262;">ACCOUNT</th>
                        <th style="text-align:right;padding:0.5rem 0.5rem;font-size:0.62rem;font-weight:700;
                                   letter-spacing:0.1em;color:#636262;">NET</th>
                        <th style="text-align:right;padding:0.5rem 0;font-size:0.62rem;font-weight:700;
                                   letter-spacing:0.1em;color:#636262;">% OF TOTAL</th>
                    </tr>
                </thead>
                <tbody>{cat_rows}</tbody>
            </table>
        </div>
        """)

        by_m = pdata.get("by_month") or []
        if by_m:
            with st.expander("Monthly breakdown", expanded=False):
                m_rows = ""
                for block in by_m:
                    lab = html.escape(str(block.get("label") or ""))
                    tot = float(block.get("total") or 0)
                    parts = ", ".join(
                        f"{k}: ${v:,.2f}"
                        for k, v in sorted((block.get("by_coa") or {}).items())
                    )
                    m_rows += f"""
                    <tr>
                        <td style="padding:0.5rem 0;vertical-align:top;">{lab}</td>
                        <td style="padding:0.5rem 0.5rem;text-align:right;vertical-align:top;
                                   font-weight:600;">${tot:,.2f}</td>
                        <td style="padding:0.5rem 0;font-size:0.8rem;color:#636262;vertical-align:top;">
                            {html.escape(parts)}</td>
                    </tr>"""
                st.html(f"""
                <table style="width:100%;border-collapse:collapse;font-size:0.875rem;">
                    <thead>
                        <tr>
                            <th style="text-align:left;padding:0.35rem 0;">Month</th>
                            <th style="text-align:right;padding:0.35rem 0.5rem;">Total</th>
                            <th style="text-align:left;padding:0.35rem 0;">By account</th>
                        </tr>
                    </thead>
                    <tbody>{m_rows}</tbody>
                </table>
                """)

        st.subheader("Detail lines")
        dlines = pdata.get("detail") or []
        if not dlines:
            st.info("No activity on these accounts in this period for the selected bank scope.")
        else:
            df_d = pd.DataFrame(
                {
                    "Date": [str(r.get("date") or "")[:10] for r in dlines],
                    "Account": [
                        f"{r.get('coa_number') or ''} — {r.get('coa_name') or ''}".strip(" —")
                        for r in dlines
                    ],
                    "Payee": [r.get("payee") or "" for r in dlines],
                    "Description": [r.get("description") or "" for r in dlines],
                    "Debit": [r.get("debit") for r in dlines],
                    "Credit": [r.get("credit") for r in dlines],
                    "Net": [r.get("net") for r in dlines],
                }
            )
            st.dataframe(df_d, use_container_width=True, hide_index=True)

    st.html("<div style='height:1.5rem'></div>")
    _render_reports_back_to_top()


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

