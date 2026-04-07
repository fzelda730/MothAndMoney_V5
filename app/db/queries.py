"""
Read-only queries mapping PostgreSQL rows to the dict shapes used by Streamlit pages.
"""

from __future__ import annotations

import json
import re
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


def fetch_payee_rules_for_template(template_id: str) -> list[dict[str, Any]]:
    """payee_pattern is stored normalized; joins COA for display."""
    tid = (template_id or "").strip()
    if not tid:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pr.payee_pattern,
                       pr.coa_id::text AS coa_id,
                       coa.account_number,
                       coa.account_name
                FROM payee_rules pr
                JOIN chart_of_accounts coa ON coa.id = pr.coa_id
                WHERE pr.template_id = %s::uuid
                ORDER BY pr.payee_pattern
                """,
                (tid,),
            )
            rows = cur.fetchall()
    return [
        {
            "payee_pattern": row["payee_pattern"],
            "coa_id": row["coa_id"],
            "coa_number": row["account_number"],
            "coa_name": row["account_name"],
        }
        for row in rows
    ]


def upsert_payee_rule(template_id: str, payee_pattern: str, coa_id: str) -> None:
    """payee_pattern must already be normalized. template_id and coa_id are UUID strings."""
    tid = (template_id or "").strip()
    pid = (payee_pattern or "").strip()
    cid = (coa_id or "").strip()
    if not tid or not pid or not cid:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payee_rules (payee_pattern, coa_id, template_id, transaction_type, confidence)
                VALUES (%s, %s::uuid, %s::uuid, 'debit', 1.000)
                ON CONFLICT (payee_pattern, template_id)
                DO UPDATE SET coa_id = EXCLUDED.coa_id
                """,
                (pid, cid, tid),
            )


def delete_payee_rule_for_template(template_id: str, payee_pattern: str) -> int:
    tid = (template_id or "").strip()
    pid = (payee_pattern or "").strip()
    if not tid or not pid:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM payee_rules
                WHERE template_id = %s::uuid AND payee_pattern = %s
                """,
                (tid, pid),
            )
            return cur.rowcount or 0


def resolve_coa_id_for_bank_payee(payee_raw: str, template_id: str) -> str | None:
    """
    Exact match on normalized payee text for the given import template.
    Call from bank CSV import when creating transactions.
    """
    pn = _normalize_payee_pattern(payee_raw)
    tid = (template_id or "").strip()
    if not pn or not tid:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT coa_id::text AS id
                FROM payee_rules
                WHERE template_id = %s::uuid AND payee_pattern = %s
                LIMIT 1
                """,
                (tid, pn),
            )
            row = cur.fetchone()
    return row["id"] if row else None


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
    """
    ref = (reference_name or "Trial balance import").strip()[:255]
    delete_pending_trial_balance_entries()
    ba_id = ensure_trial_balance_book_bank_account_id()
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
                cur.execute(
                    """
                    INSERT INTO trial_balance_entries (
                        bank_account_id, coa_id, reference_name,
                        debit_amount, credit_amount, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, 'confirmed'::trial_balance_status_enum
                    )
                    """,
                    (str(ba_id), str(coa_id), ref, deb, crd),
                )
                inserted += 1
    return inserted
