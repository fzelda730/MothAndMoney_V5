"""
MOTH AND MONEY — BANK TEMPLATE CHART LINKS (DATABASE)
/database/bank_template_chart_links_repository.py

Formal:  SQL for optional many-to-many between bank_templates.id and chart_of_accounts.
Human:   Short list of allowed posting accounts on Statement Upload for a CSV map or built-in PDF driver.

Accounting Rule:
    Deleting a template row cascades; account_number must exist on chart_of_accounts.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_DELETE_LINKS_FOR_TEMPLATE = text("""
    DELETE FROM bank_template_chart_links
    WHERE bank_template_id = :bank_template_id
""")

_INSERT_LINK = text("""
    INSERT INTO bank_template_chart_links (bank_template_id, account_number)
    VALUES (:bank_template_id, :account_number)
""")

_SELECT_ACCOUNT_NUMBERS_ORDERED = text("""
    SELECT account_number
    FROM bank_template_chart_links
    WHERE bank_template_id = :bank_template_id
    ORDER BY account_number ASC
""")


def list_linked_account_numbers_for_template(
    database_session: Session, *, bank_template_id: int
) -> list[int]:
    """
    Formal:  Returns chart account numbers linked to this template, ascending.
    Human:   Empty list means “any active account” on Statement Upload.

    Accounting Rule:
        Returns integers that exist in chart_of_accounts per FK.
    """
    result = database_session.execute(
        _SELECT_ACCOUNT_NUMBERS_ORDERED, {"bank_template_id": int(bank_template_id)}
    )
    return [int(row[0]) for row in result.fetchall()]


def replace_linked_account_numbers_for_template(
    database_session: Session,
    *,
    bank_template_id: int,
    account_numbers: list[int],
) -> None:
    """
    Formal:  Replaces all links for a template with the given account numbers (deduped).
    Human:   Save in Template Manager after multiselect.

    Accounting Rule:
        Caller must ensure template id exists and template is csv_headers in logic;
        chart rows must exist or INSERT fails on FK.
    """
    unique_sorted = sorted({int(account_number) for account_number in account_numbers})

    database_session.execute(
        _DELETE_LINKS_FOR_TEMPLATE, {"bank_template_id": int(bank_template_id)}
    )
    for account_number in unique_sorted:
        database_session.execute(
            _INSERT_LINK,
            {
                "bank_template_id": int(bank_template_id),
                "account_number": int(account_number),
            },
        )
