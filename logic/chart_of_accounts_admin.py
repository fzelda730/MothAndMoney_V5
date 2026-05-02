"""
MOTH AND MONEY — CHART OF ACCOUNTS (ADMIN LOGIC)
/logic/chart_of_accounts_admin.py

Formal:  Validation and orchestration for adding accounts outside onboarding.
Human:   Keeps numbering bands aligned with your 1000s–5000s map before SQL runs.

Human-Readable Summary:
    Band check, normal side from category, duplicate check, then one committed INSERT.
"""

from __future__ import annotations

import pandas

from database.chart_of_accounts_repository import (
    account_number_exists_in_chart,
    fetch_all_chart_accounts_ordered,
    insert_chart_account_row,
)
from database.connection import open_database_session

_ALLOWED_ACCOUNT_CATEGORIES: tuple[str, ...] = (
    "Asset",
    "Liability",
    "Equity",
    "Revenue",
    "Expense",
)

_THOUSAND_BAND_TO_CATEGORY: dict[int, str] = {
    1000: "Asset",
    2000: "Liability",
    3000: "Equity",
    4000: "Revenue",
    5000: "Expense",
}


def normal_balance_for_category(account_category: str) -> str:
    """
    Formal:  Returns Debit or Credit normal_balance for chart_of_accounts.
    Human:   Matches what your accountant expects for each account_category.

    Accounting Rule:
        Asset and Expense carry a debit normal balance; liability, equity, revenue credit.
    """
    if account_category in ("Asset", "Expense"):
        return "Debit"
    if account_category in ("Liability", "Equity", "Revenue"):
        return "Credit"
    raise ValueError(
        f"Unknown account_category {account_category!r}. "
        "Use Asset, Liability, Equity, Revenue, or Expense."
    )


def _validate_band_matches_category(account_number: int, account_category: str) -> None:
    band = (int(account_number) // 1000) * 1000
    if band not in _THOUSAND_BAND_TO_CATEGORY:
        raise ValueError(
            "Account number must sit in the standard bands: "
            "1000–1999 (Asset), 2000–2999 (Liability), 3000–3999 (Equity), "
            "4000–4999 (Revenue), 5000–5999 (Expense)."
        )
    expected_category = _THOUSAND_BAND_TO_CATEGORY[band]
    if account_category != expected_category:
        raise ValueError(
            f"That number is in the {expected_category} range (starts with {band // 1000}), "
            f"but you chose {account_category}. Pick a number that matches the category, "
            "or change the category."
        )


def validate_new_chart_account_inputs(
    *,
    account_number: int,
    account_name: str,
    account_category: str,
    is_active: int,
) -> None:
    """
    Formal:  Raises ValueError when inputs are not ready for INSERT.
    Human:   Plain-language gate before touching the database.
    """
    name_stripped = str(account_name).strip()
    if name_stripped == "":
        raise ValueError("Account name cannot be empty.")

    if account_category not in _ALLOWED_ACCOUNT_CATEGORIES:
        raise ValueError(
            "Account category must be one of: "
            "Asset, Liability, Equity, Revenue, Expense."
        )

    if int(is_active) not in (0, 1):
        raise ValueError("is_active must be 0 or 1.")

    _validate_band_matches_category(account_number, account_category)
    _ = normal_balance_for_category(account_category)


def add_chart_account_to_database(
    *,
    account_number: int,
    account_name: str,
    account_category: str,
    account_description: str | None,
    is_active: int,
) -> None:
    """
    Formal:  One transaction: validate, reject duplicates, INSERT chart_of_accounts.
    Human:   Adds a new account with no ledger lines until you post activity.

    Accounting Rule:
        chart_of_accounts row only; balances stay zero until journal_entries post.
    """
    name_stripped = str(account_name).strip()
    description_stripped = (
        None
        if account_description is None or str(account_description).strip() == ""
        else str(account_description).strip()
    )

    validate_new_chart_account_inputs(
        account_number=account_number,
        account_name=name_stripped,
        account_category=account_category,
        is_active=is_active,
    )

    normal_balance = normal_balance_for_category(account_category)

    with open_database_session() as database_session:
        if account_number_exists_in_chart(database_session, account_number):
            raise ValueError(
                "This account number is already on your chart. Pick a different number "
                "or retire the existing account first."
            )
        insert_chart_account_row(
            database_session,
            account_number=account_number,
            account_name=name_stripped,
            account_category=account_category,
            normal_balance=normal_balance,
            account_description=description_stripped,
            is_active=is_active,
        )


def load_chart_of_accounts_table_dataframe() -> pandas.DataFrame:
    """
    Formal:  Read-only chart listing for Settings display.
    Human:   Scroll the full map before adding another line.
    """
    with open_database_session() as database_session:
        rows = fetch_all_chart_accounts_ordered(database_session)
    return pandas.DataFrame(rows)
