import streamlit as st
import sys
from pathlib import Path
from datetime import date, datetime
from typing import List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from db.connection import use_sample_data
from data.bank_statement_csv import normalize_payee_for_rule
from data.providers import (
    bank_accounts,
    chart_of_accounts,
    commit_ledger_csv_import,
    db_ready,
    delete_payee_rule_for_bank_account,
    import_templates,
    ledger_summary,
    ledger_transactions,
    payee_rules_for_bank_account,
    payee_rules_schema_ready,
    persist_payee_rule_for_bank_account,
    preview_ledger_csv_import,
)

COA_SKIP_LABEL = "— Skip (no rule) —"

st.set_page_config(
    page_title="Ledger | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("ledger")
render_topbar("Search entries...")

if not db_ready():
    st.stop()

BANK_ACCOUNTS = bank_accounts()
IMPORT_TEMPLATES = import_templates()

account_options = [
    f"{a['account_name']} ****{a['masked']}"
    for a in BANK_ACCOUNTS if a["account_type"] != "cash"
]

if not account_options:
    if use_sample_data():
        st.warning(
            "No bank or card accounts in demo data (cash-only is excluded). "
            "This is unexpected—check app/data/sample_data.BANK_ACCOUNTS."
        )
    else:
        st.warning(
            "No bank or card accounts in PostgreSQL (checking, savings, or credit card). "
            "Petty cash is hidden on this screen. Add accounts via onboarding, or set "
            "**USE_SAMPLE_DATA=true** in app/.env to use built-in demo accounts."
        )
    st.stop()


def _acct_id_for_label(label: str):
    for a in BANK_ACCOUNTS:
        if f"{a['account_name']} ****{a['masked']}" == label:
            return a["id"]
    return None


def _acct_row(account_id: str) -> dict:
    for a in BANK_ACCOUNTS:
        if a.get("id") == account_id:
            return a
    return {}


def _format_ledger_statement_date(d) -> str:
    if d is None:
        return "—"
    if isinstance(d, datetime):
        return d.date().strftime("%b %d, %Y")
    if isinstance(d, date):
        return d.strftime("%b %d, %Y")
    return str(d)


def _bump_ledger_upload_reset(account_id: str) -> None:
    """Increment nonce so file_uploader remounts empty (Streamlit keeps file until key changes)."""
    k = f"ledger_upload_nonce_{account_id}"
    st.session_state[k] = int(st.session_state.get(k) or 0) + 1


def _ledger_preview_editor_key(account_id: str) -> str:
    return f"ledger_preview_editor_{account_id}"


def _included_mask_from_preview_editor(account_id: str, n_rows: int) -> List[bool]:
    """One bool per preview row: True = include in totals and commit. Defaults all True."""
    if n_rows <= 0:
        return []
    key = _ledger_preview_editor_key(account_id)
    val = st.session_state.get(key)
    if val is None:
        return [True] * n_rows
    try:
        df = pd.DataFrame(val) if isinstance(val, dict) else val
        if not hasattr(df, "iloc") or len(df) != n_rows or "Include" not in df.columns:
            return [True] * n_rows
        out: List[bool] = []
        for i in range(n_rows):
            v = df.iloc[i]["Include"]
            if pd.isna(v):
                out.append(True)
            else:
                out.append(bool(v))
        return out
    except (TypeError, ValueError, KeyError, IndexError):
        return [True] * n_rows


st.html("""
<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;">
    <span class="material-symbols-outlined" style="font-size:0.9rem;color:#636262;">
        account_balance
    </span>
    <span style="font-size:0.65rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.1em;color:#636262;">Working On:</span>
</div>
""")
selected_account = st.selectbox(
    "working_account",
    account_options,
    label_visibility="collapsed",
)
aid = _acct_id_for_label(selected_account)
ar = _acct_row(aid)
acct_type = (ar.get("account_type") or "").lower()
pv = st.session_state.get("ledger_import_preview")
if pv and pv.get("aid") != aid:
    st.session_state.pop("ledger_import_preview", None)
    pv = None

s = ledger_summary(aid)

preview_rows = (pv or {}).get("rows") if pv else None
if preview_rows:
    _inc = _included_mask_from_preview_editor(aid, len(preview_rows))
    _rows_for_bar = [r for r, ok in zip(preview_rows, _inc) if ok]
    import_deb = sum(float(r.get("debit_amount") or 0) for r in _rows_for_bar)
    import_crd = sum(float(r.get("credit_amount") or 0) for r in _rows_for_bar)
    # Start-of-period for this file = current book balance (submission opening ± posted txns),
    # not the stale ledger-submission baseline alone (that would repeat month 1’s opening).
    beg = float(s["ending_balance"])
    s_bar = {
        "beginning_balance": beg,
        "total_debits": import_deb,
        "total_credits": import_crd,
        "ending_balance": beg - import_deb + import_crd,
    }
else:
    # v_account_balances.beginning_balance is the latest ledger *submission* baseline (e.g. trial balance
    # opening), not rolled forward after CSV posts. Use ending_balance as carry-forward for the next month.
    carry = float(s["ending_balance"])
    s_bar = {
        "beginning_balance": carry,
        "total_debits": 0.0,
        "total_credits": 0.0,
        "ending_balance": carry,
    }

if preview_rows and pv:
    stmt_display = _format_ledger_statement_date(pv.get("end"))
else:
    stmt_display = _format_ledger_statement_date(s.get("last_statement_date"))

_ending_balance_label = "Calculated ending" if preview_rows else "Ending Balance"

# ── Balance summary bar ───────────────────────────────────────────────────────
st.html(f"""
<div class="mm-balance-bar">
    <div class="mm-balance-item">
        <div class="mm-balance-label">Beginning Balance</div>
        <div class="mm-balance-value">${s_bar['beginning_balance']:,.2f}</div>
    </div>
    <div class="mm-balance-item">
        <div class="mm-balance-label">Total Debits</div>
        <div class="mm-balance-value">${s_bar['total_debits']:,.2f}</div>
    </div>
    <div class="mm-balance-item">
        <div class="mm-balance-label">Total Credits</div>
        <div class="mm-balance-value">${s_bar['total_credits']:,.2f}</div>
    </div>
    <div class="mm-balance-item">
        <div class="mm-balance-label">{_ending_balance_label}</div>
        <div class="mm-balance-value ending">${s_bar['ending_balance']:,.2f}
            <span class="material-symbols-outlined"
                  style="font-size:1rem;vertical-align:middle;color:#154212;">
                check_circle
            </span>
        </div>
    </div>
    <div class="mm-balance-item">
        <div class="mm-balance-label">Last Statement Date</div>
        <div class="mm-balance-value mm-balance-date">{stmt_display}</div>
    </div>
</div>
""")

if preview_rows:
    st.caption(
        "**Beginning balance** is your **current** balance after all **posted** transactions (the right "
        "starting point for the next statement). **Debits**, **credits**, and **ending** apply only to "
        "rows with **Include** checked in the preview. Uncheck lines that belong to another period, then commit. "
        "**Last statement date** reflects this import’s **end date** until you commit."
    )
else:
    st.caption(
        "**Beginning balance** is your **current book balance** after all **posted** transactions—the "
        "starting point for the next statement. Totals stay at zero until you load a file; then this bar "
        "shows that carry-forward plus **this file’s** debits, credits, and projected ending. "
        "**Last statement date** is the **end date** you set for your **most recently ingested** CSV "
        "(the batch’s period end). "
        "Chart-of-accounts numbers apply per **transaction** in the table below."
    )
    if not use_sample_data() and abs(float(s.get("ending_balance") or 0)) < 0.01:
        st.caption(
            "If this stays **$0.00** after you confirmed Trial Balance, open **Bank & card accounts**, "
            "set **Ledger COA** to the chart line that matches this register in the TB (same account "
            "number), then **Save ledger COA**—that applies the opening balance to the Ledger."
        )

st.html("<div style='height:1.5rem'></div>")

with st.expander("Payee rules for this account", expanded=False):
    if acct_type == "journal":
        st.caption(
            "Payee rules apply to statement imports only. Journal registers use **New entry** for manual GL lines."
        )
    elif not use_sample_data() and not payee_rules_schema_ready():
        st.warning(
            "This PostgreSQL database still uses the old payee-rules layout (no `bank_account_id` on "
            "`payee_rules`). Apply the migration once, then refresh this page.\n\n"
            "From the repo root (with backups as needed):  \n"
            "`psql \"$DATABASE_URL\" -f app/db/migrate_payee_rules_bank_account.sql`  \n"
            "Or rebuild from DDL: `python scripts/reset_database.py --yes` (see script help for seeds)."
        )
    else:
        st.caption(
            "Import matches **normalized** payee text (trim, lowercase, single spaces) to your chart "
            "account for **this** account only. Same payee on another account can map elsewhere."
        )
        coa_rows = chart_of_accounts()
        coa_labels = [COA_SKIP_LABEL]
        coa_ids: List[Optional[str]] = [None]
        for r in coa_rows:
            cid = (r.get("id") or "").strip()
            if not cid:
                continue
            coa_labels.append(f'{r["number"]} - {r["name"]}')
            coa_ids.append(cid)

        rules = payee_rules_for_bank_account(aid)
        if not rules:
            st.caption("No payee rules yet for this account.")
        for rule in rules:
            rid = rule["id"]
            pat = rule["payee_pattern"]
            rk = f"ledger_pr_coa_{aid}_{rid}"
            if rk not in st.session_state:
                _di = (
                    coa_ids.index(rule["coa_id"])
                    if rule["coa_id"] in coa_ids
                    else 0
                )
                st.session_state[rk] = _di
            c_a, c_b, c_c = st.columns([2, 2, 1])
            with c_a:
                st.text(pat)
            with c_b:
                st.selectbox(
                    "COA",
                    options=list(range(len(coa_labels))),
                    format_func=lambda i, lb=coa_labels: lb[i],
                    key=rk,
                    label_visibility="collapsed",
                )
            with c_c:
                if st.button("Remove", key=f"ledger_rm_{aid}_{rid}"):
                    delete_payee_rule_for_bank_account(aid, pat)
                    st.session_state.pop(rk, None)
                    st.rerun()

        if rules and st.button("Save COA changes", key=f"ledger_save_coas_{aid}"):
            for rule in rules:
                rid = rule["id"]
                pat = rule["payee_pattern"]
                rk = f"ledger_pr_coa_{aid}_{rid}"
                idx = int(st.session_state.get(rk, 0))
                if idx < 0 or idx >= len(coa_ids):
                    idx = 0
                chosen = coa_ids[idx]
                if chosen:
                    persist_payee_rule_for_bank_account(aid, pat, chosen)
                else:
                    delete_payee_rule_for_bank_account(aid, pat)
                    st.session_state.pop(rk, None)
            st.success("Payee rules updated.")
            st.rerun()

        st.markdown("---")
        st.caption("Add a rule by payee text (normalized the same way as import).")
        st.text_input(
            "New payee pattern",
            key=f"ledger_new_pat_{aid}",
            placeholder="e.g. amazon marketplace",
        )
        st.selectbox(
            "Chart account",
            options=list(range(len(coa_labels))),
            format_func=lambda i, lb=coa_labels: lb[i],
            key=f"ledger_new_coa_{aid}",
        )
        if st.button("Add payee rule", key=f"ledger_add_rule_{aid}"):
            raw = (st.session_state.get(f"ledger_new_pat_{aid}") or "").strip()
            norm = normalize_payee_for_rule(raw)
            idx = int(st.session_state.get(f"ledger_new_coa_{aid}", 0))
            new_coa = coa_ids[idx] if 0 <= idx < len(coa_ids) else None
            if not norm:
                st.warning("Enter a payee pattern.")
            elif not new_coa:
                st.warning("Choose a chart account (not Skip).")
            else:
                persist_payee_rule_for_bank_account(aid, norm, new_coa)
                st.success("Rule added.")
                st.rerun()

# ── Upload zone + Parsing template ───────────────────────────────────────────
if acct_type == "journal":
    st.markdown("##### Statement import")
    st.info(
        "This register is for **manual journal entries** only. Statement CSV/PDF import is not used here. "
        "Leave **Ledger COA** unset on this book in **Bank & card accounts** so each line posts once to the "
        "chart account you choose."
    )
    st.page_link("pages/10_New_Entry.py", label="New journal entry", icon="➕")
else:
    if acct_type in ("checking", "savings"):
        allowed_templates = [t for t in IMPORT_TEMPLATES if (t.get("type") or "") == "bank_statement"]
    elif acct_type == "credit_card":
        allowed_templates = [t for t in IMPORT_TEMPLATES if (t.get("type") or "") == "credit_card"]
    else:
        allowed_templates = []

    # Template column first so `ledger_selected_template_id` is set before "Process File" runs.
    col_template, col_upload = st.columns([1, 1.5], gap="large")

    with col_template:
        st.html("""
        <div class="mm-card-low" style="height:100%;">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem;">
                <span class="material-symbols-outlined" style="font-size:1.25rem;color:#154212;">
                    copy_all
                </span>
                <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1rem;margin:0;">
                    Parsing Template
                </h4>
            </div>
            <p style="font-size:0.75rem;color:#636262;margin-bottom:1rem;">
                Only templates that match this account type are listed. This selection is used when you process a CSV or PDF.
            </p>
        """)

        if not allowed_templates:
            st.caption("No templates available for this account type.")
            st.session_state["ledger_selected_template_id"] = ""
        else:
            names = [t["name"] for t in allowed_templates]
            default_name = names[0]
            if pv and pv.get("aid") == aid:
                prev_tid = (pv.get("template_id") or "").strip()
                for t in allowed_templates:
                    if (t.get("id") or "").strip() == prev_tid:
                        default_name = t["name"]
                        break
            ix = names.index(default_name) if default_name in names else 0
            pick = st.selectbox(
                "Import template",
                options=names,
                index=ix,
                key=f"ledger_import_template_name_{aid}",
                label_visibility="visible",
            )
            sel = next(t for t in allowed_templates if t["name"] == pick)
            st.session_state["ledger_selected_template_id"] = sel["id"]

        st.html("""
        </div>
        """)

        c_new, _ = st.columns(2)
        with c_new:
            if st.button("+ Create New Template", key="new_template"):
                if acct_type == "credit_card":
                    st.switch_page("pages/5_Credit_Card_Config.py")
                else:
                    st.switch_page("pages/4_Bank_Statement_Template.py")

    with col_upload:
        _ul_nonce = int(st.session_state.get(f"ledger_upload_nonce_{aid}") or 0)
        uploaded = st.file_uploader(
            "Upload Bank or Credit Card Statement",
            type=["csv", "pdf", "ofx"],
            help="CSV or PDF (same column mapping as your template; PDF uses text/table extraction). "
            "OFX is not supported yet.",
            label_visibility="visible",
            key=f"ledger_statement_upload_{aid}_{_ul_nonce}",
        )

        st.html("<div style='height:0.75rem'></div>")

        col_start, col_end = st.columns(2, gap="medium")
        with col_start:
            start_date = st.date_input(
                "Start Date",
                value=date.today().replace(day=1),
                label_visibility="visible",
            )
        with col_end:
            end_date = st.date_input(
                "End Date",
                value=date.today(),
                label_visibility="visible",
            )

        stmt_ending_balance = st.number_input(
            "Bank statement ending balance",
            value=0.0,
            step=0.01,
            format="%.2f",
            help="Enter the ending balance exactly as shown on this bank or card statement. "
            "It must match **Calculated ending** in the balance summary (included rows only) or commit is blocked.",
            key=f"ledger_stmt_ending_{aid}",
        )

        if uploaded:
            if st.button("Process File", type="primary"):
                fname = (uploaded.name or "").lower()
                if fname.endswith(".ofx"):
                    st.warning(
                        "OFX import is not implemented yet. Export your statement as CSV or PDF, or use a CSV download "
                        "from your bank."
                    )
                elif not fname.endswith(".csv") and not fname.endswith(".pdf"):
                    st.warning("Please upload a .csv or .pdf file for import.")
                elif start_date > end_date:
                    st.error("Start date must be on or before end date.")
                elif not allowed_templates:
                    st.error("No import templates match this account type. Create one under Bank Statement Template.")
                else:
                    tid = st.session_state.get("ledger_selected_template_id")
                    if not tid:
                        st.error("Select an import template in the card on the left.")
                    else:
                        spin = "Parsing PDF…" if fname.endswith(".pdf") else "Parsing CSV…"
                        with st.spinner(spin):
                            rows, err = preview_ledger_csv_import(
                                aid,
                                tid,
                                uploaded.getvalue(),
                                start_date,
                                end_date,
                                filename=uploaded.name or "upload.csv",
                            )
                        if err:
                            st.error(err)
                        else:
                            st.session_state["ledger_import_preview"] = {
                                "aid": aid,
                                "rows": rows,
                                "template_id": tid,
                                "filename": uploaded.name or "upload.csv",
                                "start": start_date,
                                "end": end_date,
                            }
                            st.success(f"Loaded {len(rows)} row(s). Review and edit chart accounts below, then commit.")
                            st.rerun()

st.html("<div style='height:2rem'></div>")

# ── Import preview (after Process File) ─────────────────────────────────────
pv = st.session_state.get("ledger_import_preview")
if pv and pv.get("aid") == aid and pv.get("rows"):
    st.markdown("##### Import preview")
    st.caption(
        "Uncheck **Include** to drop a line from this import (e.g. wrong statement period). "
        "Edit **Description** if needed. Chart account defaults use payee rules for this account. "
        "**Every included row must have a chart account** (no “Skip”) before you can commit."
    )
    coa_rows = chart_of_accounts()
    coa_labels: List[str] = [COA_SKIP_LABEL]
    coa_ids: List[Optional[str]] = [None]
    for r in coa_rows:
        cid = (r.get("id") or "").strip()
        if not cid:
            continue
        coa_labels.append(f'{r["number"]} - {r["name"]}')
        coa_ids.append(cid)
    label_to_id = dict(zip(coa_labels, coa_ids))

    def _coa_label_for_row(coa_id_val: Optional[str]) -> str:
        if not coa_id_val:
            return COA_SKIP_LABEL
        if coa_id_val in coa_ids:
            return coa_labels[coa_ids.index(coa_id_val)]
        return COA_SKIP_LABEL

    rows_in = pv["rows"]
    data = []
    for r in rows_in:
        d = r["date"]
        date_s = d.isoformat() if isinstance(d, date) else str(d)
        deb = float(r.get("debit_amount") or 0)
        crd = float(r.get("credit_amount") or 0)
        data.append(
            {
                "Include": True,
                "Date": date_s,
                "Payee": r.get("payee") or "",
                "Description": (r.get("description") or "") or "",
                "Debit": deb if deb > 0 else None,
                "Credit": crd if crd > 0 else None,
                "Chart account": _coa_label_for_row(r.get("coa_id")),
            }
        )
    preview_df = pd.DataFrame(data)

    edited = st.data_editor(
        preview_df,
        column_config={
            "Include": st.column_config.CheckboxColumn("Include", help="Uncheck to omit this line from import", default=True),
            "Date": st.column_config.TextColumn("Date"),
            "Payee": st.column_config.TextColumn("Payee", width="large"),
            "Description": st.column_config.TextColumn("Description", width="medium"),
            "Debit": st.column_config.NumberColumn("Debit", format="$%.2f"),
            "Credit": st.column_config.NumberColumn("Credit", format="$%.2f"),
            "Chart account": st.column_config.SelectboxColumn(
                "Chart account",
                options=coa_labels,
                required=False,
            ),
        },
        disabled=["Date", "Payee", "Debit", "Credit"],
        hide_index=True,
        num_rows="fixed",
        key=f"ledger_preview_editor_{aid}",
        use_container_width=True,
    )

    b1, b2, _ = st.columns([1, 1, 2])
    with b1:
        discard = st.button("Discard preview", key=f"ledger_discard_{aid}")
    with b2:
        commit = st.button("Commit import", type="primary", key=f"ledger_commit_{aid}")

    if discard:
        st.session_state.pop("ledger_import_preview", None)
        _bump_ledger_upload_reset(aid)
        st.rerun()

    if commit:
        if edited is None or len(edited) != len(rows_in):
            st.error("Could not read edited table; try processing the file again.")
        else:
            out_rows: list[dict] = []
            missing_rows: list[int] = []
            for i, base in enumerate(rows_in):
                inc_val = edited.iloc[i].get("Include", True)
                if pd.isna(inc_val):
                    inc_val = True
                if not bool(inc_val):
                    continue
                lbl = edited.iloc[i]["Chart account"]
                new_coa = label_to_id.get(lbl)
                desc_edit = edited.iloc[i].get("Description")
                desc_s = (str(desc_edit) if desc_edit is not None else "").strip()
                row_out = {
                    **base,
                    "coa_id": new_coa,
                    "description": desc_s or None,
                }
                out_rows.append(row_out)
                if not (new_coa or "").strip():
                    missing_rows.append(i + 1)
            if not out_rows:
                st.error(
                    "No rows are **included** for import. Check **Include** for at least one line, "
                    "or use **Discard preview**."
                )
            else:
                if missing_rows:
                    shown = ", ".join(str(n) for n in missing_rows[:30])
                    more = (
                        f" (+{len(missing_rows) - 30} more)"
                        if len(missing_rows) > 30
                        else ""
                    )
                    st.error(
                        "Assign a **chart account** (Acct #) to every **included** line before importing. "
                        f"Still missing on row(s): **{shown}**{more}."
                    )
                else:
                    deb_imp = sum(float(r.get("debit_amount") or 0) for r in out_rows)
                    crd_imp = sum(float(r.get("credit_amount") or 0) for r in out_rows)
                    beg_book = float(s["ending_balance"])
                    calc_end = beg_book - deb_imp + crd_imp
                    rc = round(calc_end, 2)
                    rs = round(
                        float(st.session_state.get(f"ledger_stmt_ending_{aid}", 0) or 0),
                        2,
                    )
                    if rc != rs:
                        st.error(
                            f"Statement ending **${rs:,.2f}** does not match calculated ending "
                            f"**${rc:,.2f}** (difference **${rc - rs:,.2f}**). "
                            "Fix included rows, chart accounts, or the amount from your statement, then try again."
                        )
                    else:
                        with st.spinner("Saving…"):
                            n, cerr = commit_ledger_csv_import(
                                aid,
                                pv["template_id"],
                                pv["filename"],
                                pv["start"],
                                pv["end"],
                                out_rows,
                            )
                        if cerr:
                            if "Demo mode" in cerr:
                                st.warning(cerr)
                                st.session_state.pop("ledger_import_preview", None)
                                _bump_ledger_upload_reset(aid)
                                st.rerun()
                            else:
                                st.error(cerr)
                        else:
                            st.success(
                                f"Imported {n} transaction(s). Payee rules updated for assigned rows."
                            )
                            st.session_state.pop("ledger_import_preview", None)
                            _bump_ledger_upload_reset(aid)
                            st.rerun()

    st.html("<div style='height:1.5rem'></div>")

# ── Current Transactions table ────────────────────────────────────────────────
col_title, col_actions = st.columns([3, 1], gap="small")
with col_title:
    st.html("""
    <h3 style="font-family:'Manrope',sans-serif;font-size:1.4rem;font-weight:700;
               margin:0;">Current Transactions</h3>
    """)
with col_actions:
    col_filter, col_export = st.columns(2, gap="small")
    with col_filter:
        st.button("⚙ Filter", key="ledger_filter")
    with col_export:
        st.button("↑ Export", key="ledger_export")

st.caption(
    "If this account has a **ledger** chart COA set on Bank & card accounts, each import can post two "
    "lines (classification plus a mirrored leg). Use the checkbox to hide the mirror leg and match "
    "statement line count."
)
hide_mirrored_ledger_leg = st.checkbox(
    "Hide mirrored ledger leg (classification lines only)",
    value=True,
    key=f"ledger_hide_mirror_{aid}",
)
ledger_txns = ledger_transactions(aid, classification_only=hide_mirrored_ledger_leg)

st.html("<div style='height:0.75rem'></div>")

# Transaction rows
rows_html = ""
for txn in ledger_txns:
    deb_str = f"${txn['debit']:,.2f}"  if txn["debit"]   else "—"
    crd_str = f"${txn['credit']:,.2f}" if txn["credit"]  else "—"
    deb_color = "#1a1c1c" if txn["debit"] else "#c2c9bb"
    crd_color = "#1a1c1c" if txn["credit"] else "#c2c9bb"

    if txn["coa"]:
        coa_cell = f'<span class="mm-coa-badge">{txn["coa"]}</span>'
    else:
        coa_cell = '<span class="mm-assign-badge">Assign...</span>'

    flag_icon = (
        '<span class="material-symbols-outlined" style="color:#ba1a1a;font-size:1rem;">'
        'warning</span>'
        if txn["flagged"] else ""
    )

    rows_html += f"""
    <tr style="background:#ffffff;">
        <td style="padding:1rem;font-size:0.8rem;color:#636262;">{txn['date']}</td>
        <td style="padding:1rem;">
            <div class="mm-payee-name">{txn['payee']}</div>
            <div class="mm-payee-sub">{txn['sub']}</div>
        </td>
        <td style="padding:1rem;">{coa_cell}</td>
        <td style="padding:1rem;text-align:right;font-size:0.875rem;
                   color:{deb_color};font-weight:500;">{deb_str}</td>
        <td style="padding:1rem;text-align:right;font-size:0.875rem;
                   color:{crd_color};font-weight:500;">{crd_str}
                   {flag_icon}</td>
    </tr>
    <tr><td colspan="5" style="height:0.25rem;background:transparent;"></td></tr>"""

st.html(f"""
<div style="overflow-x:auto;margin-right:2rem;">
    <table class="mm-transaction-table" style="width:100%;border-collapse:separate;
                                               border-spacing:0 0.25rem;">
        <thead>
            <tr>
                <th>Date</th>
                <th>Payee</th>
                <th>COA Number</th>
                <th style="text-align:right;">Debits</th>
                <th style="text-align:right;">Credits</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
</div>
""")

# ── Subtotal row ──────────────────────────────────────────────────────────────
st.html(f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            padding:1rem 1rem;margin-right:2rem;border-top:1px solid rgba(194,201,187,0.2);">
    <span style="font-size:0.8rem;color:#154212;font-weight:600;cursor:pointer;">
        + Manual Entry
    </span>
    <div style="display:flex;align-items:center;gap:2rem;">
        <span style="font-size:0.8rem;color:#636262;">
            Subtotal Debits: <strong style="color:#1a1c1c;">${s['total_debits']:,.2f}</strong>
        </span>
        <span style="font-size:0.8rem;color:#636262;">
            Subtotal Credits: <strong style="color:#1a1c1c;">${s['total_credits']:,.2f}</strong>
        </span>
        <span style="display:flex;align-items:center;gap:0.25rem;font-size:0.8rem;
                     color:#154212;font-weight:600;">
            <span class="material-symbols-outlined" style="font-size:1rem;">check_circle</span>
            Balanced
        </span>
    </div>
</div>
""")

# ── Decorative footer ─────────────────────────────────────────────────────────
st.html("""
<div style="margin-top:4rem;width:100%;height:8rem;border-radius:0.5rem;overflow:hidden;
            background:linear-gradient(135deg,#154212,#2d5a27 60%,#a1d494);">
</div>
<div style="display:flex;justify-content:space-between;padding:1rem 0;
            font-size:0.6rem;color:#636262;font-weight:700;text-transform:uppercase;
            letter-spacing:0.1em;">
    <span>MOTH AND MONEY © 2024</span>
    <span>STUDIO LEDGER SYSTEM V4.2.0</span>
</div>
""")

