"""
Read-only queries mapping PostgreSQL rows to the dict shapes used by Streamlit pages.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
import uuid
from uuid import UUID

from psycopg2 import errors as pg_errors
from psycopg2.extras import execute_values

from db.connection import get_connection


def _num(x: Any) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    return float(x)


def _fmt_ledger_date(d: date | datetime) -> str:
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%b %d, %Y")


_STUDIO_DEFAULTS: dict[str, Any] = {
    "artist_name": "Your Name",
    "artist_title": "Creative Director",
    "studio_name": "Your Studio",
    "bio": "",
    "logo_url": "",
    "email": "",
    "tax_id": "",
    "base_currency": "USD",
    "fiscal_year_start": "January",
    "default_tax_rate": 25.0,
    "accounting_method": "Cash",
    "theme_preference": "light",
    "compact_ui": False,
}


def fetch_studio_profile() -> dict[str, Any]:
    """Shape aligned with data.sample_data.STUDIO. Empty DB returns defaults until first save."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT artist_name, artist_title, studio_name, bio, logo_url, email, tax_id,
                       base_currency, fiscal_year_start, default_tax_rate, accounting_method::text,
                       theme_preference, compact_ui
                FROM studio_profile
                ORDER BY created_at
                LIMIT 1
                """
            )
            row = cur.fetchone()
    if not row:
        return dict(_STUDIO_DEFAULTS)
    am = row["accounting_method"]
    return {
        "artist_name": row["artist_name"],
        "artist_title": row["artist_title"] or "Creative Director",
        "studio_name": row["studio_name"],
        "bio": row["bio"] or "",
        "logo_url": row["logo_url"] or "",
        "email": row["email"] or "",
        "tax_id": row["tax_id"] or "",
        "base_currency": row["base_currency"],
        "fiscal_year_start": row["fiscal_year_start"],
        "default_tax_rate": float(row["default_tax_rate"]),
        "accounting_method": am.title() if am else "Cash",
        "theme_preference": (row["theme_preference"] or "light").lower(),
        "compact_ui": bool(row["compact_ui"]),
    }


def update_studio_profile(
    *,
    artist_name: str,
    artist_title: str,
    studio_name: str,
    bio: str,
    logo_url: str,
    email: str,
    tax_id: str,
    base_currency: str,
    fiscal_year_start: str,
    default_tax_rate: float,
    accounting_method: str,
    theme_preference: str,
    compact_ui: bool,
) -> None:
    """Update the single studio_profile row (first by created_at)."""
    am = (accounting_method or "cash").lower()
    if am not in ("cash", "accrual"):
        am = "cash"
    theme = (theme_preference or "light").lower()
    if theme not in ("light", "dark", "system"):
        theme = "light"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM studio_profile")
            has_row = (cur.fetchone() or {}).get("c", 0) > 0
            params = (
                artist_name,
                artist_title[:255],
                studio_name,
                bio or None,
                logo_url or None,
                email or None,
                tax_id or None,
                base_currency[:10],
                fiscal_year_start[:20],
                default_tax_rate,
                am,
                theme[:20],
                compact_ui,
            )
            if has_row:
                cur.execute(
                    """
                    UPDATE studio_profile SET
                        artist_name = %s,
                        artist_title = %s,
                        studio_name = %s,
                        bio = %s,
                        logo_url = %s,
                        email = %s,
                        tax_id = %s,
                        base_currency = %s,
                        fiscal_year_start = %s,
                        default_tax_rate = %s,
                        accounting_method = %s::accounting_method_enum,
                        theme_preference = %s,
                        compact_ui = %s
                    WHERE id = (SELECT id FROM studio_profile ORDER BY created_at LIMIT 1)
                    """,
                    params,
                )
            else:
                cur.execute(
                    """
                    INSERT INTO studio_profile (
                        artist_name, artist_title, studio_name, bio, logo_url, email, tax_id,
                        base_currency, fiscal_year_start, default_tax_rate,
                        accounting_method, theme_preference, compact_ui
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s::accounting_method_enum, %s, %s
                    )
                    """,
                    params,
                )


def _icon_for_account_type(account_type: str) -> tuple[str, str, str]:
    t = (account_type or "").lower()
    if t == "checking":
        return "account_balance", "#154212", "#154212"
    if t == "savings":
        return "savings", "#154212", "#a1d494"
    if t == "credit_card":
        return "credit_card", "#71151d", "#ffb3b1"
    if t == "cash":
        return "payments", "#636262", "#e5e2e1"
    return "account_balance", "#154212", "#154212"


def fetch_bank_accounts() -> list[dict[str, Any]]:
    """Aligned with BANK_ACCOUNTS from sample_data (includes UI icon fields)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT bank_account_id, account_name, bank_name, account_number_masked,
                       account_type::text AS account_type,
                       beginning_balance, total_debits, total_credits, ending_balance
                FROM v_account_balances
                ORDER BY account_name
                """
            )
            rows = cur.fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        icon, icon_color, accent = _icon_for_account_type(row["account_type"])
        td = _num(row["total_debits"])
        tc = _num(row["total_credits"])
        # Match sample_data sign convention: debits column negative for outflows on bank accounts
        deb_display = -td if td else 0.0
        out.append(
            {
                "id": str(row["bank_account_id"]),
                "account_name": row["account_name"],
                "bank_name": row["bank_name"],
                "masked": row["account_number_masked"],
                "account_type": row["account_type"],
                "icon": icon,
                "icon_color": icon_color,
                "accent": accent,
                "beginning_balance": _num(row["beginning_balance"]),
                "total_debits": deb_display,
                "total_credits": tc,
                "ending_balance": _num(row["ending_balance"]),
            }
        )
    return out


def insert_bank(bank_name: str, bank_type: str) -> str:
    """Insert a bank (institution). bank_type: depository | credit_card. Returns UUID string."""
    name = (bank_name or "").strip()
    bt = (bank_type or "").strip().lower()
    if not name:
        raise ValueError("Institution name is required.")
    if bt not in ("depository", "credit_card"):
        raise ValueError("bank_type must be depository or credit_card.")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO banks (bank_name, bank_type)
                VALUES (%s, %s::bank_type_enum)
                RETURNING id::text AS id
                """,
                (name, bt),
            )
            row = cur.fetchone()
            return str(row["id"])


def fetch_banks() -> list[dict[str, Any]]:
    """All banks for onboarding dropdowns."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, bank_name, bank_type::text AS bank_type
                FROM banks
                ORDER BY bank_name
                """
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def insert_bank_account(
    bank_id: str,
    template_id: str | None,
    account_name: str,
    account_number_masked: str,
    account_type: str,
) -> str:
    """Insert bank_accounts row. template_id may be NULL. Returns UUID string."""
    bid = (bank_id or "").strip()
    an = (account_name or "").strip()
    masked = (account_number_masked or "").strip()
    at = (account_type or "").strip().lower()
    if not bid:
        raise ValueError("Institution is required.")
    if not an:
        raise ValueError("Account name is required.")
    if not masked:
        raise ValueError("Last four (or mask) is required.")
    if at not in ("checking", "savings", "credit_card", "cash"):
        raise ValueError("Invalid account_type.")
    tid = (template_id or "").strip() or None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bank_accounts (bank_id, template_id, account_name, account_number_masked, account_type)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s::account_type_enum)
                RETURNING id::text AS id
                """,
                (bid, tid, an, masked[:10], at),
            )
            row = cur.fetchone()
            return str(row["id"])


def count_transactions_for_bank_account(bank_account_id: str) -> int:
    """Number of ledger transaction rows for this account."""
    aid = (bank_account_id or "").strip()
    if not aid:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int AS c
                FROM transactions
                WHERE bank_account_id = %s::uuid
                """,
                (aid,),
            )
            row = cur.fetchone()
            return int(row["c"] or 0)


def fetch_bank_accounts_manage() -> list[dict[str, Any]]:
    """Onboarding management list: account + institution + template + txn count."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ba.id::text AS id,
                    ba.bank_id::text AS bank_id,
                    b.bank_name,
                    b.bank_type::text AS bank_type,
                    ba.account_name,
                    ba.account_number_masked,
                    ba.account_type::text AS account_type,
                    ba.template_id::text AS template_id,
                    it.template_name AS template_name,
                    ba.ledger_coa_id::text AS ledger_coa_id,
                    lc.account_number AS ledger_account_number,
                    lc.account_name AS ledger_account_name,
                    (
                        SELECT COUNT(*)::int FROM transactions t
                        WHERE t.bank_account_id = ba.id
                          AND (
                              ba.ledger_coa_id IS NULL
                              OR t.coa_id IS DISTINCT FROM ba.ledger_coa_id
                              OR t.source = 'trial_balance_opening'::transaction_source_enum
                          )
                    ) AS txn_count
                FROM bank_accounts ba
                JOIN banks b ON b.id = ba.bank_id
                LEFT JOIN import_templates it ON it.id = ba.template_id
                LEFT JOIN chart_of_accounts lc ON lc.id = ba.ledger_coa_id
                WHERE ba.is_active = TRUE
                ORDER BY b.bank_name, ba.account_name
                """
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def update_bank_account_ledger_coa(
    bank_account_id: str, ledger_coa_id: str | None
) -> str | None:
    """Set or clear ledger_coa_id. Returns None on success, else error message."""
    aid = (bank_account_id or "").strip()
    if not aid:
        return "Missing account id."
    lid = (ledger_coa_id or "").strip() or None
    if lid:
        try:
            UUID(lid)
        except ValueError:
            return "Invalid chart account id."
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE bank_accounts
                SET ledger_coa_id = %s::uuid
                WHERE id = %s::uuid AND is_active = TRUE
                """,
                (lid, aid),
            )
            if cur.rowcount == 0:
                return "Account not found or inactive."
    resync_trial_balance_opening_transactions()
    return None


def delete_bank_account_if_safe(bank_account_id: str) -> str | None:
    """
    Delete a bank account only when it has no transactions.
    Clears ledger_submissions first (FK RESTRICT). Returns None on success, else error message.
    """
    aid = (bank_account_id or "").strip()
    if not aid:
        return "Missing account id."
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*)::int AS c FROM transactions WHERE bank_account_id = %s::uuid",
                (aid,),
            )
            n = int(cur.fetchone()["c"] or 0)
            if n > 0:
                return (
                    "This account has ledger transactions and cannot be removed. "
                    f"({n} transaction{'s' if n != 1 else ''})"
                )
            cur.execute(
                "DELETE FROM ledger_submissions WHERE bank_account_id = %s::uuid",
                (aid,),
            )
            cur.execute("DELETE FROM bank_accounts WHERE id = %s::uuid", (aid,))
            if cur.rowcount == 0:
                return "Account not found or already removed."
    return None


def fetch_chart_of_accounts() -> list[dict[str, Any]]:
    """Aligned with CHART_OF_ACCOUNTS (type title case for display)."""
    type_map = {
        "asset": "Asset",
        "liability": "Liability",
        "equity": "Equity",
        "income": "Income",
        "expense": "Expense",
    }
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, account_number, account_name,
                       account_type::text AS atype, account_subtype
                FROM chart_of_accounts
                WHERE is_active = TRUE
                ORDER BY account_number
                """
            )
            rows = cur.fetchall()
    result = []
    for row in rows:
        at = (row["atype"] or "").lower()
        sub = row["account_subtype"] or ""
        sub_disp = sub.replace("_", " ").title() if sub else ""
        result.append(
            {
                "id": row["id"],
                "number": row["account_number"],
                "name": row["account_name"],
                "type": type_map.get(at, at.title()),
                "subtype": sub_disp,
            }
        )
    return result


_COA_TYPES: frozenset[str] = frozenset(
    {"asset", "liability", "equity", "income", "expense"}
)


def insert_chart_of_account(
    *,
    account_number: str,
    account_name: str,
    account_type: str,
    account_subtype: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Insert one chart_of_accounts row. Returns (new_id, None) on success,
    (None, error_message) on validation or duplicate account_number.
    """
    num = (account_number or "").strip()[:20]
    name = (account_name or "").strip()[:255]
    at = (account_type or "").strip().lower()
    sub = (account_subtype or "").strip()[:100] or None
    if not num or not name:
        return None, "Account number and account name are required."
    if at not in _COA_TYPES:
        return None, "Invalid account type."
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chart_of_accounts (account_number, account_name, account_type, account_subtype)
                    VALUES (%s, %s, %s::coa_account_type_enum, %s)
                    RETURNING id::text AS id
                    """,
                    (num, name, at, sub),
                )
                row = cur.fetchone()
        if not row:
            return None, "Insert failed."
        return str(row["id"]), None
    except pg_errors.UniqueViolation:
        return None, f"Account number {num} already exists."
    except Exception as e:
        return None, str(e)


def fetch_chart_of_account_by_id(coa_id: str) -> dict[str, Any] | None:
    """One chart row for edit forms; type is lowercase enum string."""
    cid = (coa_id or "").strip()
    if not cid:
        return None
    try:
        UUID(cid)
    except ValueError:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, account_number, account_name,
                       account_type::text AS atype, account_subtype
                FROM chart_of_accounts
                WHERE id = %s::uuid
                """,
                (cid,),
            )
            row = cur.fetchone()
    if not row:
        return None
    at = (row["atype"] or "").lower()
    sub = row["account_subtype"] or ""
    return {
        "id": row["id"],
        "number": row["account_number"],
        "name": row["account_name"],
        "type": at,
        "subtype": sub,
    }


def update_chart_of_account(
    coa_id: str,
    *,
    account_number: str,
    account_name: str,
    account_type: str,
    account_subtype: str | None = None,
) -> tuple[bool, str | None]:
    """
    Update chart_of_accounts. Returns (True, None) on success, (False, error_message) on failure.
    """
    cid = (coa_id or "").strip()
    if not cid:
        return False, "Account id is required."
    try:
        UUID(cid)
    except ValueError:
        return False, "Invalid account id."
    num = (account_number or "").strip()[:20]
    name = (account_name or "").strip()[:255]
    at = (account_type or "").strip().lower()
    sub = (account_subtype or "").strip()[:100] or None
    if not num or not name:
        return False, "Account number and account name are required."
    if at not in _COA_TYPES:
        return False, "Invalid account type."
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE chart_of_accounts
                    SET account_number = %s,
                        account_name = %s,
                        account_type = %s::coa_account_type_enum,
                        account_subtype = %s
                    WHERE id = %s::uuid
                    """,
                    (num, name, at, sub, cid),
                )
                if cur.rowcount == 0:
                    return False, "Chart account not found."
        return True, None
    except pg_errors.UniqueViolation:
        return False, f"Account number {num} already exists."
    except Exception as e:
        return False, str(e)


def count_transactions_for_coa(coa_id: str) -> int:
    """Rows in transactions referencing this chart account (any status)."""
    cid = (coa_id or "").strip()
    if not cid:
        return 0
    try:
        UUID(cid)
    except ValueError:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int AS n
                FROM transactions
                WHERE coa_id = %s::uuid
                """,
                (cid,),
            )
            row = cur.fetchone()
    return int(row["n"]) if row else 0


def count_payee_rules_for_coa(coa_id: str) -> int:
    """Rows in payee_rules referencing this chart account."""
    cid = (coa_id or "").strip()
    if not cid:
        return 0
    try:
        UUID(cid)
    except ValueError:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int AS n
                FROM payee_rules
                WHERE coa_id = %s::uuid
                """,
                (cid,),
            )
            row = cur.fetchone()
    return int(row["n"]) if row else 0


def delete_chart_of_account(coa_id: str) -> tuple[bool, str | None]:
    """
    Delete a chart row if it has no transactions. Trial balance lines for this
    COA are removed in the same transaction. Payee rules block delete until removed.
    Returns (True, None) or (False, message).
    """
    cid = (coa_id or "").strip()
    if not cid:
        return False, "Account id is required."
    try:
        UUID(cid)
    except ValueError:
        return False, "Invalid account id."
    n = count_transactions_for_coa(cid)
    if n > 0:
        return (
            False,
            "This account has posted or pending transactions assigned to it. "
            "Edit the account or reclassify those transactions before deleting.",
        )
    pr = count_payee_rules_for_coa(cid)
    if pr > 0:
        return (
            False,
            "This account is still used by payee rules. Remove or reassign those first.",
        )
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM trial_balance_entries WHERE coa_id = %s::uuid",
                    (cid,),
                )
                cur.execute(
                    "DELETE FROM chart_of_accounts WHERE id = %s::uuid",
                    (cid,),
                )
                if cur.rowcount == 0:
                    return False, "Chart account not found."
        return True, None
    except pg_errors.IntegrityError as e:
        if getattr(e, "pgcode", None) == "23503":
            return (
                False,
                "This account cannot be deleted because it is still referenced by another record. "
                "Remove payee rules or other links first.",
            )
        return False, str(e)
    except Exception as e:
        return False, str(e)


def fetch_ledger_transactions(
    bank_account_id: str, *, classification_only: bool = False
) -> list[dict[str, Any]]:
    """Aligned with LEDGER_TRANSACTIONS.

    When classification_only is True, omit mirrored ledger-leg rows (coa_id = bank ledger COA)
    so the register shows one line per import event when double-posting is enabled.
    """
    aid = (bank_account_id or "").strip()
    if not aid:
        return []
    extra = ""
    if classification_only:
        extra = """
            AND (
                ba.ledger_coa_id IS NULL
                OR t.coa_id IS DISTINCT FROM ba.ledger_coa_id
                OR t.source = 'trial_balance_opening'::transaction_source_enum
            )
        """
    params: tuple[Any, ...] = (aid,)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT t.date, t.payee, t.description, t.debit_amount, t.credit_amount,
                       t.status::text AS st, coa.account_number
                FROM transactions t
                JOIN bank_accounts ba ON ba.id = t.bank_account_id
                LEFT JOIN chart_of_accounts coa ON coa.id = t.coa_id
                WHERE t.bank_account_id = %s::uuid
                {extra}
                ORDER BY t.date DESC, t.created_at DESC
                """,
                params,
            )
            rows = cur.fetchall()

    out = []
    for row in rows:
        st = (row["st"] or "").lower()
        flagged = st == "flagged"
        coa = row["account_number"]
        out.append(
            {
                "date": _fmt_ledger_date(row["date"]),
                "payee": row["payee"] or "",
                "sub": row["description"] or "",
                "coa": coa,
                "debit": _num(row["debit_amount"]) if _num(row["debit_amount"]) else None,
                "credit": _num(row["credit_amount"]) if _num(row["credit_amount"]) else None,
                "status": st,
                "flagged": flagged,
            }
        )
    return out


def fetch_ledger_summary(bank_account_id: str) -> dict[str, Any]:
    """Aligned with LEDGER_SUMMARY for one bank account."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT beginning_balance, total_debits, total_credits, ending_balance
                FROM v_account_balances
                WHERE bank_account_id = %s
                """,
                (bank_account_id,),
            )
            row = cur.fetchone()
    if not row:
        return {
            "beginning_balance": 0.0,
            "total_debits": 0.0,
            "total_credits": 0.0,
            "ending_balance": 0.0,
            "is_balanced": True,
        }
    beg = _num(row["beginning_balance"])
    td = _num(row["total_debits"])
    tc = _num(row["total_credits"])
    end = _num(row["ending_balance"])
    return {
        "beginning_balance": beg,
        "total_debits": td,
        "total_credits": tc,
        "ending_balance": end,
        "is_balanced": abs(td - tc) < 0.01 or True,
    }


def fetch_import_templates() -> list[dict[str, Any]]:
    """Shape compatible with IMPORT_TEMPLATES (accounts list may be empty from DB)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, template_name AS name, template_type::text AS type,
                       column_map
                FROM import_templates
                ORDER BY template_name
                """
            )
            rows = cur.fetchall()
    result = []
    for row in rows:
        cm = row["column_map"]
        if isinstance(cm, str):
            import json

            cm = json.loads(cm)
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "accounts": [],
                "column_map": cm if isinstance(cm, dict) else {},
            }
        )
    return result


def fetch_import_template_by_id(template_id: str) -> dict[str, Any] | None:
    tid = (template_id or "").strip()
    if not tid:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, template_name AS name, template_type::text AS type,
                       column_map
                FROM import_templates
                WHERE id = %s::uuid
                """,
                (tid,),
            )
            row = cur.fetchone()
    if not row:
        return None
    cm = row["column_map"]
    if isinstance(cm, str):
        cm = json.loads(cm)
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "accounts": [],
        "column_map": cm if isinstance(cm, dict) else {},
    }


def fetch_bank_account_import_context(bank_account_id: str) -> dict[str, Any] | None:
    """
    Bank account row with linked import template for CSV processing.
    Returns None if account not found.
    """
    aid = (bank_account_id or "").strip()
    if not aid:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ba.id::text AS bank_account_id,
                       ba.account_type::text AS account_type,
                       ba.template_id::text AS template_id,
                       it.template_type::text AS template_type,
                       it.column_map
                FROM bank_accounts ba
                LEFT JOIN import_templates it ON it.id = ba.template_id
                WHERE ba.id = %s::uuid
                """,
                (aid,),
            )
            row = cur.fetchone()
    if not row:
        return None
    cm = row["column_map"]
    if isinstance(cm, str):
        cm = json.loads(cm)
    return {
        "bank_account_id": row["bank_account_id"],
        "account_type": row["account_type"],
        "template_id": row["template_id"],
        "template_type": row["template_type"],
        "column_map": cm if isinstance(cm, dict) else {},
    }


def insert_ledger_import_batch_and_transactions(
    *,
    bank_account_id: str,
    template_id: str,
    filename: str,
    period_start: date | None,
    period_end: date | None,
    transaction_rows: list[dict[str, Any]],
) -> str:
    """
    Insert one import_batches row and all transactions in a single DB transaction.
    Each item in transaction_rows must have: date (date), payee (str), payee_normalized (str),
    debit_amount (float), credit_amount (float), description (str|None), coa_id (str|None),
    source ('bank_import'|'credit_card_import').

    When bank_accounts.ledger_coa_id is set and differs from classification coa_id, inserts a
    second row with that COA and debit/credit swapped, sharing posting_group_id with the first leg.

    Returns the new import_batches id as text.
    """
    aid = (bank_account_id or "").strip()
    tid = (template_id or "").strip()
    fn = (filename or "").strip() or "upload.csv"
    if not aid or not tid:
        raise ValueError("bank_account_id and template_id are required.")
    if not transaction_rows:
        raise ValueError("No transaction rows to import.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ledger_coa_id::text AS ledger_coa_id
                FROM bank_accounts
                WHERE id = %s::uuid
                """,
                (aid,),
            )
            ba_row = cur.fetchone()
            ledger_coa_raw = (ba_row["ledger_coa_id"] or "").strip() if ba_row else ""

            cur.execute(
                """
                INSERT INTO import_batches (
                    bank_account_id, template_id, filename, period_start, period_end,
                    record_count, status
                )
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, 'processing'::batch_status_enum)
                RETURNING id::text AS id
                """,
                (aid, tid, fn[:500], period_start, period_end, 0),
            )
            batch_row = cur.fetchone()
            batch_id = str(batch_row["id"])

            tuples: list[tuple[Any, ...]] = []
            for r in transaction_rows:
                d = r["date"]
                if isinstance(d, datetime):
                    d = d.date()
                cls_coa = (r.get("coa_id") or "").strip() or None
                deb = float(r.get("debit_amount") or 0)
                crd = float(r.get("credit_amount") or 0)
                src = r.get("source") or "bank_import"
                desc = r.get("description")
                payee = (r.get("payee") or "")[:500]
                payee_n = (r.get("payee_normalized") or "")[:500]

                second_leg = bool(
                    ledger_coa_raw
                    and cls_coa
                    and ledger_coa_raw != cls_coa
                )
                group_id: str | None = str(uuid.uuid4()) if second_leg else None

                tuples.append(
                    (
                        aid,
                        batch_id,
                        cls_coa,
                        group_id,
                        d,
                        payee,
                        payee_n,
                        deb,
                        crd,
                        desc,
                        src,
                        "cleared",
                    )
                )
                if second_leg:
                    tuples.append(
                        (
                            aid,
                            batch_id,
                            ledger_coa_raw,
                            group_id,
                            d,
                            payee,
                            payee_n,
                            crd,
                            deb,
                            desc,
                            src,
                            "cleared",
                        )
                    )

            n_inserted = len(tuples)
            execute_values(
                cur,
                """
                INSERT INTO transactions (
                    bank_account_id, import_batch_id, coa_id, posting_group_id, date, payee,
                    payee_normalized, debit_amount, credit_amount, description, source, status
                ) VALUES %s
                """,
                tuples,
                template=(
                    "(%s, %s, %s, %s::uuid, %s, %s, %s, %s, %s, %s, "
                    "%s::transaction_source_enum, %s::transaction_status_enum)"
                ),
            )

            cur.execute(
                """
                UPDATE import_batches
                SET status = 'complete'::batch_status_enum,
                    record_count = %s
                WHERE id = %s::uuid
                """,
                (n_inserted, batch_id),
            )

    return batch_id


def update_import_template(
    template_id: str,
    template_name: str,
    column_map: dict[str, Any],
    template_type: str,
) -> bool:
    """Update name and column_map; only if row matches template_type. Returns True if a row was updated."""
    tid = (template_id or "").strip()
    name = (template_name or "").strip()[:255]
    tt = template_type if template_type in ("bank_statement", "credit_card") else "bank_statement"
    if not tid or not name:
        return False
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE import_templates
                SET template_name = %s,
                    column_map = %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s::uuid AND template_type = %s::template_type_enum
                """,
                (name, json.dumps(column_map), tid, tt),
            )
            return cur.rowcount is not None and cur.rowcount > 0


def insert_import_template(
    template_name: str,
    template_type: str,
    column_map: dict[str, Any],
) -> str:
    """Insert a bank or credit card import template. Returns new row id as text."""
    name = (template_name or "").strip()[:255] or "Untitled template"
    tt = template_type if template_type in ("bank_statement", "credit_card") else "bank_statement"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO import_templates (template_name, template_type, column_map)
                VALUES (%s, %s::template_type_enum, %s::jsonb)
                RETURNING id::text AS id
                """,
                (name, tt, json.dumps(column_map)),
            )
            row = cur.fetchone()
    return row["id"] if row else ""


def _normalize_payee_pattern(s: str) -> str:
    return " ".join((s or "").split()).strip().lower()


def schema_has_payee_rules_bank_account_id() -> bool:
    """
    True if public.payee_rules includes bank_account_id (post-migration).
    False when the database is still on the legacy template_id-only schema or on error.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'payee_rules'
                      AND column_name = 'bank_account_id'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def fetch_payee_rules_for_bank_account(bank_account_id: str) -> list[dict[str, Any]]:
    """payee_pattern is stored normalized; joins COA for display."""
    aid = (bank_account_id or "").strip()
    if not aid:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pr.id::text AS id,
                       pr.payee_pattern,
                       pr.coa_id::text AS coa_id,
                       coa.account_number,
                       coa.account_name
                FROM payee_rules pr
                JOIN chart_of_accounts coa ON coa.id = pr.coa_id
                WHERE pr.bank_account_id = %s::uuid
                ORDER BY pr.payee_pattern
                """,
                (aid,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": row["id"],
            "payee_pattern": row["payee_pattern"],
            "coa_id": row["coa_id"],
            "coa_number": row["account_number"],
            "coa_name": row["account_name"],
        }
        for row in rows
    ]


def upsert_payee_rule_for_bank_account(
    bank_account_id: str, payee_pattern: str, coa_id: str
) -> None:
    """payee_pattern must already be normalized. IDs are UUID strings."""
    aid = (bank_account_id or "").strip()
    pid = (payee_pattern or "").strip()
    cid = (coa_id or "").strip()
    if not aid or not pid or not cid:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payee_rules (payee_pattern, coa_id, bank_account_id, transaction_type, confidence)
                VALUES (%s, %s::uuid, %s::uuid, 'debit', 1.000)
                ON CONFLICT (payee_pattern, bank_account_id)
                DO UPDATE SET coa_id = EXCLUDED.coa_id
                """,
                (pid, cid, aid),
            )


def delete_payee_rule_for_bank_account(bank_account_id: str, payee_pattern: str) -> int:
    aid = (bank_account_id or "").strip()
    pid = (payee_pattern or "").strip()
    if not aid or not pid:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM payee_rules
                WHERE bank_account_id = %s::uuid AND payee_pattern = %s
                """,
                (aid, pid),
            )
            return cur.rowcount or 0


def resolve_coa_id_for_bank_payee(payee_raw: str, bank_account_id: str) -> str | None:
    """
    Exact match on normalized payee text for the given bank account.
    Call from CSV import when creating transactions.
    """
    pn = _normalize_payee_pattern(payee_raw)
    aid = (bank_account_id or "").strip()
    if not pn or not aid:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT coa_id::text AS id
                FROM payee_rules
                WHERE bank_account_id = %s::uuid AND payee_pattern = %s
                LIMIT 1
                """,
                (aid, pn),
            )
            row = cur.fetchone()
    return row["id"] if row else None


def fetch_trial_balance_report() -> list[dict[str, Any]]:
    """TRIAL_BALANCE_REPORT rows from trial_balance_entries (COA-focused; no bank column)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT coa.account_number AS coa_number,
                       coa.account_number || ' - ' || coa.account_name AS coa,
                       t.debit_amount, t.credit_amount
                FROM trial_balance_entries t
                JOIN chart_of_accounts coa ON coa.id = t.coa_id
                WHERE t.status IN ('pending', 'confirmed')
                ORDER BY coa.account_number
                """
            )
            rows = cur.fetchall()
    out = []
    for row in rows:
        deb = _num(row["debit_amount"])
        crd = _num(row["credit_amount"])
        out.append(
            {
                "coa_number": row["coa_number"],
                "coa": row["coa"],
                "debits": deb if deb else None,
                "credits": crd if crd else None,
            }
        )
    return out


def _coa_number_range_clause(
    coa_from: str | None, coa_to: str | None
) -> tuple[str, list[Any]]:
    """Extra WHERE fragment for chart_of_accounts.account_number (lexicographic)."""
    cf = (coa_from or "").strip()
    ct = (coa_to or "").strip()
    if not cf and not ct:
        return "", []
    if cf and ct:
        return " AND account_number BETWEEN %s AND %s ", [cf, ct]
    if cf:
        return " AND account_number >= %s ", [cf]
    return " AND account_number <= %s ", [ct]


_GL_STATUS_FILTER = " AND t.status IN ('pending', 'cleared') "
# GL includes flagged so activity is visible; ledger review can still flag items in the UI.
_GL_LEDGER_STATUS_FILTER = " AND t.status IN ('pending', 'cleared', 'flagged') "


def fetch_general_ledger_detail(
    period_start: date,
    period_end: date,
    coa_number_from: str | None,
    coa_number_to: str | None,
    bank_account_id: str | None,
) -> list[dict[str, Any]]:
    """
    General ledger by chart account: beginning balance = trial_balance_entries net (debit
    minus credit) for the COA, same scope as Reports Trial Balance (pending and confirmed;
    includes TB-IMPORT book when summing all banks), plus categorized transaction net before
    period_start (optional bank filter on transactions). Period lines and ending balance follow.
    Uncategorized (coa_id NULL) in a separate section when no chart account range filter.

    Returns list of dicts: coa_number, coa_name, beginning_balance, ending_balance,
    lines[{date, payee, description, debit, credit, balance}].
    """
    ps, pe = period_start, period_end
    if ps > pe:
        ps, pe = pe, ps

    bank_id = (bank_account_id or "").strip() or None
    if bank_id:
        try:
            UUID(bank_id)
        except ValueError:
            bank_id = None

    frag, frag_params = _coa_number_range_clause(coa_number_from, coa_number_to)
    _cf = (coa_number_from or "").strip()
    _ct = (coa_number_to or "").strip()
    include_uncategorized = not _cf and not _ct

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text AS id, account_number, account_name,
                       account_type::text AS atype
                FROM chart_of_accounts
                WHERE is_active = TRUE
                {frag}
                ORDER BY account_number
                """,
                frag_params,
            )
            coa_rows = cur.fetchall()

    if not coa_rows:
        return []

    ids = [str(r["id"]) for r in coa_rows]
    placeholders = ",".join(["%s::uuid"] * len(ids))

    bank_sql = ""
    bank_params: list[Any] = []
    if bank_id:
        bank_sql = " AND t.bank_account_id = %s::uuid "
        bank_params = [bank_id]

    beg_map: dict[str, float] = {i: 0.0 for i in ids}
    lines_by_coa: dict[str, list[dict[str, Any]]] = {i: [] for i in ids}

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Trial balance opening: same rows as Reports ▸ Trial Balance (pending + confirmed).
            # Include TB-IMPORT book (CSV onboarding lines live there); only filter by bank when
            # user picks a single bank account.
            tb_scope_sql = ""
            tb_scope_params: list[Any] = []
            if bank_id:
                tb_scope_sql = " AND te.bank_account_id = %s::uuid "
                tb_scope_params = [bank_id]

            cur.execute(
                f"""
                SELECT te.coa_id::text AS cid,
                       COALESCE(SUM(te.debit_amount - te.credit_amount), 0) AS tb_net
                FROM trial_balance_entries te
                WHERE te.status IN ('pending', 'confirmed')
                  AND te.coa_id IN ({placeholders})
                  {tb_scope_sql}
                GROUP BY te.coa_id
                """,
                [*ids, *tb_scope_params],
            )
            for row in cur.fetchall():
                beg_map[str(row["cid"])] = _num(row["tb_net"])

            cur.execute(
                f"""
                SELECT t.coa_id::text AS cid, COALESCE(SUM(t.debit_amount - t.credit_amount), 0) AS beg
                FROM transactions t
                WHERE t.coa_id IN ({placeholders})
                  AND t.coa_id IS NOT NULL
                  AND t.date < %s
                  {_GL_LEDGER_STATUS_FILTER}
                  {bank_sql}
                GROUP BY t.coa_id
                """,
                [*ids, ps, *bank_params],
            )
            for row in cur.fetchall():
                cid = str(row["cid"])
                beg_map[cid] = beg_map.get(cid, 0.0) + _num(row["beg"])

            cur.execute(
                f"""
                SELECT t.coa_id::text AS cid, t.date, t.payee, t.description,
                       t.debit_amount, t.credit_amount, t.created_at
                FROM transactions t
                WHERE t.coa_id IN ({placeholders})
                  AND t.date >= %s AND t.date <= %s
                  {_GL_LEDGER_STATUS_FILTER}
                  {bank_sql}
                ORDER BY t.coa_id, t.date, t.created_at
                """,
                [*ids, ps, pe, *bank_params],
            )
            for row in cur.fetchall():
                cid = str(row["cid"])
                d = row["date"]
                ds = d.isoformat() if hasattr(d, "isoformat") else str(d)
                deb = _num(row["debit_amount"])
                crd = _num(row["credit_amount"])
                lines_by_coa[cid].append(
                    {
                        "date": ds,
                        "payee": row["payee"] or "",
                        "description": row["description"] or "",
                        "debit": deb if deb else None,
                        "credit": crd if crd else None,
                        "balance": 0.0,
                    }
                )

            beg_uncat = 0.0
            uncat_lines: list[dict[str, Any]] = []
            if include_uncategorized:
                cur.execute(
                    f"""
                    SELECT COALESCE(SUM(t.debit_amount - t.credit_amount), 0) AS beg
                    FROM transactions t
                    WHERE t.coa_id IS NULL
                      AND t.date < %s
                      {_GL_LEDGER_STATUS_FILTER}
                      {bank_sql}
                    """,
                    [ps, *bank_params],
                )
                urow = cur.fetchone()
                beg_uncat = _num(urow["beg"]) if urow else 0.0

                cur.execute(
                    f"""
                    SELECT t.date, t.payee, t.description,
                           t.debit_amount, t.credit_amount, t.created_at
                    FROM transactions t
                    WHERE t.coa_id IS NULL
                      AND t.date >= %s AND t.date <= %s
                      {_GL_LEDGER_STATUS_FILTER}
                      {bank_sql}
                    ORDER BY t.date, t.created_at
                    """,
                    [ps, pe, *bank_params],
                )
                for row in cur.fetchall():
                    d = row["date"]
                    ds = d.isoformat() if hasattr(d, "isoformat") else str(d)
                    deb = _num(row["debit_amount"])
                    crd = _num(row["credit_amount"])
                    uncat_lines.append(
                        {
                            "date": ds,
                            "payee": row["payee"] or "",
                            "description": row["description"] or "",
                            "debit": deb if deb else None,
                            "credit": crd if crd else None,
                            "balance": 0.0,
                        }
                    )

    out: list[dict[str, Any]] = []
    for r in coa_rows:
        cid = str(r["id"])
        num = r["account_number"]
        name = r["account_name"]
        beg = beg_map.get(cid, 0.0)
        lines = lines_by_coa.get(cid, [])
        run = beg
        for ln in lines:
            deb = _num(ln["debit"] or 0)
            crd = _num(ln["credit"] or 0)
            run = run + deb - crd
            ln["balance"] = run
        ending = run
        atype = (r.get("atype") or "").lower()
        out.append(
            {
                "coa_number": num,
                "coa_name": name,
                "coa_type": atype,
                "beginning_balance": beg,
                "ending_balance": ending,
                "lines": lines,
            }
        )

    if include_uncategorized and (
        abs(beg_uncat) > 1e-9 or len(uncat_lines) > 0
    ):
        run_u = beg_uncat
        for ln in uncat_lines:
            deb = _num(ln["debit"] or 0)
            crd = _num(ln["credit"] or 0)
            run_u = run_u + deb - crd
            ln["balance"] = run_u
        out.append(
            {
                "coa_number": "—",
                "coa_name": "Uncategorized (no chart account assigned)",
                "coa_type": "expense",
                "beginning_balance": beg_uncat,
                "ending_balance": run_u,
                "lines": uncat_lines,
            }
        )

    return out


def _bank_account_id_for_tb_row(cur, row: dict[str, Any], default_id: str) -> str:
    raw = row.get("bank_account_id") or row.get("Bank account id")
    if raw is None or str(raw).strip() == "":
        return default_id
    aid = str(raw).strip()
    try:
        UUID(aid)
    except (ValueError, TypeError):
        return default_id
    cur.execute(
        "SELECT 1 FROM bank_accounts WHERE id = %s::uuid AND is_active = TRUE",
        (aid,),
    )
    if cur.fetchone():
        return aid
    return default_id


def seed_opening_transactions_from_trial_balance(cur, reference_name: str) -> int:
    """
    One cleared transaction per bank account with ledger_coa_id: net TB amount for that COA
    on the TB-IMPORT book. Replaces prior trial_balance_opening rows so re-confirming TB is idempotent.

    Amounts use bank-register columns (debit reduces carry, credit increases) to match
    v_account_balances and CSV imports—not raw GAAP debit/credit on the TB line.
    """
    ref = (reference_name or "").strip()[:255]
    if not ref:
        return 0
    cur.execute(
        """
        SELECT id::text FROM bank_accounts
        WHERE account_number_masked = 'TB-IMPORT' LIMIT 1
        """
    )
    row = cur.fetchone()
    tb_import_id = str(row["id"]) if row else None
    if not tb_import_id:
        return 0

    cur.execute(
        """
        DELETE FROM transactions
        WHERE source = 'trial_balance_opening'::transaction_source_enum
        """
    )

    cur.execute(
        """
        SELECT ba.id::text AS ba_id, ba.ledger_coa_id::text AS lcid
        FROM bank_accounts ba
        WHERE ba.is_active = TRUE AND ba.ledger_coa_id IS NOT NULL
        """
    )
    accounts = cur.fetchall()
    today = date.today()
    payee = "Trial balance opening"
    payee_n = "trial balance opening"
    n_ins = 0
    for acc in accounts:
        bid = acc["ba_id"]
        lcid = acc["lcid"]
        cur.execute(
            """
            SELECT COALESCE(SUM(te.debit_amount), 0) AS sdeb,
                   COALESCE(SUM(te.credit_amount), 0) AS scrd
            FROM trial_balance_entries te
            WHERE te.status = 'confirmed'::trial_balance_status_enum
              AND te.bank_account_id = %s::uuid
              AND te.coa_id = %s::uuid
              AND te.reference_name = %s
            """,
            (tb_import_id, lcid, ref),
        )
        rrow = cur.fetchone()
        sdeb = float(rrow["sdeb"] or 0)
        scrd = float(rrow["scrd"] or 0)
        net = sdeb - scrd
        if abs(net) < 0.0001:
            continue
        # Bank-register: ending = baseline - debits + credits (same as statement imports).
        # Positive TB net (asset-style) → credit column so carry increases.
        if net >= 0:
            deb_amt, cr_amt = 0.0, net
        else:
            deb_amt, cr_amt = -net, 0.0
        cur.execute(
            """
            INSERT INTO transactions (
                bank_account_id, import_batch_id, coa_id, posting_group_id, date,
                payee, payee_normalized, debit_amount, credit_amount, description,
                source, status, is_categorized
            ) VALUES (
                %s::uuid, NULL, %s::uuid, NULL, %s,
                %s, %s, %s, %s, %s,
                'trial_balance_opening'::transaction_source_enum,
                'cleared'::transaction_status_enum, TRUE
            )
            """,
            (
                bid,
                lcid,
                today,
                payee[:500],
                payee_n[:500],
                deb_amt,
                cr_amt,
                f"Opening ({ref})"[:500],
            ),
        )
        n_ins += 1
    return n_ins


def resync_trial_balance_opening_transactions() -> None:
    """
    Re-run TB opening seed using the latest confirmed trial balance batch (by imported_at).
    Call after ledger_coa_id changes so opening transactions exist even if TB was confirmed first.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT reference_name FROM trial_balance_entries
                WHERE status = 'confirmed'::trial_balance_status_enum
                ORDER BY imported_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return
            ref = (row.get("reference_name") or "").strip()
            if not ref:
                return
            seed_opening_transactions_from_trial_balance(cur, ref)


def delete_pending_trial_balance_entries() -> int:
    """Remove onboarding trial balance rows not yet confirmed. Returns deleted row count."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM trial_balance_entries
                WHERE status = 'pending'::trial_balance_status_enum
                """
            )
            return cur.rowcount or 0


def fetch_trial_balance_import_preview() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """TRIAL_BALANCE_IMPORT_PREVIEW and TRIAL_BALANCE_TOTALS."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ba.account_number_masked AS bank_account,
                       coa.account_number || ' - ' || coa.account_name AS coa,
                       t.debit_amount, t.credit_amount,
                       FALSE AS error
                FROM trial_balance_entries t
                JOIN bank_accounts ba ON ba.id = t.bank_account_id
                JOIN chart_of_accounts coa ON coa.id = t.coa_id
                ORDER BY ba.account_number_masked
                """
            )
            rows = cur.fetchall()
    preview = []
    total_deb = 0.0
    total_crd = 0.0
    for row in rows:
        deb = _num(row["debit_amount"])
        crd = _num(row["credit_amount"])
        if deb:
            total_deb += deb
        if crd:
            total_crd += crd
        preview.append(
            {
                "bank_account": row["bank_account"],
                "coa": row["coa"],
                "debits": deb if deb else None,
                "credits": crd if crd else None,
                "error": row["error"],
            }
        )
    totals = {
        "total_debits": total_deb,
        "total_credits": total_crd,
        "is_balanced": abs(total_deb - total_crd) < 0.02,
        "variance": abs(total_deb - total_crd),
    }
    return preview, totals


def first_bank_account_id_non_cash() -> str | None:
    """Default ledger account: first non-cash bank account."""
    for a in fetch_bank_accounts():
        if a.get("account_type") != "cash":
            return a["id"]
    return None


def _type_display_to_coa_db(display: str) -> tuple[str, str | None]:
    """Map UI type label to coa_account_type_enum and subtype."""
    d = (display or "").strip()
    mapping: dict[str, tuple[str, str | None]] = {
        "Asset": ("asset", "current_asset"),
        "Liability": ("liability", "current_liability"),
        "Equity": ("equity", "owners_equity"),
        "Income": ("income", "operating_income"),
        "Expense": ("expense", "overhead"),
    }
    return mapping.get(d, ("asset", "current_asset"))


def ensure_trial_balance_book_bank_account_id() -> UUID:
    """Single placeholder bank account for COA-centric trial balance lines."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM bank_accounts
                WHERE account_number_masked = 'TB-IMPORT'
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                return row["id"]
            cur.execute(
                """
                INSERT INTO banks (bank_name, bank_type)
                VALUES ('Book', 'depository'::bank_type_enum)
                RETURNING id
                """
            )
            bank_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO bank_accounts (bank_id, account_name, account_number_masked, account_type)
                VALUES (%s, 'Trial balance import', 'TB-IMPORT', 'cash'::account_type_enum)
                RETURNING id
                """,
                (bank_id,),
            )
            return cur.fetchone()["id"]


def _parse_coa_label_for_save(label: str) -> tuple[str, str]:
    s = (label or "").strip()
    if " — " in s:
        a, b = s.split(" — ", 1)
        return a.strip()[:20], b.strip()[:255]
    for sep in (" - ", " – "):
        if sep in s:
            parts = s.split(sep, 1)
            return parts[0].strip()[:20], (parts[1].strip() if len(parts) > 1 else s)[:255]
    parts = s.split(None, 1)
    return (parts[0][:20] if parts else "")[:20], (
        parts[1][:255] if len(parts) > 1 else s
    )[:255]


def _strip_leading_account_num_from_line(line: str, num: str) -> str:
    """Remove leading account number from a trial balance line (e.g. '5000 — Rent' → 'Rent')."""
    line = (line or "").strip()
    n = (num or "").strip()
    if not line or not n:
        return ""
    m = re.match(rf"^{re.escape(n)}\s*[-–—:\u2013]\s*(.+)$", line)
    if m:
        return m.group(1).strip()
    if line.startswith(n):
        return line[len(n) :].lstrip(" -–—:\t")
    return ""


def _coa_num_and_name_for_import_row(coa_label: str, full_name_line: str) -> tuple[str, str]:
    """
    Account number from the COA cell; name from embedded label or from the import Full name column.
    """
    num, acc_from_label = _parse_coa_label_for_save(coa_label)
    if not num:
        return "", ""
    fn = (full_name_line or "").strip()
    acc = (acc_from_label or "").strip()
    if acc and acc != num:
        return num, acc[:255]
    derived = _strip_leading_account_num_from_line(fn, num) if fn else ""
    if derived:
        return num, derived[:255]
    if fn and fn.strip() != num:
        return num, fn[:255]
    return num, f"Account {num}"


def save_trial_balance_csv_import(
    reference_name: str,
    rows: list[dict[str, Any]],
) -> int:
    """
    Persist CSV trial balance preview: upsert COAs, insert trial_balance_entries as confirmed.
    Each row dict expects keys: Full name, COA, Type, Debits, Credits (as in Streamlit df).
    Rows use the TB-IMPORT book bank_account_id unless a row dict includes bank_account_id (UUID).
    After insert, seeds opening transactions for bank accounts with ledger_coa_id (see
    seed_opening_transactions_from_trial_balance).
    """
    ref = (reference_name or "").strip()[:255]
    if not ref:
        return 0
    delete_pending_trial_balance_entries()
    default_ba = ensure_trial_balance_book_bank_account_id()
    default_ba_str = str(default_ba)
    inserted = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for r in rows:
                coa_label = str(r.get("COA", "")).strip()
                type_disp = str(r.get("Type", "Asset")).strip()
                deb = _num(r.get("Debits"))
                crd = _num(r.get("Credits"))
                num, acc_name = _coa_num_and_name_for_import_row(
                    coa_label, str(r.get("Full name", ""))
                )
                if not num:
                    continue
                at, sub = _type_display_to_coa_db(type_disp)
                name = (acc_name or "").strip()[:255] or f"Account {num}"
                cur.execute(
                    """
                    INSERT INTO chart_of_accounts (account_number, account_name, account_type, account_subtype)
                    VALUES (%s, %s, %s::coa_account_type_enum, %s)
                    ON CONFLICT (account_number) DO UPDATE SET
                        account_name = EXCLUDED.account_name
                    RETURNING id
                    """,
                    (num[:20], name, at, sub),
                )
                coa_id = cur.fetchone()["id"]
                row_ba = _bank_account_id_for_tb_row(cur, r, default_ba_str)
                cur.execute(
                    """
                    INSERT INTO trial_balance_entries (
                        bank_account_id, coa_id, reference_name,
                        debit_amount, credit_amount, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, 'confirmed'::trial_balance_status_enum
                    )
                    """,
                    (row_ba, str(coa_id), ref, deb, crd),
                )
                inserted += 1
            seed_opening_transactions_from_trial_balance(cur, ref)
    return inserted
