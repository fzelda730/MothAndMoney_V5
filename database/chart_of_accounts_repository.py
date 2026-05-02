"""
MOTH AND MONEY — CHART OF ACCOUNTS (DATABASE READ/WRITE)
/database/chart_of_accounts_repository.py

Formal:  Parameterized SQL for chart_of_accounts existence checks, inserts, and listing.
Human:   Thin data access only — business rules live in logic.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_ACCOUNT_NUMBER_EXISTS_QUERY = text("""
    SELECT 1 AS present
    FROM chart_of_accounts
    WHERE account_number = :account_number
    LIMIT 1
""")

_INSERT_CHART_ROW = text("""
    INSERT INTO chart_of_accounts (
        account_number,
        account_name,
        account_category,
        normal_balance,
        account_description,
        is_active
    )
    VALUES (
        :account_number,
        :account_name,
        :account_category,
        :normal_balance,
        :account_description,
        :is_active
    )
""")

_SELECT_CHART_ORDERED = text("""
    SELECT
        account_number,
        account_name,
        account_category,
        normal_balance,
        account_description,
        is_active
    FROM chart_of_accounts
    ORDER BY account_number ASC
""")


def account_number_exists_in_chart(database_session: Session, account_number: int) -> bool:
    """
    Formal:  Returns True when chart_of_accounts already holds this account_number.
    Human:   Stops duplicate money buckets before INSERT.
    """
    row = database_session.execute(
        _ACCOUNT_NUMBER_EXISTS_QUERY, {"account_number": int(account_number)}
    ).fetchone()
    return row is not None


def insert_chart_account_row(
    database_session: Session,
    *,
    account_number: int,
    account_name: str,
    account_category: str,
    normal_balance: str,
    account_description: str | None,
    is_active: int,
) -> None:
    """
    Formal:  Inserts one chart_of_accounts row (caller validated uniqueness and bands).
    Human:   Adds a new bucket to the Map.
    """
    database_session.execute(
        _INSERT_CHART_ROW,
        {
            "account_number": int(account_number),
            "account_name": account_name,
            "account_category": account_category,
            "normal_balance": normal_balance,
            "account_description": account_description,
            "is_active": int(is_active),
        },
    )


def fetch_all_chart_accounts_ordered(database_session: Session) -> list[dict]:
    """
    Formal:  Returns all chart rows ordered by account_number for display or export.
    Human:   Full list for Settings review.
    """
    result = database_session.execute(_SELECT_CHART_ORDERED)
    return [dict(row._mapping) for row in result.fetchall()]


_SELECT_ACTIVE_CHART_ORDERED = text("""
    SELECT
        account_number,
        account_name,
        account_category,
        normal_balance,
        account_description,
        is_active
    FROM chart_of_accounts
    WHERE is_active = 1
    ORDER BY account_number ASC
""")


def fetch_active_chart_accounts_ordered(database_session: Session) -> list[dict]:
    """
    Formal:  Returns active chart rows for pickers (statement templates, ingest).
    Human:   Only accounts you can still post to.
    """
    result = database_session.execute(_SELECT_ACTIVE_CHART_ORDERED)
    return [dict(row._mapping) for row in result.fetchall()]
