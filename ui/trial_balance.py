import streamlit as st
import pandas
from sqlalchemy import text

from database.connection import open_database_session
from logic.currency_presentation import format_currency_standard_us

def render_trial_balance_page():
    st.title("Trial Balance")
    st.caption(
        "Formal: Full active chart with net Debit/Credit columns from the ledger. "
        "Human: Every open account shows up — zeros mean no net activity yet."
    )

    query = text("""
        SELECT 
            coa.account_number AS "No.",
            coa.account_name AS "Account Name",
            coa.account_category AS "Category",
            CASE WHEN (COALESCE(SUM(le.debit_amount), 0) - COALESCE(SUM(le.credit_amount), 0)) > 0 
                 THEN ROUND(
                     COALESCE(SUM(le.debit_amount), 0) - COALESCE(SUM(le.credit_amount), 0), 2
                 ) ELSE 0 END AS "Debit",
            CASE WHEN (COALESCE(SUM(le.credit_amount), 0) - COALESCE(SUM(le.debit_amount), 0)) > 0 
                 THEN ROUND(
                     COALESCE(SUM(le.credit_amount), 0) - COALESCE(SUM(le.debit_amount), 0), 2
                 ) ELSE 0 END AS "Credit"
        FROM chart_of_accounts coa
        LEFT JOIN ledger_entries le ON le.account_number = coa.account_number
        WHERE coa.is_active = 1
        GROUP BY coa.account_number, coa.account_name, coa.account_category
        ORDER BY coa.account_number ASC
    """)

    with open_database_session() as session:
        trial_balance_report_dataframe = pandas.read_sql(query, session.connection())

    trial_balance_display_dataframe = trial_balance_report_dataframe.copy()

    def trial_balance_money_cell(ledger_side_amount) -> str:
        if pandas.isna(ledger_side_amount):
            return ""
        return format_currency_standard_us(ledger_side_amount)

    trial_balance_display_dataframe["Debit"] = trial_balance_display_dataframe["Debit"].apply(
        trial_balance_money_cell
    )
    trial_balance_display_dataframe["Credit"] = trial_balance_display_dataframe[
        "Credit"
    ].apply(trial_balance_money_cell)

    st.dataframe(
        trial_balance_display_dataframe,
        width="stretch",
        hide_index=True,
        column_config={
            "No.": st.column_config.NumberColumn(
                "No.",
                format="%d",
            ),
            "Debit": st.column_config.TextColumn("Debit"),
            "Credit": st.column_config.TextColumn("Credit"),
        },
    )

    total_debits = trial_balance_report_dataframe["Debit"].sum()
    total_credits = trial_balance_report_dataframe["Credit"].sum()

    st.divider()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Debits", format_currency_standard_us(total_debits))
    with col2:
        st.metric("Total Credits", format_currency_standard_us(total_credits))
    with col3:
        if abs(total_debits - total_credits) < 0.01:
            st.success("✅ Ledger is Balanced")
        else:
            st.error(
                f"❌ Imbalance: {format_currency_standard_us(abs(total_debits - total_credits))}"
            )