"""
MOTH AND MONEY — ONBOARDING PAGE (UI)
/ui/onboarding_page.py

Formal:  Streamlit surface for Trial Balance upload, Review grid, posting audit,
         and Establish Ledger — all classification and commits delegated to OnboardingEngine.
Human:   Birth of the ledger with a Danger Zone, then one deliberate Commit when the math ties.
"""

from __future__ import annotations

from datetime import date

import streamlit as st
from streamlit.column_config import NumberColumn, SelectboxColumn, TextColumn

from database.db_maintenance import wipe_local_ledger_database
from logic.onboarding_engine import OnboardingEngine


def render_onboarding_page() -> None:
    """
    Formal:  Renders onboarding when chart_of_accounts is empty: reset, upload,
             data_editor Review, Decimal audit metrics, gated Establish Ledger.
    Human:   You stay in control until debits and credits match exactly.

    Accounting Rule:
        Rule 11 — no account classification or balance math here; OnboardingEngine only.
    """
    if "onboarding_engine_singleton" not in st.session_state:
        st.session_state.onboarding_engine_singleton = OnboardingEngine()

    onboarding_engine = st.session_state.onboarding_engine_singleton

    st.title("Onboarding")
    st.caption(
        "Formal: First-time General Ledger setup from an opening Trial Balance. "
        "Human: Upload, review the proposed Chart, then establish the ledger when totals tie out."
    )

    st.markdown("### Danger Zone")
    st.caption(
        "Human: This wipes your local moth_and_money.db — every account and journal line. "
        "Formal: Full database reset via database.db_maintenance."
    )
    if st.session_state.pop("onboarding_danger_zone_clear_on_next_run", False):
        st.session_state.pop("onboarding_database_reset_acknowledged", None)
    user_acknowledges_full_data_loss = st.checkbox(
        "I understand this will delete all existing ledger data on this machine.",
        value=False,
        key="onboarding_database_reset_acknowledged",
    )
    if st.button(
        "Wipe ledger database",
        type="primary",
        disabled=not user_acknowledges_full_data_loss,
        width="stretch",
        key="onboarding_database_reset_execute",
    ):
        try:
            wipe_local_ledger_database()
            for session_key in (
                "onboarding_file_signature",
                "onboarding_review_grid",
                "onboarding_uploaded_name",
            ):
                st.session_state.pop(session_key, None)
            # Defer clearing checkbox key until next run (before widget bind); see Danger Zone block above.
            st.session_state["onboarding_danger_zone_clear_on_next_run"] = True
            st.success(
                "The ledger file was cleared and schema reapplied. Upload a fresh Trial Balance when you are ready."
            )
            st.rerun()
        except Exception as reset_error:
            st.error(
                "We could not finish the reset. Close any other app using this file, then try again. "
                f"Details: {reset_error!s}"
            )

    st.divider()
    st.markdown("### Upload")
    st.caption(
        "Formal: Trial Balance CSV — Full name or Account Name with Debit and Credit. "
        "Human: QuickBooks-style preamble rows are skipped automatically."
    )
    uploaded_trial_balance_file = st.file_uploader(
        "Trial Balance CSV",
        type=["csv"],
        label_visibility="visible",
        help="Use the same export you would give a tax professional; we only read structure and amounts.",
    )

    if uploaded_trial_balance_file is None:
        for session_key in ("onboarding_file_signature", "onboarding_review_grid", "onboarding_uploaded_name"):
            st.session_state.pop(session_key, None)
    else:
        file_signature = (uploaded_trial_balance_file.name, uploaded_trial_balance_file.size)
        if st.session_state.get("onboarding_file_signature") != file_signature:
            st.session_state.onboarding_file_signature = file_signature
            st.session_state.onboarding_uploaded_name = uploaded_trial_balance_file.name
            try:
                raw_bytes = uploaded_trial_balance_file.getvalue()
                raw_dataframe = OnboardingEngine.read_trial_balance_csv_bytes(raw_bytes)
                proposal_list = onboarding_engine.prepare_proposal(raw_dataframe)
                st.session_state.onboarding_review_grid = onboarding_engine.proposal_to_editor_dataframe(
                    proposal_list
                )
            except ValueError as parse_error:
                st.error(str(parse_error))
                st.session_state.pop("onboarding_review_grid", None)
            except Exception as read_error:
                st.error(
                    "This file could not be read as CSV. Save as UTF-8 CSV, then try again. "
                    f"Details: {read_error!s}"
                )
                st.session_state.pop("onboarding_review_grid", None)

    st.divider()
    st.markdown("### Review")
    st.caption(
        "Formal: Proposed chart_of_accounts mapping and opening debit/credit columns. "
        "Human: Adjust names, categories, or amounts if your export needs a light touch."
    )

    if (
        "onboarding_review_grid" in st.session_state
        and not st.session_state["onboarding_review_grid"].empty
    ):
        edited_grid = st.data_editor(
            st.session_state.onboarding_review_grid,
            width="stretch",
            num_rows="fixed",
            hide_index=True,
            column_config={
                "account_number": NumberColumn(
                    "Account number",
                    format="%d",
                    required=True,
                    help="Formal: Assigned bucket number (1000s–5000s). Human: Steps of ten per category.",
                ),
                "account_name": TextColumn("Account name", required=True),
                "account_type": SelectboxColumn(
                    "Account type",
                    options=["Asset", "Liability", "Equity", "Revenue", "Expense"],
                    required=True,
                    help="Formal: account_category / account_type. Human: Pick the bucket that matches reality.",
                ),
                "debit": NumberColumn("Debit", format="$%.2f", min_value=0.0),
                "credit": NumberColumn("Credit", format="$%.2f", min_value=0.0),
            },
            key="onboarding_trial_balance_editor",
        )
        st.session_state.onboarding_review_grid = edited_grid

        proposal_after_edits = onboarding_engine.editor_dataframe_to_proposal(edited_grid)
        total_debits, total_credits, difference_amount = onboarding_engine.posting_balance_audit(
            proposal_after_edits
        )

        st.divider()
        st.markdown("### Audit")
        st.caption(
            "Formal: Trial Balance footing check (sum Debits, sum Credits, difference). "
            "Human: Establish Ledger stays off until the difference is exactly zero."
        )
        metric_row = st.columns(3)
        with metric_row[0]:
            st.metric("Total debits", f"${total_debits:,.2f}")
        with metric_row[1]:
            st.metric("Total credits", f"${total_credits:,.2f}")
        with metric_row[2]:
            st.metric(
                "Difference",
                f"${difference_amount:,.2f}",
                help="Formal: debits minus credits. Must be zero to post.",
            )

        st.divider()
        st.markdown("### Commit")
        opening_balance_calendar_date = st.date_input(
            "Opening balance as of",
            value=date.today(),
            help="Formal: entry_date on the opening journal entry (ISO in the database). Human: Usually your Trial Balance date.",
        )

        is_balanced = onboarding_engine.validate_balances(proposal_after_edits)
        if is_balanced:
            st.success("Debits and credits match exactly — you may establish the ledger when the grid looks right.")
        else:
            st.warning(
                "Totals are not in balance. Adjust the Review grid until difference reads $0.00; the button below stays off."
            )

        establish_blocked = (
            uploaded_trial_balance_file is None
            or not is_balanced
            or st.session_state["onboarding_review_grid"].empty
        )

        if st.button(
            "🚀 Establish Ledger",
            type="primary",
            disabled=establish_blocked,
            width="stretch",
            key="onboarding_establish_ledger",
        ):
            try:
                opening_balance_date_iso = opening_balance_calendar_date.isoformat()
                source_metadata = st.session_state.get(
                    "onboarding_uploaded_name",
                    uploaded_trial_balance_file.name,
                )
                chart_count, ledger_count = onboarding_engine.commit_to_database(
                    proposal_after_edits,
                    opening_balance_date_iso=opening_balance_date_iso,
                    source_metadata=source_metadata,
                )
                st.success(
                    f"Established {chart_count} chart_of_accounts rows and "
                    f"{ledger_count} opening ledger_entries. Returning you to the Hub view."
                )
                for session_key in (
                    "onboarding_file_signature",
                    "onboarding_review_grid",
                    "onboarding_uploaded_name",
                ):
                    st.session_state.pop(session_key, None)
                st.rerun()
            except ValueError as business_error:
                st.error(str(business_error))
            except Exception as commit_error:
                st.error(
                    "Establish Ledger did not finish. Confirm the database file is not open elsewhere, then retry. "
                    f"Details: {commit_error!s}"
                )
    else:
        st.info("Upload a Trial Balance CSV above to preview the proposed Chart and balances.")
