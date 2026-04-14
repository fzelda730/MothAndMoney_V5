"""
Hooks for credit card CSV import: resolve COA from payee_rules for a bank account.
"""

from __future__ import annotations


def coa_id_from_payee_rules(payee_raw: str, bank_account_id: str) -> str | None:
    from data.providers import resolve_credit_card_import_payee_coa_id

    return resolve_credit_card_import_payee_coa_id(payee_raw, bank_account_id)
