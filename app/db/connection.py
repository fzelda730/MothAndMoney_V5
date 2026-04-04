"""
PostgreSQL connection helpers. Loads environment from app/.env (same directory as this package's parent).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import quote_plus

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

_APP_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_APP_DIR / ".env")


def use_sample_data() -> bool:
    """When True (default), pages use data.sample_data instead of the database."""
    v = os.getenv("USE_SAMPLE_DATA", "true").strip().lower()
    return v in ("1", "true", "yes", "on")


def database_url() -> str | None:
    """Return a libpq connection string, or None if not configured."""
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    host = os.getenv("DB_HOST", "").strip()
    if not host:
        return None
    port = os.getenv("DB_PORT", "5432").strip()
    name = os.getenv("DB_NAME", "moth_and_money").strip()
    user = quote_plus(os.getenv("DB_USER", "postgres").strip())
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


@contextmanager
def get_connection() -> Iterator[psycopg2.extensions.connection]:
    """Yield a psycopg2 connection using RealDictCursor for row dicts."""
    dsn = database_url()
    if not dsn:
        raise RuntimeError(
            "Database is not configured. Set DATABASE_URL or DB_HOST (and related) in app/.env, "
            "or set USE_SAMPLE_DATA=true."
        )
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_connection() -> tuple[bool, str | None]:
    """Return (ok, error_message)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True, None
    except Exception as e:
        return False, str(e)
