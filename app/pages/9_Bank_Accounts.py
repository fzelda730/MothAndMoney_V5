"""Register bank and credit card accounts for PostgreSQL-backed mode."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.providers import (
    bank_accounts_manage,
    banks_for_onboarding,
    chart_of_accounts,
    db_ready,
    delete_bank_account_from_db,
    import_templates,
    save_bank_account_to_db,
    update_bank_account_ledger_coa_in_db,
)
from db.connection import use_sample_data

_ADD_NEW = "Add a new institution"
_USE_SAVED = "Use an institution already saved"

st.set_page_config(
    page_title="Bank & Card Accounts | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("onboarding")
render_topbar("Register accounts…")

if not db_ready():
    st.stop()

st.html("""
<div style="font-size:0.65rem;color:#636262;font-weight:700;text-transform:uppercase;
            letter-spacing:0.1em;margin-bottom:0.5rem;">
    Configuration › Accounts
</div>
<h1 class="mm-page-title" style="font-size:2rem;margin-bottom:0.25rem;">
    Bank &amp; card accounts
</h1>
<p class="mm-page-description" style="margin-bottom:1.5rem;">
    Register each checking, savings, cash, or credit card account you will use in the Ledger.
    Link an import template you created under Bank Statement or Credit Card mapping first.
</p>
""")

if use_sample_data():
    st.info(
        "Demo mode is on (**USE_SAMPLE_DATA=true**). Account registration is stored in PostgreSQL only. "
        "Set **USE_SAMPLE_DATA=false** in app/.env to add real accounts."
    )
    st.stop()

_managed_accounts = bank_accounts_manage()
banks = banks_for_onboarding()
# If banks is empty but accounts exist (edge case), derive institutions from registered accounts.
if not banks:
    _seen: dict[str, dict] = {}
    for r in _managed_accounts:
        bid = (r.get("bank_id") or "").strip()
        if bid and bid not in _seen:
            _seen[bid] = {
                "id": bid,
                "bank_name": r.get("bank_name") or "",
                "bank_type": (r.get("bank_type") or "depository"),
            }
    banks = list(_seen.values())


def _institution_dropdown_label(b: dict) -> str:
    name = (b.get("bank_name") or "").strip() or "(unnamed)"
    kind = "Bank (depository)" if b.get("bank_type") == "depository" else "Card issuer"
    if name == "Book":
        kind = f"{kind} — trial balance placeholder"
    return f"{name} · {kind}"

banks_pickable = banks
banks_by_id = {str(b["id"]): b for b in banks_pickable}
all_templates = import_templates()

st.subheader("Add an account")
# Mode / institution kind / saved-institution picker must be OUTSIDE st.form. Widgets inside a form
# do not update Python until submit, so the UI would stay on the wrong branch and credit_card
# templates would never appear when switching to a card issuer.
mode = st.radio(
    "How do you want to add this account?",
    [_ADD_NEW, _USE_SAVED],
    horizontal=True,
    key="bank_acct_add_mode",
    help="New: type the bank or issuer name. Saved: pick from institutions already in the database.",
)

existing_bank_id: str | None = None
bank_type_for_new = ""
bt_eff: str | None = None

if mode == _ADD_NEW:
    st.caption(
        "**New institution:** use the **text field in the form** for the bank or card issuer name "
        "(e.g. Relay). The import template dropdown is only for **CSV column mapping**—not the bank name."
    )
    kind = st.radio(
        "What kind of institution is this?",
        ["Bank (checking / savings / cash)", "Credit card issuer"],
        horizontal=True,
        key="bank_acct_inst_kind",
    )
    bank_type_for_new = "depository" if kind.startswith("Bank") else "credit_card"
    bt_eff = bank_type_for_new
else:
    if not banks_pickable:
        st.caption("No saved institutions yet—choose “Add a new institution” above.")
    else:
        _ids = list(banks_by_id.keys())
        existing_bank_id = st.selectbox(
            "Which saved institution?",
            options=_ids,
            format_func=lambda bid: _institution_dropdown_label(banks_by_id[bid]),
            key="bank_acct_saved_inst",
            help="Lists rows from the banks table. If you see accounts below but nothing here, refresh the page.",
        )
        _b = banks_by_id.get(existing_bank_id)
        if _b:
            st.markdown(
                f"**Bank or card issuer:** {_b['bank_name']} "
                f"({'depository' if _b['bank_type'] == 'depository' else 'credit card issuer'})"
            )
        if existing_bank_id and existing_bank_id in banks_by_id:
            bt_eff = banks_by_id[existing_bank_id]["bank_type"]

with st.form("add_bank_account", clear_on_submit=True):
    new_bank_name = ""
    if mode == _ADD_NEW:
        new_bank_name = st.text_input(
            "Bank or card issuer name",
            max_chars=255,
            placeholder="e.g. Relay",
            help="Type the institution name here. This is not the same as choosing an import template below.",
        )

    if bt_eff == "depository":
        tpl_list = [t for t in all_templates if t.get("type") == "bank_statement"]
    elif bt_eff == "credit_card":
        tpl_list = [t for t in all_templates if t.get("type") == "credit_card"]
    else:
        tpl_list = []
    tpl_labels = ["— No template (optional) —"] + [f"{t['name']}" for t in tpl_list]
    tpl_idx = st.selectbox(
        "Import template (CSV column mapping)",
        range(len(tpl_labels)),
        format_func=lambda i: tpl_labels[i],
        help="Your saved statement format from Bank Statement or Credit Card config—not the bank name.",
    )
    template_id: str | None = None
    if tpl_idx > 0:
        template_id = tpl_list[tpl_idx - 1]["id"]

    account_name = st.text_input("Account display name", max_chars=255)
    last4 = st.text_input("Last four digits (or mask)", max_chars=10)

    if bt_eff == "depository":
        _at_options = ["checking", "savings", "cash", "journal"]
    elif bt_eff == "credit_card":
        _at_options = ["credit_card"]
    else:
        _at_options = ["checking"]
    account_type = st.selectbox(
        "Account type",
        _at_options,
        format_func=lambda x: x.replace("_", " ").title(),
        help="Credit card accounts use a **credit card issuer** institution (see above).",
        disabled=bt_eff not in ("depository", "credit_card"),
    )
    if bt_eff not in ("depository", "credit_card"):
        st.caption("Choose an institution above to set account type options.")

    submitted = st.form_submit_button("Save account", type="primary")

if submitted:
    err_msg: str | None = None
    if mode == _ADD_NEW and not (new_bank_name or "").strip():
        err_msg = "Enter an institution name."
    elif mode == _USE_SAVED and not existing_bank_id:
        err_msg = "Add a new institution first, or seed banks from demo SQL."
    elif not (account_name or "").strip():
        err_msg = "Enter an account display name."
    elif not (last4 or "").strip():
        err_msg = "Enter the last four digits (or a mask for cash)."
    elif bt_eff not in ("depository", "credit_card"):
        err_msg = "Choose or add an institution before saving."
    if not err_msg:
        _id, err_msg = save_bank_account_to_db(
            existing_bank_id=existing_bank_id if mode == _USE_SAVED else None,
            new_bank_name=new_bank_name if mode == _ADD_NEW else None,
            bank_type_for_new=bank_type_for_new if mode == _ADD_NEW else None,
            template_id=template_id,
            account_name=account_name,
            account_number_masked=last4,
            account_type=account_type,
        )
    if err_msg:
        st.error(err_msg)
    else:
        st.success("Account saved.")
        st.rerun()

st.divider()
st.subheader("Registered accounts")
st.caption(
    "Optional **ledger chart account**: when set, each committed import line posts a second row to that COA "
    "(debit/credit swapped) so the GL has both classification and bank/card legs. "
    "Use a cash/bank asset for checking and savings; a card liability account for credit cards."
)

_coa_rows = chart_of_accounts()
_ledger_coa_labels = ["— None —"]
_ledger_coa_ids: list[str | None] = [None]
for _ca in _coa_rows:
    _cid = (_ca.get("id") or "").strip()
    if not _cid:
        continue
    _ledger_coa_labels.append(f"{_ca['number']} - {_ca['name']}")
    _ledger_coa_ids.append(_cid)

rows = _managed_accounts
if not rows:
    st.caption("No accounts yet.")
else:
    for r in rows:
        txn = int(r.get("txn_count") or 0)
        tn = r.get("template_name") or "—"
        st.markdown(
            f"**{r['account_name']}** ({r['bank_name']}) · ****{r['account_number_masked']} · "
            f"{r['account_type'].replace('_', ' ')} · template: {tn} · **{txn}** transaction(s)"
        )
        _lc = (r.get("ledger_coa_id") or "").strip()
        _cur_i = _ledger_coa_ids.index(_lc) if _lc in _ledger_coa_ids else 0
        _lc_widget_key = f"ledger_coa_ui_{r['id']}_{_lc or 'none'}"
        c_a, c_b, c_c = st.columns([2, 2, 1])
        with c_a:
            st.selectbox(
                "Ledger COA (double-entry)",
                options=list(range(len(_ledger_coa_labels))),
                format_func=lambda i, lb=_ledger_coa_labels: lb[i],
                index=_cur_i,
                key=_lc_widget_key,
                help="Mirrored posting for imports. Leave unset for a single line per row (classification only).",
            )
        with c_b:
            st.write("")
            st.write("")
            if st.button("Save ledger COA", key=f"save_lc_{r['id']}", type="primary"):
                _pick = int(st.session_state.get(_lc_widget_key, _cur_i))
                _new = _ledger_coa_ids[_pick]
                _err = update_bank_account_ledger_coa_in_db(r["id"], _new)
                if _err:
                    st.error(_err)
                else:
                    st.session_state["_ledger_coa_saved"] = True
                    st.rerun()
        with c_c:
            st.write("")
            st.write("")
            if txn > 0:
                st.caption("Cannot remove while transactions exist.")
            else:
                if st.button("Remove", key=f"rm_{r['id']}", type="secondary"):
                    err = delete_bank_account_from_db(r["id"])
                    if err:
                        st.error(err)
                    else:
                        st.session_state["_acct_removed_ok"] = True
                        st.rerun()
        st.markdown("")

if st.session_state.pop("_acct_removed_ok", False):
    st.success("Account removed.")
if st.session_state.pop("_ledger_coa_saved", False):
    st.success("Ledger chart account saved.")
