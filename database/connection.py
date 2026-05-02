"""
MOTH AND MONEY — DATABASE CONNECTION GUARDIAN
/database/connection.py

Formal:  Provides the authoritative SQLAlchemy engine and session lifecycle
         for the moth_and_money.db General Ledger.
Human:   This file is the one front door to your financial data — every
         read and write goes through here, safely.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_PROJECT_ROOT_DIRECTORY = Path(__file__).resolve().parent.parent
_SQLITE_DATABASE_FILE_PATH = _PROJECT_ROOT_DIRECTORY / "moth_and_money.db"

_shared_database_engine: Engine | None = None


def get_sqlite_database_file_path() -> Path:
    """
    Formal:  Returns the absolute path to moth_and_money.db under the
             project root used by this installation.
    Human:   One shared answer to “where is my ledger file?” — including
             for reset scripts that must delete or recreate that file.
    """
    return _SQLITE_DATABASE_FILE_PATH


def dispose_shared_database_engine() -> None:
    """
    Formal:  Disposes and clears the cached SQLAlchemy engine so a new
             SQLite file path or recreated file can be opened cleanly.
    Human:   Call this after wiping the database file so Streamlit does
             not keep stale connections to a file that no longer exists.
    """
    global _shared_database_engine
    if _shared_database_engine is not None:
        _shared_database_engine.dispose()
        _shared_database_engine = None


def get_database_engine() -> Engine:
    """
    Formal:  Returns the singleton SQLAlchemy engine bound to moth_and_money.db,
             creating it on first call and reusing it thereafter.
    Human:   Opens (or finds) your ledger file once, then keeps the door
             open so every page loads fast.
    """
    global _shared_database_engine
    if _shared_database_engine is None:
        _shared_database_engine = create_engine(
            f"sqlite:///{_SQLITE_DATABASE_FILE_PATH}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return _shared_database_engine


@contextmanager
def open_database_session() -> Generator[Session, None, None]:
    """
    Formal:  Yields an atomic SQLAlchemy session — committing on success,
             rolling back on any exception to preserve double-entry integrity.
    Human:   Think of this as a "save transaction" wrapper — if anything
             goes wrong mid-write, your ledger snaps back to its last
             clean state automatically.
    """
    database_session_factory = sessionmaker(bind=get_database_engine())
    active_session = database_session_factory()
    try:
        yield active_session
        active_session.commit()
    except Exception:
        active_session.rollback()
        raise
    finally:
        active_session.close()


def verify_database_connection() -> tuple[bool, str | None]:
    """
    Formal:  Executes a lightweight diagnostic query against moth_and_money.db
             and returns a structured (success, error_message) result.
    Human:   A quick "is your ledger file healthy?" check the Dashboard can
             show as a plain status badge instead of a scary error screen.
    """
    try:
        with get_database_engine().connect() as live_connection:
            live_connection.execute(text("SELECT 1"))
        return True, None
    except Exception as database_error:
        return False, str(database_error)
