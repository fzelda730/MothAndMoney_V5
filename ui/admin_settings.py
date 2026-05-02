"""
MOTH AND MONEY — ADMIN / SETTINGS (UI)
/ui/admin_settings.py

Formal:  Ledger administration: add chart_of_accounts rows, destructive reset,
         and pointers when the chart is empty.
Human:   Grow the Map or restart the file—without scattering SQL in the layout.
"""

from __future__ import annotations

import streamlit as st

from database.db_maintenance import wipe_local_ledger_database
from database.sqlite_lifecycle import count_chart_of_accounts_rows
from logic.chart_of_accounts_admin import (
    add_chart_account_to_database,
    load_chart_of_accounts_table_dataframe,
    normal_balance_for_category,
)


def render_admin_settings_page() -> None:
    """
    Formal:  Renders Settings / Admin after chart_of_accounts exists: chart add form,
             current chart table, Danger Zone reset.
    Human:   When you need a new bucket or a full wipe, open this room.

    Accounting Rule:
        Add-account posts chart rows only; balances stay zero until journals post.
    """
    st.title("Settings / Admin")
    st.caption(
        "Formal: Ledger administration. Human: Add accounts here or restart your local database."
    )

    st.markdown("### Chart of accounts — add account")
    st.caption(
        "Formal: New chart_of_accounts row (1000s–5000s). Human: Another money bucket for "
        "future activity — balance stays at zero until you post to the ledger."
    )

    try:
        chart_accounts_display_dataframe = load_chart_of_accounts_table_dataframe()
    except Exception as load_error:
        chart_accounts_display_dataframe = None
        st.warning(
            "We could not load the chart for display. Check your database file. "
            f"Details: {load_error!s}"
        )

    if chart_accounts_display_dataframe is not None and not chart_accounts_display_dataframe.empty:
        st.dataframe(
            chart_accounts_display_dataframe,
            width="stretch",
            hide_index=True,
            column_config={
                "account_number": st.column_config.NumberColumn("Account number", format="%d"),
                "account_name": st.column_config.TextColumn("Account name"),
                "account_category": st.column_config.TextColumn("Account category"),
                "normal_balance": st.column_config.TextColumn("Normal balance"),
                "account_description": st.column_config.TextColumn(
                    "Account description",
                ),
                "is_active": st.column_config.NumberColumn("Active (1=yes)", format="%d"),
            },
        )
    elif chart_accounts_display_dataframe is not None:
        st.info("Your chart is empty in the database; use Onboarding if you need a full Trial Balance.")

    with st.form("admin_settings_add_chart_account_form", clear_on_submit=False):
        field_columns = st.columns(2)
        with field_columns[0]:
            new_account_number = st.number_input(
                "Account number",
                min_value=1000,
                max_value=9999,
                value=1000,
                step=10,
                help="Formal: unique key. Human: Keep inside 1000s–5000s for your category.",
            )
        with field_columns[1]:
            new_account_category = st.selectbox(
                "Account category",
                options=["Asset", "Liability", "Equity", "Revenue", "Expense"],
                index=0,
                help="Formal: Asset | Liability | Equity | Revenue | Expense.",
            )

        normal_side = normal_balance_for_category(new_account_category)
        st.caption(
            f"Formal: Normal balance for this category is {normal_side}. "
            f"Human: That is the side where this bucket “expects” growth when things are healthy."
        )

        new_account_name = st.text_input(
            "Account name",
            placeholder="e.g. Petty cash — studio",
            help="Formal: account_name on the chart. Human: What you will look for in reports.",
        )
        new_account_description = st.text_area(
            "Account description (optional)",
            placeholder="What this bucket is for",
            help="Formal: optional account_description. Human: One line for Future-You.",
        )
        new_account_is_active = st.checkbox(
            "Account is active",
            value=True,
            help="Formal: is_active = 1 keeps the account open for posting.",
        )

        submitted = st.form_submit_button("Add account to chart", type="primary", width="stretch")

    if submitted:
        try:
            add_chart_account_to_database(
                account_number=int(new_account_number),
                account_name=new_account_name,
                account_category=new_account_category,
                account_description=new_account_description or None,
                is_active=1 if new_account_is_active else 0,
            )
            st.success(
                f"Added account {int(new_account_number)} — {new_account_name.strip() or '(named)'} "
                "to the chart. You can post to it when you record the next journal."
            )
            st.rerun()
        except ValueError as validation_message:
            st.error(str(validation_message))
        except Exception as insert_error:
            st.error(
                "We could not save this account. Confirm the database is not locked elsewhere. "
                f"Details: {insert_error!s}"
            )

    st.divider()
    st.markdown("### Danger Zone")
    st.caption(
        "Human: This permanently deletes every journal line and account in your "
        "local moth_and_money.db file — use only when you want a clean slate."
    )
    if st.session_state.pop("admin_settings_danger_zone_clear_on_next_run", False):
        st.session_state.pop("admin_settings_database_reset_acknowledged", None)
    user_acknowledges_full_data_loss = st.checkbox(
        "I understand this will wipe all existing data.",
        value=False,
        key="admin_settings_database_reset_acknowledged",
    )
    if st.button(
        "Reset Database",
        type="primary",
        disabled=not user_acknowledges_full_data_loss,
        width="stretch",
        key="admin_settings_database_reset_execute",
    ):
        try:
            wipe_local_ledger_database()
            st.session_state["admin_settings_danger_zone_clear_on_next_run"] = True
            st.success(
                "The database file was cleared and the schema was recreated. "
                "When your chart is empty, use Onboarding from the main Moth and Money view to import a Trial Balance again."
            )
            st.rerun()
        except Exception as reset_error:
            st.error(
                "We could not finish resetting the database. Close any other "
                f"app using this file, then try again. Details: {reset_error!s}"
            )

    st.divider()
    st.markdown("### After a reset")
    chart_row_total = count_chart_of_accounts_rows()
    if chart_row_total == 0:
        st.info(
            "Your chart_of_accounts is empty. The main Moth and Money view will show "
            "Onboarding next — upload your Trial Balance there to establish the ledger again."
        )
    else:
        st.caption(
            "Human: Reset above clears all accounts and journals; you will see "
            "Onboarding again until you establish the ledger from a Trial Balance."
        )
