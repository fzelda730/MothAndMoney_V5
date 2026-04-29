
"""
MOTH AND MONEY — DATABASE BOOTSTRAP
/database/bootstrap.py

Formal:  Initialises the moth_and_money.db schema by executing schema.sql
         against the SQLite engine, creating all tables if they do not yet exist.
Human:   Run this once (or any time) to make sure your ledger file is
         ready — it will never overwrite data that is already there.
"""

from __future__ import annotations

from pathlib import Path

from database.connection import get_database_engine

_SCHEMA_FILE_PATH = Path(__file__).resolve().parent / "schema.sql"


def initialize_database_schema() -> None:
    """
    Formal:  Reads schema.sql and executes it against moth_and_money.db,
             establishing the chart_of_accounts, journal_entries, and
             ledger_entries tables required for double-entry bookkeeping.
    Human:   Builds the three empty "rooms" in your ledger file so the
             rest of the app has somewhere to store your financial data.
    """
    raw_sql_script = _SCHEMA_FILE_PATH.read_text(encoding="utf-8")

    database_engine = get_database_engine()
    raw_sqlite_connection = database_engine.raw_connection()
    try:
        raw_sqlite_connection.executescript(raw_sql_script)
        raw_sqlite_connection.commit()
    finally:
        raw_sqlite_connection.close()


if __name__ == "__main__":
    initialize_database_schema()
    print("moth_and_money.db is ready — all tables are in place.")
