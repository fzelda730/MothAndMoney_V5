"""
MOTH AND MONEY — GENERAL LEDGER (DATABASE)
/database/general_ledger_repository.py

Formal:  Parameterized SQL for chart bands, opening nets, and period ledger lines.
Human:   One place to read what the General Ledger needs from moth_and_money.db.

Accounting Rule:
    Opening uses journals strictly before period start; activity is inclusive in [start, end].
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

_MIN_MAX_ACTIVE = text("""
    SELECT MIN(account_number) AS band_low, MAX(account_number) AS band_high
    FROM chart_of_accounts
    WHERE is_active = 1
""")

_JOURNAL_ENTRY_DATE_BOUNDS = text("""
    SELECT
        MIN(entry_date) AS earliest_entry_date_iso,
        MAX(entry_date) AS latest_entry_date_iso
    FROM journal_entries
""")

_CHART_IN_BAND = text("""
    SELECT
        account_number,
        account_name,
        account_category,
        normal_balance,
        is_active
    FROM chart_of_accounts
    WHERE is_active = 1
      AND account_number >= :account_number_low
      AND account_number <= :account_number_high
    ORDER BY account_number ASC
""")

_OPENING_NET_BY_ACCOUNT = text("""
    SELECT
        ledger_line.account_number,
        COALESCE(SUM(ledger_line.debit_amount - ledger_line.credit_amount), 0)
            AS opening_net_debit_minus_credit
    FROM ledger_entries AS ledger_line
    INNER JOIN journal_entries AS journal_header
        ON journal_header.journal_entry_id = ledger_line.journal_entry_id
    WHERE ledger_line.account_number >= :account_number_low
      AND ledger_line.account_number <= :account_number_high
      AND journal_header.entry_date < :period_start_exclusive_iso
    GROUP BY ledger_line.account_number
""")

_PERIOD_LINES = text("""
    SELECT
        journal_header.entry_date AS entry_date_iso,
        journal_header.journal_entry_id AS journal_entry_id,
        journal_header.entry_description AS entry_description,
        journal_header.source_metadata AS source_metadata,
        ledger_line.ledger_entry_id AS ledger_entry_id,
        ledger_line.account_number AS account_number,
        ledger_line.debit_amount AS debit_amount,
        ledger_line.credit_amount AS credit_amount,
        ledger_line.payee AS payee,
        ledger_line.reference AS reference
    FROM ledger_entries AS ledger_line
    INNER JOIN journal_entries AS journal_header
        ON journal_header.journal_entry_id = ledger_line.journal_entry_id
    WHERE ledger_line.account_number >= :account_number_low
      AND ledger_line.account_number <= :account_number_high
      AND journal_header.entry_date >= :period_start_inclusive_iso
      AND journal_header.entry_date <= :period_end_inclusive_iso
    ORDER BY
        journal_header.entry_date ASC,
        journal_header.journal_entry_id ASC,
        ledger_line.ledger_entry_id ASC
""")


def fetch_journal_entry_date_iso_bounds(
    database_session: Session,
) -> tuple[str | None, str | None]:
    """
    Formal:  Min and max journal_entries.entry_date (ISO strings) in the ledger file.
    Human:   General Ledger defaults so statement months are not hidden behind “this month.”
    """
    row = database_session.execute(_JOURNAL_ENTRY_DATE_BOUNDS).fetchone()
    if row is None:
        return None, None
    mapping = dict(row._mapping)
    earliest = mapping.get("earliest_entry_date_iso")
    latest = mapping.get("latest_entry_date_iso")
    if earliest is None or latest is None:
        return None, None
    return str(earliest).strip(), str(latest).strip()


def fetch_active_account_number_bounds(
    database_session: Session,
) -> tuple[int | None, int | None]:
    """
    Formal:  Min and max active chart account_number values; None when chart is empty.
    Human:   Powers the "All accounts" shortcut without typing band endpoints.
    """
    row = database_session.execute(_MIN_MAX_ACTIVE).fetchone()
    if row is None or row[0] is None:
        return None, None
    return int(row[0]), int(row[1])


def fetch_chart_accounts_in_number_band(
    database_session: Session,
    *,
    account_number_low: int,
    account_number_high: int,
) -> list[dict]:
    """
    Formal:  Active chart rows whose account_number lies in [low_high] inclusive.
    Human:   The account headings the GL will print for this report.
    """
    result_rows = database_session.execute(
        _CHART_IN_BAND,
        {
            "account_number_low": int(account_number_low),
            "account_number_high": int(account_number_high),
        },
    ).fetchall()
    return [dict(row._mapping) for row in result_rows]


def fetch_opening_net_debit_minus_credit_by_account(
    database_session: Session,
    *,
    account_number_low: int,
    account_number_high: int,
    period_start_exclusive_iso: str,
) -> dict[int, Decimal]:
    """
    Formal:  Per-account SUM(debit - credit) for lines on journals before period_start.
    Human:   The beginning balance driver in algebraic form (debit minus credit).

    Accounting Rule:
        period_start_exclusive_iso is first day of the report — everything before counts toward opening.
    """
    result_rows = database_session.execute(
        _OPENING_NET_BY_ACCOUNT,
        {
            "account_number_low": int(account_number_low),
            "account_number_high": int(account_number_high),
            "period_start_exclusive_iso": str(period_start_exclusive_iso).strip(),
        },
    ).fetchall()
    return {
        int(row._mapping["account_number"]): Decimal(
            str(row._mapping["opening_net_debit_minus_credit"])
        )
        for row in result_rows
    }


def fetch_period_ledger_line_rows_for_general_ledger(
    database_session: Session,
    *,
    account_number_low: int,
    account_number_high: int,
    period_start_inclusive_iso: str,
    period_end_inclusive_iso: str,
) -> list[dict]:
    """
    Formal:  Ledger lines in the account band dated inside the inclusive window.
    Human:   Every posting row that belongs on the GL body for this period.

    Accounting Rule:
        Ordered by date, journal, ledger line for stable running balance.
    """
    result_rows = database_session.execute(
        _PERIOD_LINES,
        {
            "account_number_low": int(account_number_low),
            "account_number_high": int(account_number_high),
            "period_start_inclusive_iso": str(period_start_inclusive_iso).strip(),
            "period_end_inclusive_iso": str(period_end_inclusive_iso).strip(),
        },
    ).fetchall()
    return [dict(row._mapping) for row in result_rows]
