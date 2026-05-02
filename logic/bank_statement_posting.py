"""
MOTH AND MONEY — BANK STATEMENT POSTING (LOGIC)
/logic/bank_statement_posting.py

Formal:  One balanced journal per import file: N transactions become 2×N ledger lines plus audit fields.
Human:   Every line hits your cash/card bucket on one leg and your chosen offset account (or 5890 clearing) on the other.

Accounting Rule:
    Duplicate source_metadata on journal_entries is rejected. Asset vs Liability uses template is_liability.
    Each row may carry offset_account_number; non-clearing choices persist to payee_chart_account_mappings on commit.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text

from database.chart_of_accounts_repository import account_number_exists_in_chart
from database.connection import open_database_session
from database.payee_chart_account_mapping_repository import (
    delete_payee_chart_account_mapping,
    upsert_payee_chart_account_mapping,
)
from database.statement_import_chart_seed import (
    STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER,
    ensure_statement_import_clearing_account,
)
from logic.payee_statement_classification import normalize_payee_for_mapping_key

_INSERT_JOURNAL = text("""
    INSERT INTO journal_entries (entry_date, entry_description, source_metadata)
    VALUES (:entry_date, :entry_description, :source_metadata)
""")

_INSERT_LEDGER = text("""
    INSERT INTO ledger_entries
        (journal_entry_id, account_number, debit_amount, credit_amount, payee, reference)
    VALUES
        (:journal_entry_id, :account_number, :debit_amount, :credit_amount, :payee, :reference)
""")

_CHECK_SOURCE_SEEN = text("""
    SELECT journal_entry_id FROM journal_entries
    WHERE source_metadata = :source_metadata
    LIMIT 1
""")


def _money_string(amount: Decimal) -> str:
    """
    Formal:  Quantize to cents for NUMERIC(15,2) columns.
    Human:   Keeps SQLite ledger readable and aligned with Rule 5 precision habits.
    """
    return str(amount.quantize(Decimal("0.01")))


def _ledger_pair_for_line(
    *,
    signed_amount: Decimal,
    target_is_liability: bool,
) -> tuple[str, str, str, str]:
    """
    Formal:  Debit/credit strings for the register leg paired with the offset leg for one signed transaction.
    Human:   Positive amounts are “your normal direction” per account type (see module doc tests).

    Accounting Rule:
        Register + offset legs always balance this line pair before the next transaction pair.
    """
    absolute_amount = abs(signed_amount)
    if absolute_amount == 0:
        return "0.00", "0.00", "0.00", "0.00"
    magnitude = _money_string(absolute_amount)
    if not target_is_liability:
        if signed_amount >= 0:
            return magnitude, "0.00", "0.00", magnitude
        return "0.00", magnitude, magnitude, "0.00"
    if signed_amount >= 0:
        return "0.00", magnitude, magnitude, "0.00"
    return magnitude, "0.00", "0.00", magnitude


def post_statement_import_transactions(
    *,
    target_account_number: int,
    source_metadata: str,
    entry_description: str,
    is_liability_template: bool,
    transaction_rows: list[dict],
) -> int:
    """
    Formal:  Inserts one journal_entries row and paired ledger_entries for each parsed transaction.
    Human:   Use after you confirm the preview — same filename cannot post twice.

    Accounting Rule:
        Double-entry per line pair; off leg uses offset_account_number when present (else 5890 clearing).
        payee/reference preserved on the register leg; payee mappings persist when offset is not clearing.
    """
    cleaned_source = str(source_metadata).strip()
    if cleaned_source == "":
        raise ValueError("source_metadata must name this file for audit (Rule 5).")

    if len(transaction_rows) == 0:
        raise ValueError("There are no transactions to post.")

    target_bucket = int(target_account_number)
    all_dates = [str(row["posting_date_iso"]) for row in transaction_rows]
    entry_date_iso = max(all_dates)

    ledger_payload: list[dict] = []
    for row in transaction_rows:
        payee = str(row.get("payee") or "")[:500]
        reference = str(row.get("reference") or "")[:500]
        amount_value = row["amount"]
        if not isinstance(amount_value, Decimal):
            amount_value = Decimal(str(amount_value))

        target_debit, target_credit, offset_debit, offset_credit = (
            _ledger_pair_for_line(
                signed_amount=amount_value,
                target_is_liability=bool(is_liability_template),
            )
        )
        offset_account_raw = row.get("offset_account_number")
        if offset_account_raw is None:
            offset_bucket = STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER
        else:
            offset_bucket = int(offset_account_raw)
        ledger_payload.append(
            {
                "account_number": target_bucket,
                "debit_amount": target_debit,
                "credit_amount": target_credit,
                "payee": payee,
                "reference": reference,
            }
        )
        ledger_payload.append(
            {
                "account_number": offset_bucket,
                "debit_amount": offset_debit,
                "credit_amount": offset_credit,
                "payee": "",
                "reference": "",
            }
        )

    with open_database_session() as database_session:
        ensure_statement_import_clearing_account(database_session)
        if not account_number_exists_in_chart(database_session, target_bucket):
            raise ValueError(
                "That chart account is missing. Refresh after adding the bucket on Onboarding."
            )

        for row in transaction_rows:
            offset_account_raw = row.get("offset_account_number")
            offset_bucket = (
                int(offset_account_raw)
                if offset_account_raw is not None
                else STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER
            )
            if offset_bucket == target_bucket:
                raise ValueError(
                    "One line had the same offset account as your bank or card bucket — pick an "
                    "expense, revenue, or clearing account that is not this register account."
                )
            if not account_number_exists_in_chart(database_session, offset_bucket):
                raise ValueError(
                    "One offset account is missing from the chart. Return to Onboarding if you "
                    f"deleted account **{offset_bucket}**."
                )

        duplicate_row = database_session.execute(
            _CHECK_SOURCE_SEEN, {"source_metadata": cleaned_source}
        ).fetchone()
        if duplicate_row:
            raise ValueError(
                "This exact filename was already posted. Rename the export or clear the duplicate journal first."
            )

        journal_insert = database_session.execute(
            _INSERT_JOURNAL,
            {
                "entry_date": entry_date_iso,
                "entry_description": str(entry_description).strip() or "Statement import",
                "source_metadata": cleaned_source,
            },
        )
        journal_entry_id = int(journal_insert.lastrowid)

        for line in ledger_payload:
            line["journal_entry_id"] = journal_entry_id
            database_session.execute(_INSERT_LEDGER, line)

        for row in transaction_rows:
            payee_normalized_key = normalize_payee_for_mapping_key(str(row.get("payee") or ""))
            if payee_normalized_key == "":
                continue
            offset_account_raw = row.get("offset_account_number")
            offset_bucket = (
                int(offset_account_raw)
                if offset_account_raw is not None
                else STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER
            )
            if offset_bucket == STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER:
                delete_payee_chart_account_mapping(
                    database_session,
                    payee_normalized_key=payee_normalized_key,
                )
            else:
                upsert_payee_chart_account_mapping(
                    database_session,
                    payee_normalized_key=payee_normalized_key,
                    account_number=offset_bucket,
                )

    return len(ledger_payload)
