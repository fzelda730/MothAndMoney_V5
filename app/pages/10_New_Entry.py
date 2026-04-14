"""New entry: chart of account (journal entry planned)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.providers import (
    chart_of_accounts,
    db_ready,
    delete_chart_of_account_from_db,
    get_chart_of_account_for_edit,
    save_chart_of_account_to_db,
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
    Create or edit chart of accounts for categorizing transactions. Journal entries will be added here later.
</p>
""")

entry_kind = st.radio(
    "Entry type",
    options=["Chart of account", "Journal entry"],
    horizontal=True,
    key="new_entry_kind",
)

if entry_kind == "Journal entry":
    st.info(
        "Journal entry is not available yet. Use **Chart of account** to add an account number "
        "to your chart of accounts."
    )
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
