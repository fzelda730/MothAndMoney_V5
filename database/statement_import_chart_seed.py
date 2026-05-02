"""
MOTH AND MONEY — STATEMENT IMPORT CHART SEED
/database/statement_import_chart_seed.py

Formal:  Ensures a dedicated balancing bucket exists for bank statement imports.
Human:   Posts stay double-entry while you reclassify from clearing later.

Accounting Rule:
    Expense 5890 is Debit-normal; used only as the paired leg during import.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from database.chart_of_accounts_repository import (
    account_number_exists_in_chart,
    insert_chart_account_row,
)

STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER = 5890


def ensure_statement_import_clearing_account(database_session: Session) -> None:
    """
    Formal:  Idempotently inserts chart_of_accounts 5890 when missing.
    Human:   Your statement lines always have a balancing home in the ledger.

    Accounting Rule:
        One clearing bucket shared by every CSV/PDF driver in this forge slice.
    """
    if account_number_exists_in_chart(
        database_session, STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER
    ):
        return
    insert_chart_account_row(
        database_session,
        account_number=STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER,
        account_name="Statement import clearing",
        account_category="Expense",
        normal_balance="Debit",
        account_description=(
            "Automatic balancing leg for bank statement imports — reclassify as you go."
        ),
        is_active=1,
    )
