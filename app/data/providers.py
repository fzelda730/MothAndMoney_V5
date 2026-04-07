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

    return queries.fetch_import_templates()


def chart_of_accounts():
    if use_sample_data():
        from data.sample_data import CHART_OF_ACCOUNTS

        return CHART_OF_ACCOUNTS
    from db import queries

    return queries.fetch_chart_of_accounts()


def trial_balance_report():
    if use_sample_data():
        from data.sample_data import TRIAL_BALANCE_REPORT

        return TRIAL_BALANCE_REPORT
    from db import queries

    return queries.fetch_trial_balance_report()


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


def save_trial_balance_csv_to_db(reference_name: str, rows: list[dict]) -> int:
    """Persist CSV trial balance rows when USE_SAMPLE_DATA=false. Returns inserted line count."""
    if use_sample_data():
        return 0
    from db import queries

    return queries.save_trial_balance_csv_import(reference_name, rows)


def save_bank_statement_template_to_db(template_name: str, column_map: dict) -> str:
    """Insert a bank statement import template. Returns new row id, or empty string if demo or failure."""
    if use_sample_data():
        return ""
    if not (template_name or "").strip():
        return ""
    from db import queries

    return queries.insert_import_template(template_name, "bank_statement", column_map)


def payee_rules_for_template(template_id: str) -> list[dict]:
    """DB-backed payee_rules rows for an import template (empty in demo mode)."""
    if use_sample_data():
        return []
    from db import queries

    return queries.fetch_payee_rules_for_template(template_id)


def persist_payee_rule(
    template_id: str, payee_pattern_normalized: str, coa_id: str | None
) -> None:
    """Upsert or delete a payee rule. No-op in demo mode (use session on the page)."""
    if use_sample_data():
        return
    from db import queries

    pid = (payee_pattern_normalized or "").strip()
    tid = (template_id or "").strip()
    if not tid or not pid:
        return
    if coa_id:
        queries.upsert_payee_rule(tid, pid, coa_id.strip())
    else:
        queries.delete_payee_rule_for_template(tid, pid)


def resolve_bank_import_payee_coa_id(payee_raw: str, template_id: str) -> str | None:
    """
    Resolve COA id from payee text for a bank import batch (exact normalized match).
    In demo mode, reads rules from session key bank_payee_demo_rules if present.
    """
    from data.bank_statement_csv import normalize_payee_for_rule

    norm = normalize_payee_for_rule(payee_raw)
    tid = (template_id or "").strip()
    if not norm or not tid:
        return None
    if use_sample_data():
        nested = st.session_state.get("bank_payee_demo_rules", {}).get(tid, {})
        return nested.get(norm)
    from db import queries

    return queries.resolve_coa_id_for_bank_payee(payee_raw, template_id)


def save_credit_card_template_to_db(template_name: str, column_map: dict) -> str:
    """Insert a credit card import template. Empty string if demo mode or insert failed."""
    if use_sample_data():
        return ""
    from db import queries

    return queries.insert_import_template(template_name, "credit_card", column_map)


def first_non_cash_bank_account_id() -> str | None:
    if use_sample_data():
        for a in bank_accounts():
            if a.get("account_type") != "cash":
                return a["id"]
        return None
    from db import queries

    return queries.first_bank_account_id_non_cash()
