"""
CSV helpers for bank statement template: headers, column suggestions, preview rows.
"""

from __future__ import annotations

import csv
import io
from typing import Any

BANK_COLUMN_NOT_USED = "— Not used —"

BANK_FIELD_DATE = "date"
BANK_FIELD_TRANSACTION_TYPE = "transaction_type"
BANK_FIELD_PAYEE = "payee"
BANK_FIELD_AMOUNT = "amount"
BANK_FIELD_CHART_OF_ACCOUNT = "chart_of_account"
BANK_FIELD_DESCRIPTION = "description"

BANK_MAP_FIELD_KEYS: tuple[str, ...] = (
    BANK_FIELD_DATE,
    BANK_FIELD_TRANSACTION_TYPE,
    BANK_FIELD_PAYEE,
    BANK_FIELD_AMOUNT,
    BANK_FIELD_CHART_OF_ACCOUNT,
    BANK_FIELD_DESCRIPTION,
)


def _parse_money(cell: str) -> float:
    if cell is None:
        return 0.0
    s = str(cell).replace("$", "").replace(",", "").replace("\t", "").strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def iter_bank_csv_rows(data: bytes) -> list[list[str]]:
    text = io.StringIO(data.decode("utf-8-sig", errors="replace"))
    return list(csv.reader(text))


def bank_statement_csv_headers_from_bytes(data: bytes) -> tuple[list[str], int]:
    """Return (header_cells, header_row_index). First non-empty row wins."""
    rows = iter_bank_csv_rows(data)
    if not rows:
        return [], 0
    for i, row in enumerate(rows[:40]):
        if not row:
            continue
        hdr = [(c or "").strip() for c in row]
        if any(hdr):
            return hdr, i
    return [], 0


def _col_index(headers: list[str], choice: str | None, not_used: str) -> int | None:
    if choice is None or (choice or "").strip() == (not_used or "").strip():
        return None
    c = (choice or "").strip()
    for i, h in enumerate(headers):
        if (h or "").strip() == c:
            return i
    return None


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx < 0:
        return ""
    if idx >= len(row):
        return ""
    v = row[idx]
    return (v if v is not None else "").strip()


def suggest_bank_column_mapping(headers: list[str]) -> dict[str, str]:
    """Best-effort defaults: logical field -> exact header name."""
    out: dict[str, str] = {}

    def norm(h: str) -> str:
        return (h or "").strip()

    def low(h: str) -> str:
        return norm(h).lower()

    for h in headers:
        l = low(h)
        if BANK_FIELD_DATE not in out and (
            l == "date"
            or "transaction date" in l
            or (l.endswith(" date") and "post" not in l)
            or l == "post date"
            or "value date" in l
        ):
            out[BANK_FIELD_DATE] = norm(h)

    for h in headers:
        l = low(h)
        if BANK_FIELD_TRANSACTION_TYPE not in out and (
            l in ("type", "dr/cr", "debit/credit")
            or "transaction type" in l
            or l.startswith("debit")
            or l.startswith("credit")
        ):
            out[BANK_FIELD_TRANSACTION_TYPE] = norm(h)

    for h in headers:
        l = low(h)
        if BANK_FIELD_PAYEE not in out and (
            l in ("description", "payee", "merchant", "narrative", "name")
            or "memo" in l
        ):
            out[BANK_FIELD_PAYEE] = norm(h)

    for h in headers:
        l = low(h)
        if BANK_FIELD_AMOUNT not in out and (
            l == "amount"
            or "amount" in l
            or l in ("value", "net amount")
        ):
            out[BANK_FIELD_AMOUNT] = norm(h)

    for h in headers:
        l = low(h)
        if BANK_FIELD_CHART_OF_ACCOUNT not in out and (
            ("account" in l and "number" in l)
            or l in ("category", "gl code", "account code", "class")
            or "chart" in l
        ):
            out[BANK_FIELD_CHART_OF_ACCOUNT] = norm(h)

    for h in headers:
        l = low(h)
        if BANK_FIELD_DESCRIPTION not in out and l in (
            "note",
            "reference",
            "details",
            "detail",
            "memo",
        ):
            out[BANK_FIELD_DESCRIPTION] = norm(h)

    return out


def _display_type_from_row(amount: float, type_cell: str) -> str:
    t = (type_cell or "").strip().upper()
    if "CREDIT" in t or "DEP" in t or "DEPOSIT" in t:
        return "CREDIT"
    if "DEBIT" in t or "WITH" in t or "WITHDRAW" in t or "PAYMENT" in t:
        return "DEBIT"
    if "CR" in t.split() or t == "C":
        return "CREDIT"
    if "DR" in t.split() or t == "D":
        return "DEBIT"
    return "CREDIT" if amount >= 0 else "DEBIT"


def build_bank_statement_preview_rows(
    data: bytes,
    headers: list[str],
    header_idx: int,
    mapping: dict[str, str],
    not_used: str = BANK_COLUMN_NOT_USED,
    max_rows: int = 3,
) -> list[dict[str, Any]]:
    """
    First max_rows data rows after header, using mapping (header names -> indices).
    Each dict: date, type (CREDIT|DEBIT), payee, amount (float), coa.
    """
    i_date = _col_index(headers, mapping.get(BANK_FIELD_DATE), not_used)
    i_tt = _col_index(headers, mapping.get(BANK_FIELD_TRANSACTION_TYPE), not_used)
    i_payee = _col_index(headers, mapping.get(BANK_FIELD_PAYEE), not_used)
    i_amt = _col_index(headers, mapping.get(BANK_FIELD_AMOUNT), not_used)
    i_coa = _col_index(headers, mapping.get(BANK_FIELD_CHART_OF_ACCOUNT), not_used)
    i_desc = _col_index(headers, mapping.get(BANK_FIELD_DESCRIPTION), not_used)

    rows = iter_bank_csv_rows(data)
    out: list[dict[str, Any]] = []
    for row in rows[header_idx + 1 :]:
        if len(out) >= max_rows:
            break
        if not row or not any((c or "").strip() for c in row):
            continue
        payee = _cell(row, i_payee)
        if not payee and i_desc is not None:
            payee = _cell(row, i_desc)
        amt = _parse_money(_cell(row, i_amt))
        type_raw = _cell(row, i_tt)
        disp_type = _display_type_from_row(amt, type_raw)
        coa = _cell(row, i_coa)
        date_s = _cell(row, i_date)
        out.append(
            {
                "date": date_s or "—",
                "type": disp_type,
                "payee": payee or "—",
                "amount": amt,
                "coa": coa or "—",
            }
        )
    return out


def normalize_payee_for_rule(s: str) -> str:
    """Single canonical form for payee_rules.payee_pattern (exact match at import)."""
    return " ".join((s or "").split()).strip().lower()


def unique_payee_candidates_from_bytes(
    data: bytes,
    headers: list[str],
    header_idx: int,
    mapping: dict[str, str],
    not_used: str = BANK_COLUMN_NOT_USED,
    max_data_rows: int = 200,
    max_unique: int = 100,
) -> list[tuple[str, str]]:
    """
    Scan up to max_data_rows after the header; collect distinct payee/description values.
    Returns up to max_unique (display_text, normalized_key) sorted by display (case-insensitive).
    display_text is the first non-empty raw value seen for that normalized key.
    """
    i_payee = _col_index(headers, mapping.get(BANK_FIELD_PAYEE), not_used)
    i_desc = _col_index(headers, mapping.get(BANK_FIELD_DESCRIPTION), not_used)
    if i_payee is None and i_desc is None:
        return []

    rows = iter_bank_csv_rows(data)
    seen: dict[str, str] = {}
    n_scanned = 0
    for row in rows[header_idx + 1 :]:
        if n_scanned >= max_data_rows:
            break
        if not row or not any((c or "").strip() for c in row):
            continue
        n_scanned += 1
        payee = _cell(row, i_payee)
        if not payee and i_desc is not None:
            payee = _cell(row, i_desc)
        if not payee:
            continue
        key = normalize_payee_for_rule(payee)
        if not key:
            continue
        if key not in seen:
            seen[key] = payee.strip()
        if len(seen) >= max_unique:
            break

    ordered = sorted(seen.items(), key=lambda kv: kv[1].lower())
    return [(display, norm) for norm, display in ordered]
