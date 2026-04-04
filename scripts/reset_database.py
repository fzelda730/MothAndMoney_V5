#!/usr/bin/env python3
"""
Drop and recreate the PostgreSQL database from app/.env, then apply app/db/schema.sql.

Use before manual testing when you want a clean slate. After reset, only schema.sql
defaults exist (studio profile + chart of accounts).

Optional: --with-seed runs app/db/seed_demo.sql (demo banks, accounts, transactions).

Requires: psql on PATH, psycopg2, python-dotenv (app venv), app/.env with DB_* or DATABASE_URL.

Usage (from repo root, venv active):
  python scripts/reset_database.py
  python scripts/reset_database.py --yes
  python scripts/reset_database.py --yes --with-seed
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"
ENV_FILE = APP_DIR / ".env"
SCHEMA_SQL = APP_DIR / "db" / "schema.sql"
SEED_SQL = APP_DIR / "db" / "seed_demo.sql"


def load_config() -> dict:
    if not ENV_FILE.is_file():
        sys.exit(f"Missing {ENV_FILE}. Copy app/.env.example and set database credentials.")
    load_dotenv(ENV_FILE)

    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        p = urlparse(url)
        path = (p.path or "").lstrip("/")
        dbname = path.split("/")[0] if path else ""
        if not dbname:
            sys.exit(
                "DATABASE_URL must include a database name in the path, e.g. .../moth_and_money"
            )
        return {
            "host": p.hostname or "localhost",
            "port": int(p.port or 5432),
            "user": unquote(p.username or "postgres"),
            "password": unquote(p.password or ""),
            "dbname": dbname,
        }

    host = os.getenv("DB_HOST", "").strip()
    if not host:
        sys.exit("Set DATABASE_URL or DB_HOST (and related) in app/.env")
    return {
        "host": host,
        "port": int(os.getenv("DB_PORT", "5432").strip() or 5432),
        "user": os.getenv("DB_USER", "postgres").strip(),
        "password": os.getenv("DB_PASSWORD", ""),
        "dbname": os.getenv("DB_NAME", "moth_and_money").strip(),
    }


def terminate_sessions(cur, dbname: str) -> None:
    cur.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = %s AND pid <> pg_backend_pid()
        """,
        (dbname,),
    )


def drop_and_create(cfg: dict) -> None:
    dbname = cfg["dbname"]
    conn = psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        dbname="postgres",
    )
    conn.set_session(autocommit=True)
    try:
        with conn.cursor() as cur:
            terminate_sessions(cur, dbname)
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname))
            )
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(dbname),
                    sql.Identifier(cfg["user"]),
                )
            )
    finally:
        conn.close()


def run_psql_file(cfg: dict, sql_path: Path) -> None:
    psql = shutil.which("psql")
    if not psql:
        sys.exit(
            "psql not found on PATH. Install PostgreSQL client tools, or run schema.sql manually."
        )
    if not sql_path.is_file():
        sys.exit(f"Missing SQL file: {sql_path}")

    env = {**os.environ, "PGPASSWORD": str(cfg["password"])}
    cmd = [
        psql,
        "-h",
        str(cfg["host"]),
        "-p",
        str(cfg["port"]),
        "-U",
        str(cfg["user"]),
        "-d",
        str(cfg["dbname"]),
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        str(sql_path),
    ]
    r = subprocess.run(cmd, env=env, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr or r.stdout or "")
        sys.exit(r.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drop and recreate the Moth and Money database, then apply schema.sql."
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Do not ask for confirmation",
    )
    parser.add_argument(
        "--with-seed",
        action="store_true",
        help="Also run app/db/seed_demo.sql (demo accounts and transactions)",
    )
    args = parser.parse_args()

    if not SCHEMA_SQL.is_file():
        sys.exit(f"Missing {SCHEMA_SQL}")

    cfg = load_config()
    dbname = str(cfg["dbname"])

    if not args.yes:
        print(
            f"This will DROP database {dbname!r} on {cfg['host']}:{cfg['port']} "
            "and recreate it. All data in that database will be lost."
        )
        a = input("Type YES to continue: ").strip()
        if a != "YES":
            print("Aborted.")
            sys.exit(1)

    print(f"Dropping and creating database {dbname!r}...")
    drop_and_create(cfg)
    print(f"Applying {SCHEMA_SQL.relative_to(REPO_ROOT)}...")
    run_psql_file(cfg, SCHEMA_SQL)
    if args.with_seed:
        print(f"Applying {SEED_SQL.relative_to(REPO_ROOT)}...")
        run_psql_file(cfg, SEED_SQL)
    print("Done. Set USE_SAMPLE_DATA=false in app/.env and run: streamlit run app/app.py")


if __name__ == "__main__":
    main()
