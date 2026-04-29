"""
MOTH AND MONEY — CHART OF ACCOUNTS SEEDER
/logic/seeding.py

Formal:  Reads the proposed Chart of Accounts from CSV and performs a
         bulk upsert into the chart_of_accounts table in moth_and_money.db.
Human:   Plants all your "money buckets" into the database so the rest
         of the app has a real Chart of Accounts to work with.
"""

from __future__ import annotations

from pathlib import Path

import pandas
from sqlalchemy import text

from database.connection import open_database_session

_SAMPLES_DIRECTORY = Path(__file__).resolve().parent.parent / "Samples"
_CHART_OF_ACCOUNTS_CSV = _SAMPLES_DIRECTORY / "CMF_Trial_Balance_V5_Proposed.csv"

_ACCOUNT_CATEGORY_MAP = {
    1: ("Asset",     "Debit"),
    2: ("Liability", "Credit"),
    3: ("Equity",    "Credit"),
    4: ("Revenue",   "Credit"),
    5: ("Expense",   "Debit"),
}


def _derive_category_and_normal_balance(
    account_number: int,
) -> tuple[str, str]:
    """
    Formal:  Returns the account_category and normal_balance for a given
             account number, following the 1000s–5000s Accounting Hierarchy.
    Human:   Looks at the first digit of the account number and decides
             whether it is an Asset, Liability, Equity, Revenue, or Expense.
    """
    thousands_digit = account_number // 1000
    return _ACCOUNT_CATEGORY_MAP.get(thousands_digit, ("Uncategorized", "Debit"))


def seed_chart_of_accounts_from_csv() -> None:
    """
    Formal:  Reads CMF_Trial_Balance_V5_Proposed.csv and bulk-upserts all
             account records into the chart_of_accounts table, deriving
             category and normal balance from the account number range.
    Human:   Loads your full Chart of Accounts from the spreadsheet into
             the live database — safe to run more than once.
    """
    chart_of_accounts_dataframe = pandas.read_csv(
        _CHART_OF_ACCOUNTS_CSV,
        usecols=["Account Number", "Account Name"],
        dtype={"Account Number": int, "Account Name": str},
    )

    account_records = []
    for _, csv_row in chart_of_accounts_dataframe.iterrows():
        account_number = int(csv_row["Account Number"])
        account_category, normal_balance = _derive_category_and_normal_balance(
            account_number
        )
        account_records.append(
            {
                "account_number": account_number,
                "account_name": csv_row["Account Name"].strip(),
                "account_category": account_category,
                "normal_balance": normal_balance,
                "account_description": None,
                "is_active": 1,
            }
        )

    insert_statement = text("""
        INSERT OR REPLACE INTO chart_of_accounts
            (account_number, account_name, account_category,
             normal_balance, account_description, is_active)
        VALUES
            (:account_number, :account_name, :account_category,
             :normal_balance, :account_description, :is_active)
    """)

    with open_database_session() as accounting_session:
        accounting_session.execute(insert_statement, account_records)

    total_accounts_seeded = len(account_records)
    print(
        f"Formal:  {total_accounts_seeded} accounts successfully upserted "
        f"into chart_of_accounts.\n"
        f"Human:   Your {total_accounts_seeded} money buckets are planted "
        f"and ready to use."
    )


if __name__ == "__main__":
    seed_chart_of_accounts_from_csv()
