"""
Read-only queries mapping PostgreSQL rows to the dict shapes used by Streamlit pages.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

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


def fetch_studio_profile() -> dict[str, Any]:
    """Shape aligned with data.sample_data.STUDIO."""
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
        raise RuntimeError("studio_profile has no rows; apply app/db/schema.sql")
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
                (
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
                ),
            )
            if cur.rowcount == 0:
                raise RuntimeError("studio_profile: no row to update")


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
                SELECT account_number, account_name, account_type::text AS atype, account_subtype
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
                "number": row["account_number"],
                "name": row["account_name"],
                "type": type_map.get(at, at.title()),
                "subtype": sub_disp,
            }
        )
    return result


def fetch_ledger_transactions(bank_account_id: str) -> list[dict[str, Any]]:
    """Aligned with LEDGER_TRANSACTIONS."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.date, t.payee, t.description, t.debit_amount, t.credit_amount,
                       t.status::text AS st, coa.account_number
                FROM transactions t
                LEFT JOIN chart_of_accounts coa ON coa.id = t.coa_id
                WHERE t.bank_account_id = %s
                ORDER BY t.date DESC, t.created_at DESC
                """,
                (bank_account_id,),
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


def fetch_trial_balance_report() -> list[dict[str, Any]]:
    """TRIAL_BALANCE_REPORT rows from trial_balance_entries."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ba.account_number_masked AS bank_account,
                       coa.account_number AS coa_number,
                       coa.account_number || ' - ' || coa.account_name AS coa,
                       t.debit_amount, t.credit_amount
                FROM trial_balance_entries t
                JOIN bank_accounts ba ON ba.id = t.bank_account_id
                JOIN chart_of_accounts coa ON coa.id = t.coa_id
                WHERE t.status IN ('pending', 'confirmed')
                ORDER BY ba.account_number_masked, coa.account_number
                """
            )
            rows = cur.fetchall()
    out = []
    for row in rows:
        deb = _num(row["debit_amount"])
        crd = _num(row["credit_amount"])
        out.append(
            {
                "bank_account": row["bank_account"],
                "coa_number": row["coa_number"],
                "coa": row["coa"],
                "debits": deb if deb else None,
                "credits": crd if crd else None,
            }
        )
    return out


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
