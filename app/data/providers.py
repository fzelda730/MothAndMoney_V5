"""
Unified data access: sample_data when USE_SAMPLE_DATA=true, else PostgreSQL queries.
"""

from __future__ import annotations

import streamlit as st

from db.connection import check_connection, use_sample_data


def db_ready() -> bool:
    """Return False and show an error if DB mode is on but the database is unreachable."""
    if use_sample_data():
        return True
    ok, err = check_connection()
    if ok:
        return True
    st.error(
        "PostgreSQL is not reachable. Set USE_SAMPLE_DATA=true in app/.env to use demo data, "
        "or fix DATABASE_URL / DB_* and ensure the database is running."
    )
    if err:
        st.caption(err)
    return False


def bank_accounts():
    if use_sample_data():
        from data.sample_data import BANK_ACCOUNTS

        return BANK_ACCOUNTS
    from db import queries

    return queries.fetch_bank_accounts()


def studio_profile():
    if use_sample_data():
        from data.sample_data import STUDIO

        return STUDIO
    from db import queries

    return queries.fetch_studio_profile()


def save_studio_profile_to_db(**kwargs) -> None:
    """Persist studio_profile row. Only use when USE_SAMPLE_DATA is false."""
    from db import queries

    queries.update_studio_profile(**kwargs)


def dashboard_stats():
    """Portfolio headline stats remain demo-derived until summary tables exist."""
    from data.sample_data import DASHBOARD_STATS

    return DASHBOARD_STATS


def tax_provision():
    from data.sample_data import TAX_PROVISION

    return TAX_PROVISION


def ledger_transactions(bank_account_id: str | None):
    if use_sample_data():
        from data.sample_data import LEDGER_TRANSACTIONS

        return LEDGER_TRANSACTIONS
    from db import queries

    if not bank_account_id:
        return []
    return queries.fetch_ledger_transactions(bank_account_id)


def ledger_summary(bank_account_id: str | None):
    if use_sample_data():
        from data.sample_data import LEDGER_SUMMARY

        return LEDGER_SUMMARY
    from db import queries

    if not bank_account_id:
        return {
            "beginning_balance": 0.0,
            "total_debits": 0.0,
            "total_credits": 0.0,
            "ending_balance": 0.0,
            "is_balanced": True,
        }
    return queries.fetch_ledger_summary(bank_account_id)


def import_templates():
    if use_sample_data():
        from data.sample_data import IMPORT_TEMPLATES

        return IMPORT_TEMPLATES
    from db import queries

    rows = queries.fetch_import_templates()
    if rows:
        return rows
    from data.sample_data import IMPORT_TEMPLATES

    return IMPORT_TEMPLATES


def chart_of_accounts():
    if use_sample_data():
        from data.sample_data import CHART_OF_ACCOUNTS

        return CHART_OF_ACCOUNTS
    from db import queries

    rows = queries.fetch_chart_of_accounts()
    if rows:
        return rows
    from data.sample_data import CHART_OF_ACCOUNTS

    return CHART_OF_ACCOUNTS


def trial_balance_report():
    if use_sample_data():
        from data.sample_data import TRIAL_BALANCE_REPORT

        return TRIAL_BALANCE_REPORT
    from db import queries

    rows = queries.fetch_trial_balance_report()
    if rows:
        return rows
    from data.sample_data import TRIAL_BALANCE_REPORT

    return TRIAL_BALANCE_REPORT


def trial_balance_import():
    if use_sample_data():
        from data.sample_data import TRIAL_BALANCE_IMPORT_PREVIEW, TRIAL_BALANCE_TOTALS

        return TRIAL_BALANCE_IMPORT_PREVIEW, TRIAL_BALANCE_TOTALS
    from db import queries

    preview, totals = queries.fetch_trial_balance_import_preview()
    if preview:
        return preview, totals
    return [], {
        "total_debits": 0.0,
        "total_credits": 0.0,
        "is_balanced": False,
        "variance": 0.0,
    }


def discard_pending_trial_balance() -> int:
    """Delete pending trial_balance_entries (no-op in demo mode)."""
    if use_sample_data():
        return 0
    from db import queries

    return queries.delete_pending_trial_balance_entries()


def first_non_cash_bank_account_id() -> str | None:
    if use_sample_data():
        for a in bank_accounts():
            if a.get("account_type") != "cash":
                return a["id"]
        return None
    from db import queries

    return queries.first_bank_account_id_non_cash()
