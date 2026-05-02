"""
MOTH AND MONEY — BANK TEMPLATES (DATABASE)
/database/bank_templates_repository.py

Formal:  SQL for bank_templates CSV maps and built-in ingest registry rows.
Human:   Thin data access — mapping rules live in logic.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_INSERT_BANK_TEMPLATE = text("""
    INSERT INTO bank_templates (
        name,
        linked_account_number,
        date_col,
        payee_col,
        amount_col,
        reference_col,
        is_liability,
        ingest_kind,
        built_in_parser_key
    )
    VALUES (
        :name,
        :linked_account_number,
        :date_col,
        :payee_col,
        :amount_col,
        :reference_col,
        :is_liability,
        :ingest_kind,
        :built_in_parser_key
    )
""")

_FETCH_TEMPLATE_BY_PRIMARY_KEY = text("""
    SELECT
        id,
        name,
        linked_account_number,
        date_col,
        payee_col,
        amount_col,
        reference_col,
        is_liability,
        ingest_kind,
        built_in_parser_key,
        created_at
    FROM bank_templates
    WHERE id = :bank_template_id
""")


def fetch_bank_template_row_by_identifier(
    database_session: Session, *, bank_template_id: int
) -> dict | None:
    """
    Formal:  One bank_templates row by primary key (same column shape as ingest menu rows).
    Human:   Used when saving template–chart links for a specific saved map.

    Accounting Rule:
        N/A — read-only catalog row.
    """
    result = database_session.execute(
        _FETCH_TEMPLATE_BY_PRIMARY_KEY, {"bank_template_id": int(bank_template_id)}
    ).fetchone()
    if result is None:
        return None
    return dict(result._mapping)

_SELECT_ALL_ORDERED_FOR_MENU = text("""
    SELECT
        id,
        name,
        linked_account_number,
        date_col,
        payee_col,
        amount_col,
        reference_col,
        is_liability,
        ingest_kind,
        built_in_parser_key,
        created_at
    FROM bank_templates
    ORDER BY
        CASE ingest_kind WHEN 'built_in_pdf' THEN 0 ELSE 1 END,
        name ASC
""")

_COUNT_NAME = text("""
    SELECT COUNT(*) AS count_rows
    FROM bank_templates
    WHERE LOWER(TRIM(name)) = LOWER(TRIM(:template_name))
""")

_RETIRE_LEGACY_CHASE_PDF_BUILTIN = text("""
    DELETE FROM bank_templates
    WHERE built_in_parser_key = 'chase_pdf'
       OR (
            ingest_kind = 'built_in_pdf'
            AND LOWER(TRIM(name)) = LOWER('Chase PDF (built-in)')
       )
""")

_SEED_CHASE_CREDIT_CARD_BUILT_IN = text("""
    INSERT OR IGNORE INTO bank_templates (
        name,
        linked_account_number,
        date_col,
        payee_col,
        amount_col,
        reference_col,
        is_liability,
        ingest_kind,
        built_in_parser_key
    )
    VALUES (
        'Chase credit card PDF (built-in)',
        NULL,
        '',
        '',
        '',
        '',
        1,
        'built_in_pdf',
        'chase_credit_card_pdf'
    )
""")

_SEED_CAPITAL_ONE_CARD_BUILT_IN = text("""
    INSERT OR IGNORE INTO bank_templates (
        name,
        linked_account_number,
        date_col,
        payee_col,
        amount_col,
        reference_col,
        is_liability,
        ingest_kind,
        built_in_parser_key
    )
    VALUES (
        'Capital One card PDF (built-in)',
        NULL,
        '',
        '',
        '',
        '',
        1,
        'built_in_pdf',
        'capital_one_card_pdf'
    )
""")

_SEED_CHASE_CHECKING_BUILT_IN = text("""
    INSERT OR IGNORE INTO bank_templates (
        name,
        linked_account_number,
        date_col,
        payee_col,
        amount_col,
        reference_col,
        is_liability,
        ingest_kind,
        built_in_parser_key
    )
    VALUES (
        'Chase checking PDF (built-in)',
        NULL,
        '',
        '',
        '',
        '',
        0,
        'built_in_pdf',
        'chase_checking_pdf'
    )
""")


def insert_bank_template_row(
    database_session: Session,
    *,
    template_name: str,
    linked_account_number: int | None,
    date_col: str,
    payee_col: str,
    amount_col: str,
    reference_col: str,
    is_liability: int,
    ingest_kind: str,
    built_in_parser_key: str | None,
) -> None:
    """
    Formal:  Inserts one bank_templates row.
    Human:   One saved mapping or one registry entry at a time.
    """
    database_session.execute(
        _INSERT_BANK_TEMPLATE,
        {
            "name": template_name,
            "linked_account_number": linked_account_number,
            "date_col": date_col,
            "payee_col": payee_col,
            "amount_col": amount_col,
            "reference_col": reference_col,
            "is_liability": int(is_liability),
            "ingest_kind": ingest_kind,
            "built_in_parser_key": built_in_parser_key,
        },
    )


def fetch_all_bank_templates_ordered_for_menu(database_session: Session) -> list[dict]:
    """
    Formal:  Returns every template row for ingest / admin lists.
    Human:   Built-in parsers sort ahead of CSV header maps.
    """
    result = database_session.execute(_SELECT_ALL_ORDERED_FOR_MENU)
    return [dict(row._mapping) for row in result.fetchall()]


def count_bank_templates_by_normalized_name(
    database_session: Session,
    template_name: str,
) -> int:
    """
    Formal:  Counts rows whose name matches trimmed case-insensitive string.
    Human:   Friendly duplicate check before UNIQUE blows up.
    """
    row = database_session.execute(
        _COUNT_NAME, {"template_name": str(template_name).strip()}
    ).fetchone()
    return int(row[0]) if row else 0


def retire_legacy_chase_pdf_builtin_template_row(database_session: Session) -> None:
    """
    Formal:  Removes the retired Chase PDF (built-in) / chase_pdf parser registry row if present.
    Human:   One-time cleanup when upgrading to Chase credit card PDF + checking PDF split.

    Accounting Rule:
        N/A — template catalog migration only.
    """
    database_session.execute(_RETIRE_LEGACY_CHASE_PDF_BUILTIN)


def seed_chase_credit_card_built_in_template_row(database_session: Session) -> None:
    """
    Formal:  Idempotent INSERT OR IGNORE for Chase credit card PDF (ACCOUNT ACTIVITY layout).
    Human:   Ultimate Rewards style statements; is_liability 1 for card posting rules.
    """
    database_session.execute(_SEED_CHASE_CREDIT_CARD_BUILT_IN)


def seed_capital_one_card_built_in_template_row(database_session: Session) -> None:
    """
    Formal:  Idempotent INSERT OR IGNORE for the Capital One card PDF registry row.
    Human:   Quicksilver-style text PDFs map here; is_liability marks card posting rules.
    """
    database_session.execute(_SEED_CAPITAL_ONE_CARD_BUILT_IN)


def seed_chase_checking_built_in_template_row(database_session: Session) -> None:
    """
    Formal:  Idempotent INSERT OR IGNORE for Chase deposit / Total Checking PDF layout.
    Human:   Asset posting (is_liability 0); transaction grid includes running balance column.
    """
    database_session.execute(_SEED_CHASE_CHECKING_BUILT_IN)
