"""
Hooks for bank statement CSV import. When inserting `transactions`, resolve COA from payee rules.
"""

from __future__ import annotations


def coa_id_from_payee_rules(payee_raw: str, bank_account_id: str) -> str | None:
    """
    Exact normalized match against payee_rules for this bank account.
    Uses PostgreSQL in DB mode; session-backed rules in demo mode.
    """
    from data.providers import resolve_bank_import_payee_coa_id

    return resolve_bank_import_payee_coa_id(payee_raw, bank_account_id)
