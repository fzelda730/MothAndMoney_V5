
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


def ensure_sqlite_optional_columns(raw_sqlite_connection) -> None:
    """
    Formal:  ALTER TABLE ADD COLUMN for fields added after first database creation.
    Human:   Older moth_and_money.db files pick up new ledger and template columns safely.

    Accounting Rule:
        Defaults keep existing rows valid; opening-balance lines use empty payee/reference.
    """
    cursor = raw_sqlite_connection.execute("PRAGMA table_info(ledger_entries)")
    ledger_column_names = {row[1] for row in cursor.fetchall()}
    if "payee" not in ledger_column_names:
        raw_sqlite_connection.execute(
            "ALTER TABLE ledger_entries ADD COLUMN payee TEXT NOT NULL DEFAULT ''"
        )
    if "reference" not in ledger_column_names:
        raw_sqlite_connection.execute(
            "ALTER TABLE ledger_entries ADD COLUMN reference TEXT NOT NULL DEFAULT ''"
        )

    cursor = raw_sqlite_connection.execute("PRAGMA table_info(bank_templates)")
    bank_template_column_names = {row[1] for row in cursor.fetchall()}
    if "reference_col" not in bank_template_column_names:
        raw_sqlite_connection.execute(
            "ALTER TABLE bank_templates ADD COLUMN reference_col TEXT NOT NULL DEFAULT ''"
        )


def ensure_bank_template_chart_links_table(raw_sqlite_connection) -> None:
    """
    Formal:  Creates bank_template_chart_links if missing (journaled DBs from before this table).
    Human:   Opening the app after an upgrade still gets the junction table without a full re-init.

    Accounting Rule:
        FK to bank_templates and chart_of_accounts; CASCADE when a template row is deleted.
    """
    raw_sqlite_connection.execute(
        """
        CREATE TABLE IF NOT EXISTS bank_template_chart_links (
            bank_template_id    INTEGER NOT NULL
                                    REFERENCES bank_templates(id)
                                    ON DELETE CASCADE,
            account_number      INTEGER NOT NULL
                                    REFERENCES chart_of_accounts(account_number),
            PRIMARY KEY (bank_template_id, account_number)
        )
        """
    )
    raw_sqlite_connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bank_template_chart_links_template
            ON bank_template_chart_links (bank_template_id)
        """
    )


def ensure_csv_bank_templates_drop_legacy_linked_account(raw_sqlite_connection) -> None:
    """
    Formal:  Sets bank_templates.linked_account_number to NULL for csv_headers rows only.
    Human:   Legacy Relay-style rows sometimes stored a default account; Target chart account is
             always chosen (or short-listed) on Statement Upload now.

    Accounting Rule:
        built_in_pdf and other ingest kinds are not modified.
    """
    raw_sqlite_connection.execute(
        """
        UPDATE bank_templates
        SET linked_account_number = NULL
        WHERE ingest_kind = 'csv_headers'
          AND linked_account_number IS NOT NULL
        """
    )


def ensure_payee_chart_account_mappings_table(raw_sqlite_connection) -> None:
    """
    Formal:  Creates payee_chart_account_mappings when missing (DBs created before this table).
    Human:   Statement Upload can remember payee-to-account choices without a full re-init.

    Accounting Rule:
        FK to chart_of_accounts; one row per normalized payee key.
    """
    raw_sqlite_connection.execute(
        """
        CREATE TABLE IF NOT EXISTS payee_chart_account_mappings (
            payee_normalized_key    TEXT    NOT NULL,
            account_number          INTEGER NOT NULL
                                        REFERENCES chart_of_accounts(account_number),
            created_at              TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at              TEXT    NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (payee_normalized_key)
        )
        """
    )
    raw_sqlite_connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_payee_chart_account_mappings_account
            ON payee_chart_account_mappings (account_number)
        """
    )


def initialize_database_schema() -> None:
    """
    Formal:  Reads schema.sql and executes it against moth_and_money.db,
             establishing chart_of_accounts, journal_entries, ledger_entries,
             bank_templates, and idempotent built-in ingest seeds (Chase, Capital One, etc.).
    Human:   Builds the three empty "rooms" in your ledger file so the
             rest of the app has somewhere to store your financial data.
    """
    raw_sql_script = _SCHEMA_FILE_PATH.read_text(encoding="utf-8")

    database_engine = get_database_engine()
    raw_sqlite_connection = database_engine.raw_connection()
    try:
        raw_sqlite_connection.executescript(raw_sql_script)
        ensure_sqlite_optional_columns(raw_sqlite_connection)
        ensure_bank_template_chart_links_table(raw_sqlite_connection)
        ensure_payee_chart_account_mappings_table(raw_sqlite_connection)
        ensure_csv_bank_templates_drop_legacy_linked_account(raw_sqlite_connection)
        raw_sqlite_connection.commit()
    finally:
        raw_sqlite_connection.close()

    from database.statement_import_chart_seed import ensure_statement_import_clearing_account
    from database.connection import open_database_session

    with open_database_session() as database_session:
        ensure_statement_import_clearing_account(database_session)

    from logic.bank_templates import ensure_builtin_bank_template_rows

    ensure_builtin_bank_template_rows()


if __name__ == "__main__":
    initialize_database_schema()
    print("moth_and_money.db is ready — all tables are in place.")
