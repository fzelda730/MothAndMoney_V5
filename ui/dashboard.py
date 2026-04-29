"""
MOTH AND MONEY — DASHBOARD PAGE
ui/dashboard.py

Formal:  Renders the executive summary view — total assets, total liabilities,
         net value, and a current cash liquidity table — sourced from the live ledger.
Human:   Your financial snapshot. Three numbers and your top cash accounts,
         pulled fresh from the database every time you open this page.
"""

from __future__ import annotations

from decimal import Decimal

import pandas
import streamlit as st
from sqlalchemy import text

from database.connection import open_database_session


# ---------------------------------------------------------------------------
# Data-fetching functions (pure — no st calls)
# ---------------------------------------------------------------------------

def fetch_total_assets_balance() -> Decimal:
    """
    Formal:  Returns the net balance of all Asset accounts (1000–1999).
    Human:   Everything you own, added up.
    """
    query = text("""
        SELECT COALESCE(SUM(debit_amount) - SUM(credit_amount), 0)
        FROM ledger_entries
        WHERE account_number >= 1000 AND account_number < 2000
    """)
    with open_database_session() as accounting_session:
        result = accounting_session.execute(query).scalar()
    return Decimal(str(result))


def fetch_total_liabilities_balance() -> Decimal:
    """
    Formal:  Returns the net balance of all Liability accounts (2000–2999).
    Human:   Everything you owe, added up.
    """
    query = text("""
        SELECT COALESCE(SUM(credit_amount) - SUM(debit_amount), 0)
        FROM ledger_entries
        WHERE account_number >= 2000 AND account_number < 3000
    """)
    with open_database_session() as accounting_session:
        result = accounting_session.execute(query).scalar()
    return Decimal(str(result))


def fetch_current_cash_liquidity_table() -> pandas.DataFrame:
    """
    Formal:  Returns the top 5 non-zero cash accounts (1000–1099) sorted
             by net balance descending.
    Human:   Your most liquid "money fortress" accounts, ranked by size.
    """
    query = text("""
        SELECT coa.account_name      AS "Account",
               ROUND(SUM(le.debit_amount) - SUM(le.credit_amount), 2) AS "Balance"
        FROM ledger_entries le
        JOIN chart_of_accounts coa USING (account_number)
        WHERE le.account_number >= 1000 AND le.account_number < 1100
        GROUP BY le.account_number, coa.account_name
        HAVING "Balance" != 0
        ORDER BY "Balance" DESC
        LIMIT 5
    """)
    with open_database_session() as accounting_session:
        rows = accounting_session.execute(query).fetchall()
    return pandas.DataFrame(rows, columns=["Account", "Balance"])


# ---------------------------------------------------------------------------
# Display function (UI only — no raw SQL)
# ---------------------------------------------------------------------------

def render_dashboard_page() -> None:
    """
    Formal:  Renders the Dashboard page with three stat cards and a
             current cash liquidity table.
    Human:   Shows the big three numbers and your top cash accounts.
    """
    st.title("Dashboard")
    st.caption("Your financial fortress — live from the ledger.")

    total_assets      = fetch_total_assets_balance()
    total_liabilities = fetch_total_liabilities_balance()
    net_value         = total_assets - total_liabilities

    asset_column, liability_column, net_value_column = st.columns(3)

    with asset_column:
        st.metric(
            label="Total Assets",
            value=f"${total_assets:,.2f}",
            help="Sum of all 1000-series accounts. Formal: Net debit balance of Asset accounts."
        )
    with liability_column:
        st.metric(
            label="Total Liabilities",
            value=f"${total_liabilities:,.2f}",
            help="Sum of all 2000-series accounts. Formal: Net credit balance of Liability accounts."
        )
    with net_value_column:
        st.metric(
            label="Net Value",
            value=f"${net_value:,.2f}",
            help="Assets minus Liabilities. Formal: Owner's economic interest in the business."
        )

    st.divider()
    st.subheader("Current Cash — Top 5 Liquidity Accounts")
    st.caption("Accounts 1000–1099 with a non-zero balance, ranked by size.")

    liquidity_dataframe = fetch_current_cash_liquidity_table()
    if liquidity_dataframe.empty:
        st.info("No cash balances found. Run logic.seeding and logic.initial_funding first.")
    else:
        st.dataframe(
            liquidity_dataframe,
            width="stretch",
            hide_index=True,
        )
