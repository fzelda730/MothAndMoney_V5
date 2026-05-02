"""
MOTH AND MONEY — LOCAL LEDGER FILE MAINTENANCE
/database/db_maintenance.py

Formal:  Single entry for wiping moth_and_money.db and re-applying schema DDL,
         delegated to the existing SQLite lifecycle helpers.
Human:   Danger Zone actions in onboarding and settings call here — not scattered SQL.
"""

from __future__ import annotations

from database.sqlite_lifecycle import reset_sqlite_database_file_and_schema


def wipe_local_ledger_database() -> None:
    """
    Formal:  Deletes the SQLite ledger file (if present), disposes the pooled engine,
             and recreates empty General Ledger tables from schema.sql.
    Human:   Use only when you intend to erase every account and journal line locally.

    Accounting Rule:
        This affects only the General Ledger file bound in database.connection.
    """
    reset_sqlite_database_file_and_schema()
