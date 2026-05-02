"""
MOTH AND MONEY — SQLITE FILE LIFECYCLE
/database/sqlite_lifecycle.py

Formal:  Supports wiping moth_and_money.db and re-applying schema.sql, and
         exposes a read-only chart_of_accounts row count for app gating.
Human:   "Reset Database" and “is the Chart still empty?” live here — small,
         predictable operations around your single SQLite ledger file.
"""

from __future__ import annotations

from sqlalchemy import text

from database.bootstrap import initialize_database_schema
from database.connection import (
    dispose_shared_database_engine,
    get_database_engine,
    get_sqlite_database_file_path,
)


def reset_sqlite_database_file_and_schema() -> None:
    """
    Formal:  Removes moth_and_money.db (if present), disposes the pooled engine,
             and re-runs schema DDL so all tables are recreated empty.
    Human:   Starts your ledger from a blank slate — every prior journal line
             is gone; use only when you truly intend to wipe all existing data.
    """
    dispose_shared_database_engine()
    ledger_database_file_path = get_sqlite_database_file_path()
    if ledger_database_file_path.is_file():
        ledger_database_file_path.unlink()
    initialize_database_schema()


def count_chart_of_accounts_rows() -> int:
    """
    Formal:  Executes SELECT COUNT(*) against chart_of_accounts for routing
             and readiness checks (e.g. System Initialization gate).
    Human:   Answers “do we have any money buckets yet?” with a single number.
    """
    with get_database_engine().connect() as live_connection:
        scalar_result = live_connection.execute(
            text("SELECT COUNT(*) FROM chart_of_accounts")
        ).scalar_one()
    return int(scalar_result)
