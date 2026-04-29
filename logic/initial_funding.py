"""
MOTH AND MONEY — OPENING BALANCE FUNDING
/logic/initial_funding.py

Formal:  Posts the opening trial balance as a single journal entry with one
         ledger line per non-zero account, balanced before committing.
Human:   Loads your real starting balances into the Fortress — if the
         numbers don't balance, nothing gets saved.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas
from sqlalchemy import text

from database.connection import open_database_session

_SAMPLES_DIRECTORY   = Path(__file__).resolve().parent.parent / "Samples"
_TRIAL_BALANCE_CSV   = _SAMPLES_DIRECTORY / "CMF_Trial_Balance_V5_Proposed.csv"

_OPENING_ENTRY_DATE        = "2026-12-31"
_OPENING_ENTRY_DESCRIPTION = "Opening Balance: Founding the V5 Fortress"
_OPENING_SOURCE_METADATA   = "CMF_Trial_Balance_V5_Proposed.csv"


def _parse_currency_string_to_decimal(raw_value) -> Decimal:
    """
    Formal:  Converts a raw CSV currency cell — which may be blank or
             comma-formatted — to a Decimal with two decimal places.
    Human:   Cleans up messy spreadsheet numbers so the math stays exact.
    """
    if pandas.isna(raw_value) or str(raw_value).strip() == "":
        return Decimal("0.00")
    clean_value = str(raw_value).replace(",", "").strip()
    return Decimal(clean_value)


def post_opening_balance_from_csv() -> None:
    """
    Formal:  Reads the trial balance CSV, validates that total debits equal
             total credits, then writes one journal entry and N ledger lines
             to moth_and_money.db within a single atomic session.
    Human:   Plants your real opening balances — but only if the books
             balance first. One bad number and nothing gets saved.
    """
    trial_balance_dataframe = pandas.read_csv(_TRIAL_BALANCE_CSV)

    ledger_line_records = []
    total_debit_amount  = Decimal("0.00")
    total_credit_amount = Decimal("0.00")

    for _, csv_row in trial_balance_dataframe.iterrows():
        account_number = int(csv_row["Account Number"])
        row_debit_amount  = _parse_currency_string_to_decimal(csv_row["Debit"])
        row_credit_amount = _parse_currency_string_to_decimal(csv_row["Credit"])

        if row_debit_amount == Decimal("0.00") and row_credit_amount == Decimal("0.00"):
            continue

        total_debit_amount  += row_debit_amount
        total_credit_amount += row_credit_amount

        ledger_line_records.append({
            "account_number": account_number,
            "debit_amount":   str(row_debit_amount),
            "credit_amount":  str(row_credit_amount),
        })

    if total_debit_amount != total_credit_amount:
        raise ValueError(
            f"The opening balance does not balance. "
            f"Total Debits ({total_debit_amount}) do not equal "
            f"Total Credits ({total_credit_amount}). "
            f"Please review CMF_Trial_Balance_V5_Proposed.csv before posting."
        )

    insert_journal_statement = text("""
        INSERT INTO journal_entries
            (entry_date, entry_description, source_metadata)
        VALUES
            (:entry_date, :entry_description, :source_metadata)
    """)

    insert_ledger_statement = text("""
        INSERT INTO ledger_entries
            (journal_entry_id, account_number, debit_amount, credit_amount)
        VALUES
            (:journal_entry_id, :account_number, :debit_amount, :credit_amount)
    """)

    check_existing_statement = text("""
        SELECT journal_entry_id FROM journal_entries
        WHERE source_metadata = :source_metadata
        LIMIT 1
    """)

    with open_database_session() as accounting_session:
        existing_entry = accounting_session.execute(
            check_existing_statement,
            {"source_metadata": _OPENING_SOURCE_METADATA},
        ).fetchone()

        if existing_entry:
            print(
                "Formal:  Opening balance entry already exists — skipped.\n"
                "Human:   Your Fortress is already funded. Nothing was changed."
            )
            return

        journal_insert_result = accounting_session.execute(
            insert_journal_statement,
            {
                "entry_date":        _OPENING_ENTRY_DATE,
                "entry_description": _OPENING_ENTRY_DESCRIPTION,
                "source_metadata":   _OPENING_SOURCE_METADATA,
            },
        )
        new_journal_entry_identifier = journal_insert_result.lastrowid

        for ledger_line in ledger_line_records:
            ledger_line["journal_entry_id"] = new_journal_entry_identifier

        accounting_session.execute(insert_ledger_statement, ledger_line_records)

    total_lines_posted = len(ledger_line_records)
    print(
        f"Formal:  Opening journal entry posted with {total_lines_posted} "
        f"ledger lines. Debits = Credits = {total_debit_amount}.\n"
        f"Human:   Your Fortress is funded. {total_lines_posted} accounts "
        f"have real opening balances."
    )


if __name__ == "__main__":
    post_opening_balance_from_csv()
