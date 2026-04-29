import streamlit as st
import pandas
from sqlalchemy import text
from database.connection import open_database_session

def render_trial_balance_page():
    st.title("Trial Balance")
    st.caption("Formal: Verification of ledger equilibrium. Human: Making sure the math matches the bank.")

    query = text("""
        SELECT 
            coa.account_number AS "No.",
            coa.account_name AS "Account Name",
            coa.account_category AS "Category",
            CASE WHEN (SUM(le.debit_amount) - SUM(le.credit_amount)) > 0 
                 THEN ROUND(SUM(le.debit_amount) - SUM(le.credit_amount), 2) ELSE 0 END AS "Debit",
            CASE WHEN (SUM(le.credit_amount) - SUM(le.debit_amount)) > 0 
                 THEN ROUND(SUM(le.credit_amount) - SUM(le.debit_amount), 2) ELSE 0 END AS "Credit"
        FROM ledger_entries le
        JOIN chart_of_accounts coa USING (account_number)
        GROUP BY coa.account_number
        HAVING "Debit" != 0 OR "Credit" != 0
        ORDER BY coa.account_number ASC
    """)

    with open_database_session() as session:
        df = pandas.read_sql(query, session.connection())

    st.dataframe(df, width="stretch", hide_index=True)

    total_debits = df["Debit"].sum()
    total_credits = df["Credit"].sum()

    st.divider()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Debits", f"${total_debits:,.2f}")
    with col2:
        st.metric("Total Credits", f"${total_credits:,.2f}")
    with col3:
        if abs(total_debits - total_credits) < 0.01:
            st.success("✅ Ledger is Balanced")
        else:
            st.error(f"❌ Imbalance: {abs(total_debits - total_credits):,.2f}")