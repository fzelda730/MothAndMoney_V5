"""
MOTH AND MONEY — PAYEE CHART ACCOUNT MAPPING (DATABASE)
/database/payee_chart_account_mapping_repository.py

Formal:  CRUD for payee_chart_account_mappings — normalized payee key to offset chart account.
Human:   Remembers what you picked on Statement Upload so the next file can pre-fill.

Accounting Rule:
    One mapping per normalized payee string; FK ensures the target account exists in the chart.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_SELECT_ALL = text("""
    SELECT payee_normalized_key, account_number
    FROM payee_chart_account_mappings
""")

_UPSERT = text("""
    INSERT INTO payee_chart_account_mappings
        (payee_normalized_key, account_number, created_at, updated_at)
    VALUES
        (:payee_normalized_key, :account_number, datetime('now'), datetime('now'))
    ON CONFLICT(payee_normalized_key) DO UPDATE SET
        account_number = excluded.account_number,
        updated_at = datetime('now')
""")

_DELETE = text("""
    DELETE FROM payee_chart_account_mappings
    WHERE payee_normalized_key = :payee_normalized_key
""")


def fetch_payee_normalized_key_to_account_number(
    database_session: Session,
) -> dict[str, int]:
    """
    Formal:  Returns every saved mapping as dict[payee_normalized_key] -> account_number.
    Human:   The whole payee memory file in one read for classification.
    """
    result_rows = database_session.execute(_SELECT_ALL).fetchall()
    return {str(row[0]): int(row[1]) for row in result_rows}


def upsert_payee_chart_account_mapping(
    database_session: Session,
    *,
    payee_normalized_key: str,
    account_number: int,
) -> None:
    """
    Formal:  Inserts or replaces the offset account for this normalized payee key.
    Human:   Teach the forge that this merchant belongs in that bucket.
    """
    database_session.execute(
        _UPSERT,
        {
            "payee_normalized_key": str(payee_normalized_key).strip(),
            "account_number": int(account_number),
        },
    )


def delete_payee_chart_account_mapping(
    database_session: Session,
    *,
    payee_normalized_key: str,
) -> None:
    """
    Formal:  Removes a mapping row when the owner chooses clearing-only classification.
    Human:   Forgets this payee so the next import starts unclassified again.
    """
    database_session.execute(
        _DELETE,
        {"payee_normalized_key": str(payee_normalized_key).strip()},
    )
