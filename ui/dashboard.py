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
from database.statement_import_chart_seed import (
    STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER,
)
from logic.currency_presentation import format_currency_standard_us


def format_last_statement_date_for_dashboard(raw_value: object) -> str:
    """
    Formal:  Presents journal `entry_date` text in the liquidity table, or an em dash when
             no statement import has posted to that account.
    Human:   A clean date cell so you can see at a glance how fresh each bucket is.
    Accounting Rule: Presentation only — does not change ledger data.
    """
    if raw_value is None or (isinstance(raw_value, float) and pandas.isna(raw_value)):
        return "—"
    return str(raw_value).strip()


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
             by net balance descending, plus the latest journal entry_date for
             statement imports (journal lines pairing the account with
             statement-import clearing).
    Human:   Your biggest cash buckets and when each last received a posted
             bank statement.
    """
    query = text("""
        WITH cash_balances AS (
            SELECT
                ledger_line.account_number,
                chart.account_name,
                ROUND(SUM(ledger_line.debit_amount) - SUM(ledger_line.credit_amount), 2)
                    AS account_balance
            FROM ledger_entries AS ledger_line
            JOIN chart_of_accounts AS chart USING (account_number)
            WHERE ledger_line.account_number >= 1000 AND ledger_line.account_number < 1100
            GROUP BY ledger_line.account_number, chart.account_name
            HAVING account_balance != 0
        ),
        ranked_cash AS (
            SELECT
                account_number,
                account_name,
                account_balance,
                ROW_NUMBER() OVER (ORDER BY account_balance DESC) AS liquidity_rank
            FROM cash_balances
        ),
        last_statement_by_account AS (
            SELECT
                bank_line.account_number,
                MAX(journal.entry_date) AS last_statement_date
            FROM journal_entries AS journal
            INNER JOIN ledger_entries AS bank_line
                ON bank_line.journal_entry_id = journal.journal_entry_id
            INNER JOIN ledger_entries AS clearing_line
                ON clearing_line.journal_entry_id = journal.journal_entry_id
                AND clearing_line.account_number = :statement_import_clearing_account_number
            WHERE bank_line.account_number >= 1000 AND bank_line.account_number < 1100
            GROUP BY bank_line.account_number
        )
        SELECT
            ranked_cash.account_name AS "Account",
            ranked_cash.account_balance AS "Balance",
            last_statement_by_account.last_statement_date AS "Last statement date"
        FROM ranked_cash
        LEFT JOIN last_statement_by_account
            ON last_statement_by_account.account_number = ranked_cash.account_number
        WHERE ranked_cash.liquidity_rank <= 5
        ORDER BY ranked_cash.liquidity_rank
    """)
    with open_database_session() as accounting_session:
        row_mappings = accounting_session.execute(
            query,
            {
                "statement_import_clearing_account_number": STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER,
            },
        ).mappings().all()
    return pandas.DataFrame(row_mappings)


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
            value=format_currency_standard_us(total_assets),
            help="Sum of all 1000-series accounts. Formal: Net debit balance of Asset accounts."
        )
    with liability_column:
        st.metric(
            label="Total Liabilities",
            value=format_currency_standard_us(total_liabilities),
            help="Sum of all 2000-series accounts. Formal: Net credit balance of Liability accounts."
        )
    with net_value_column:
        st.metric(
            label="Net Value",
            value=format_currency_standard_us(net_value),
            help="Assets minus Liabilities. Formal: Owner's economic interest in the business."
        )

    st.divider()
    st.subheader("Current Cash — Top 5 Liquidity Accounts")
    st.caption(
        "Accounts 1000–1099 with a non-zero balance, ranked by size. "
        "Last statement date is the newest posted statement import that hit this account."
    )

    liquidity_dataframe = fetch_current_cash_liquidity_table()
    if liquidity_dataframe.empty:
        st.info(
            "No cash balances found yet. If you just opened the app, finish Onboarding "
            "with a balanced Trial Balance so cash accounts post to the ledger."
        )
    else:
        cash_liquidity_display_dataframe = liquidity_dataframe.copy()
        cash_liquidity_display_dataframe["Balance"] = cash_liquidity_display_dataframe[
            "Balance"
        ].apply(format_currency_standard_us)

        cash_liquidity_display_dataframe["Last statement date"] = (
            cash_liquidity_display_dataframe["Last statement date"].apply(
                format_last_statement_date_for_dashboard
            )
        )
        st.dataframe(
            cash_liquidity_display_dataframe,
            width="stretch",
            hide_index=True,
            column_config={
                "Account": st.column_config.TextColumn("Account"),
                "Balance": st.column_config.TextColumn("Balance"),
                "Last statement date": st.column_config.TextColumn(
                    "Last statement date"
                ),
            },
        )
