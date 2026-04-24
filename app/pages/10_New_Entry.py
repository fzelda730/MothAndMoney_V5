"""New entry: chart of account and manual journal entries."""

from __future__ import annotations

import sys
from pathlib import Path

from datetime import date

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.providers import (
    bank_accounts,
    chart_of_accounts,
    db_ready,
    delete_chart_of_account_from_db,
    get_chart_of_account_for_edit,
    save_chart_of_account_to_db,
    save_journal_entry_to_db,
    save_register_transaction_to_db,
    update_chart_of_account_in_db,
)
from db.connection import use_sample_data

_COA_TYPE_CHOICES: list[tuple[str, str]] = [
    ("Asset", "asset"),
    ("Liability", "liability"),
    ("Equity", "equity"),
    ("Income", "income"),
    ("Expense", "expense"),
]


def _coa_type_index(coa_type: str) -> int:
    t = (coa_type or "").strip().lower()
    for i, (_, v) in enumerate(_COA_TYPE_CHOICES):
        if v == t:
            return i
    return 0


@st.dialog("Delete chart account")
def _delete_coa_dialog(coa_id: str, display_label: str) -> None:
    st.markdown(f"Permanently delete **{display_label}**? This cannot be undone.")
    st.caption(
        "Accounts with posted or pending transactions cannot be deleted. "
        "Confirming delete removes trial balance lines for this account. "
        "Payee rules must be removed or reassigned first."
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with c2:
        if st.button("Delete permanently", type="primary", use_container_width=True):
            ok, err = delete_chart_of_account_from_db(coa_id)
            if ok:
                st.success("Chart account deleted.")
                st.rerun()
            else:
                st.error(err or "Delete failed.")


st.set_page_config(
    page_title="New Entry | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("new_entry")
render_topbar("New entry…")

if not db_ready():
    st.stop()

st.html("""
<div style="font-size:0.65rem;color:#636262;font-weight:700;text-transform:uppercase;
            letter-spacing:0.1em;margin-bottom:0.5rem;">
    Entry
</div>
<h1 class="mm-page-title" style="font-size:2rem;margin-bottom:0.25rem;">
    New entry
</h1>
<p class="mm-page-description" style="margin-bottom:1.5rem;">
    Create or edit chart of accounts, post journal entries, or add a one-line **register** transaction
    (shows on the bank Ledger and in GL / TB like an import).
</p>
""")

entry_kind = st.radio(
    "Entry type",
    options=["Chart of account", "Journal entry", "Register transaction"],
    horizontal=True,
    key="new_entry_kind",
)

if entry_kind == "Journal entry":
    st.subheader("Journal entry")

    if use_sample_data():
        st.warning(
            "Demo mode does not post to PostgreSQL. Set **USE_SAMPLE_DATA=false** in app/.env to use journal entries."
        )
        st.stop()

    journal_accounts = [
        a
        for a in bank_accounts()
        if (a.get("account_type") or "").lower() == "journal"
    ]
    if not journal_accounts:
        st.warning(
            "No **Journal** register found. Under **Bank & card accounts**, add a depository institution and "
            "choose account type **Journal**, then return here."
        )
        st.page_link("pages/9_Bank_Accounts.py", label="Bank & card accounts", icon="🏦")
        st.stop()

    je_labels = [f"{a['account_name']} ****{a['masked']}" for a in journal_accounts]
    je_ids = [a["id"] for a in journal_accounts]
    je_pick = st.selectbox(
        "Journal book",
        options=list(range(len(je_labels))),
        format_func=lambda i, lb=je_labels: lb[i],
        help="Only accounts with type Journal can receive manual GL entries.",
    )
    bank_account_id = je_ids[je_pick]

    coa_rows = chart_of_accounts()
    if not coa_rows:
        st.error("Add chart of accounts first.")
        st.stop()
    coa_line_labels = [f"{r['number']} - {r['name']}" for r in coa_rows]
    coa_line_ids = [(r.get("id") or "").strip() for r in coa_rows]

    n_lines = st.number_input("Number of lines", min_value=2, max_value=20, value=2, step=1)
    entry_date = st.date_input("Entry date", value=date.today())
    reference = st.text_input("Reference", max_chars=500, placeholder="e.g. Accrual — office rent")
    memo = st.text_area("Memo (optional)", max_chars=5000, height=80)

    st.markdown("**Lines** — each row: one chart account and either a debit **or** a credit (not both).")
    line_data: list[dict] = []
    for li in range(int(n_lines)):
        c1, c2, c3 = st.columns([2.2, 1, 1])
        with c1:
            # -1 = no selection yet (blank) so a new entry does not pre-fill the first COA
            _coa_opts = list(range(-1, len(coa_line_labels)))
            coa_idx = st.selectbox(
                f"Account line {li + 1}",
                options=_coa_opts,
                format_func=lambda i, labels=coa_line_labels: (
                    "— Select account —" if i < 0 else labels[i]
                ),
                index=0,
                key=f"je_coa_{li}",
                label_visibility="visible",
            )
        with c2:
            deb = st.number_input(
                "Debit",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                key=f"je_deb_{li}",
            )
        with c3:
            crd = st.number_input(
                "Credit",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                key=f"je_crd_{li}",
            )
        line_data.append(
            {
                "coa_id": (coa_line_ids[coa_idx] if coa_idx >= 0 else "").strip(),
                "debit_amount": float(deb),
                "credit_amount": float(crd),
            }
        )

    if st.button("Post journal entry", type="primary", key="je_submit"):
        ref_s = (reference or "").strip()
        if not ref_s:
            st.error("Reference is required.")
        else:
            gid, err = save_journal_entry_to_db(
                bank_account_id=bank_account_id,
                entry_date=entry_date,
                reference=ref_s,
                memo=(memo or "").strip() or None,
                lines=line_data,
            )
            if err:
                st.error(err)
            else:
                st.success("Journal entry posted.")
                if gid:
                    st.caption(f"Posting group: `{gid}`")
                p1, p2 = st.columns(2)
                with p1:
                    st.page_link("pages/6_Ledger.py", label="Go to Ledger", icon="📖")
                with p2:
                    st.page_link("pages/7_Reports.py", label="Go to Reports", icon="📊")

    st.stop()

if entry_kind == "Register transaction":
    st.subheader("Register transaction")

    if use_sample_data():
        st.warning(
            "Demo mode does not post to PostgreSQL. Set **USE_SAMPLE_DATA=false** in app/.env to use "
            "register transactions."
        )
        st.stop()

    all_accts = bank_accounts()
    register_accounts = [
        a
        for a in all_accts
        if (a.get("account_type") or "").lower() != "journal"
    ]
    if not register_accounts:
        st.error("Add a bank or card under **Bank & card accounts** first.")
        st.page_link("pages/9_Bank_Accounts.py", label="Bank & card accounts", icon="🏦")
        st.stop()

    reg_labels = [f"{a['account_name']} ****{a['masked']}" for a in register_accounts]
    reg_ids = [a["id"] for a in register_accounts]
    reg_pick = st.selectbox(
        "Register (bank or card account)",
        options=list(range(len(reg_labels))),
        format_func=lambda i, lb=reg_labels: lb[i],
        help="The transaction is posted to this subledger, like a statement line.",
    )
    reg_bank_id = reg_ids[reg_pick]
    ar = next(a for a in register_accounts if a["id"] == reg_bank_id)
    _lc = (ar.get("ledger_coa_id") or "").strip()
    if _lc and ar.get("ledger_coa_number"):
        st.caption(
            f"This register is linked to chart **{ar.get('ledger_coa_number')}** for cash. "
            f"Choose a **different** chart account for this line so the book balance can move."
        )

    coa_rows = chart_of_accounts()
    if not coa_rows:
        st.error("Add chart of accounts first.")
        st.stop()
    coa_lbls = [f"{r['number']} - {r['name']}" for r in coa_rows]
    coa_ids = [(r.get("id") or "").strip() for r in coa_rows]
    _coa_opts = list(range(-1, len(coa_lbls)))
    coa_i = st.selectbox(
        "Chart account (offset to this register line)",
        options=_coa_opts,
        format_func=lambda i, lab=coa_lbls: "— Select account —" if i < 0 else lab[i],
        index=0,
        key="reg_entry_coa",
    )
    r_date = st.date_input("Date", value=date.today(), key="reg_entry_date")
    r_payee = st.text_input(
        "Payee / short label",
        max_chars=500,
        placeholder="e.g. OB adjustment, Statement reconcile",
    )
    r_memo = st.text_area("Memo (optional)", max_chars=5000, height=80, key="reg_entry_memo")
    r_dir = st.radio(
        "Amount to register",
        options=["Debit (increase typical bank outflow column)", "Credit (increase typical inflow column)"],
        horizontal=True,
        key="reg_entry_dir",
    )
    r_amt = st.number_input(
        "Amount",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.2f",
        key="reg_entry_amt",
    )
    st.caption(
        "Debits and credits follow the same sign rules as **statement imports** for this account type."
    )

    if st.button("Post to register", type="primary", key="reg_entry_submit"):
        if coa_i < 0:
            st.error("Choose a chart account.")
        else:
            cid = coa_ids[coa_i]
            amt = float(r_amt)
            if amt <= 0:
                st.error("Enter a positive amount.")
            else:
                is_deb = "Debit" in (r_dir or "")
                deb, crd = (amt, 0.0) if is_deb else (0.0, amt)
                tx_id, err = save_register_transaction_to_db(
                    bank_account_id=reg_bank_id,
                    entry_date=r_date,
                    payee=(r_payee or "").strip() or "Register adjustment",
                    description=(r_memo or "").strip() or None,
                    coa_id=cid,
                    debit_amount=deb,
                    credit_amount=crd,
                )
                if err:
                    st.error(err)
                else:
                    st.success("Register transaction posted.")
                    if tx_id:
                        st.caption(f"Transaction id: `{tx_id}`")
                    p1, p2 = st.columns(2)
                    with p1:
                        st.page_link("pages/6_Ledger.py", label="Go to Ledger", icon="📖")
                    with p2:
                        st.page_link("pages/7_Reports.py", label="Go to Reports", icon="📊")

    st.stop()

st.subheader("Chart of account")

if use_sample_data():
    st.warning(
        "Demo mode uses a fixed sample chart. Set **USE_SAMPLE_DATA=false** in app/.env to create, edit, "
        "or delete accounts in PostgreSQL."
    )
    coa_mode = "Create new"
else:
    coa_mode = st.radio(
        "Mode",
        options=["Create new", "Edit existing"],
        horizontal=True,
        key="coa_mode_new_entry",
    )

st.caption(
    "Changing **account type** after transactions exist is allowed; reports will reflect the new "
    "classification. **Account number** must stay unique across the chart."
)

if coa_mode == "Create new":
    with st.form("form_new_coa", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            acct_num = st.text_input(
                "Account number",
                max_chars=20,
                placeholder="e.g. 1999",
                help="Unique number (up to 20 characters).",
            )
        with col_b:
            labels = [x[0] for x in _COA_TYPE_CHOICES]
            type_idx = st.selectbox(
                "Account type",
                options=list(range(len(labels))),
                format_func=lambda i, lb=labels: lb[i],
            )
        acct_name = st.text_input(
            "Account name",
            max_chars=255,
            placeholder="e.g. Transfer clearing",
        )
        subtype = st.text_input(
            "Subtype (optional)",
            max_chars=100,
            placeholder="e.g. clearing",
        )
        submitted = st.form_submit_button("Save chart account", type="primary")

    if submitted:
        _, coa_type = _COA_TYPE_CHOICES[type_idx]
        new_id, err = save_chart_of_account_to_db(
            account_number=(acct_num or "").strip(),
            account_name=(acct_name or "").strip(),
            account_type=coa_type,
            account_subtype=(subtype or "").strip() or None,
        )
        if err:
            st.error(err)
        else:
            st.success(
                "Chart account created. It will appear in Ledger and Reports wherever you pick a chart account."
            )
            if new_id:
                st.caption(f"Internal id: `{new_id}`")
            p1, p2 = st.columns(2)
            with p1:
                st.page_link("pages/6_Ledger.py", label="Go to Ledger", icon="📖")
            with p2:
                st.page_link("pages/7_Reports.py", label="Go to Reports", icon="📊")

else:
    if st.session_state.pop("coa_edit_saved_msg", False):
        st.success("Chart account updated.")
        p1, p2 = st.columns(2)
        with p1:
            st.page_link("pages/6_Ledger.py", label="Go to Ledger", icon="📖")
        with p2:
            st.page_link("pages/7_Reports.py", label="Go to Reports", icon="📊")

    rows = chart_of_accounts()
    if not rows:
        st.warning("No chart accounts yet. Create one under **Create new** first.")
        st.stop()

    options_map = {f"{r['number']} - {r['name']}": r["id"] for r in rows}
    labels_sorted = sorted(options_map.keys())
    sel_label = st.selectbox(
        "Account to edit",
        options=labels_sorted,
        key="edit_coa_label_select",
    )
    sel_id = options_map[sel_label]
    row = get_chart_of_account_for_edit(sel_id)
    if not row:
        st.error("Could not load that chart account.")
        st.stop()

    tid = row["id"]
    type_idx_edit = _coa_type_index(row["type"])

    with st.form("form_edit_coa", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            acct_num_e = st.text_input(
                "Account number",
                max_chars=20,
                value=row["number"],
                help="Unique number (up to 20 characters).",
                key=f"coa_edit_num_{tid}",
            )
        with col_b:
            labels_t = [x[0] for x in _COA_TYPE_CHOICES]
            type_idx_e = st.selectbox(
                "Account type",
                options=list(range(len(labels_t))),
                index=type_idx_edit,
                format_func=lambda i, lb=labels_t: lb[i],
                key=f"coa_edit_type_{tid}",
            )
        acct_name_e = st.text_input(
            "Account name",
            max_chars=255,
            value=row["name"],
            key=f"coa_edit_name_{tid}",
        )
        subtype_e = st.text_input(
            "Subtype (optional)",
            max_chars=100,
            value=row["subtype"] or "",
            key=f"coa_edit_sub_{tid}",
        )
        save_edit = st.form_submit_button("Save changes", type="primary")

    if save_edit:
        _, coa_type_e = _COA_TYPE_CHOICES[type_idx_e]
        ok, err = update_chart_of_account_in_db(
            tid,
            account_number=(acct_num_e or "").strip(),
            account_name=(acct_name_e or "").strip(),
            account_type=coa_type_e,
            account_subtype=(subtype_e or "").strip() or None,
        )
        if err:
            st.error(err)
        else:
            for k in (
                f"coa_edit_num_{tid}",
                f"coa_edit_type_{tid}",
                f"coa_edit_name_{tid}",
                f"coa_edit_sub_{tid}",
            ):
                st.session_state.pop(k, None)
            st.session_state["coa_edit_saved_msg"] = True
            st.rerun()

    if st.button("Delete account", type="secondary", key="btn_delete_coa"):
        _delete_coa_dialog(sel_id, sel_label)
