"""
Universal Layout Audit for credit card statement PDFs: find transaction zone (3 of 4 header
groups), skip summary tables, normalize dates/descriptions/amounts.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_DATE_TOKENS = (
    "trans date",
    "post date",
    "transaction date",
    "posting date",
    "value date",
    "date",
)
_DESC_TOKENS = (
    "description",
    "transaction",
    "payee",
    "merchant",
    "narrative",
    "details",
)
_AMOUNT_TOKENS = ("amount", "debit", "credit", "charges")
_BALANCE_TOKENS = ("balance", "running balance")

_SUMMARY_RED_FLAGS = (
    "account summary",
    "minimum payment warning",
    "late payment warning",
)


def _normalize_cell(cell: Any) -> str:
    if cell is None:
        return ""
    return " ".join(str(cell).replace("\n", " ").split()).strip()


def _pad_table(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return []
    w = max(len(r) for r in rows)
    return [r + [""] * (w - len(r)) for r in rows]


def _row_text_lower(row: list[str]) -> str:
    return " ".join((c or "").lower() for c in row)


def _header_groups_present(header_joined: str) -> tuple[bool, bool, bool, bool]:
    hj = header_joined.lower()
    has_date = any(t in hj for t in _DATE_TOKENS)
    has_desc = any(t in hj for t in _DESC_TOKENS)
    has_amt = any(t in hj for t in _AMOUNT_TOKENS)
    has_bal = any(t in hj for t in _BALANCE_TOKENS)
    return has_date, has_desc, has_amt, has_bal


def _header_group_count(hj: str) -> int:
    d, desc, a, b = _header_groups_present(hj)
    return int(d) + int(desc) + int(a) + int(b)


def _looks_like_summary_only_header(hj: str) -> bool:
    low = hj.lower()
    if any(r in low for r in _SUMMARY_RED_FLAGS):
        return True
    if "previous balance" in low and "trans date" not in low and "description" not in low:
        return True
    return False


def _tables_from_pdf(pdf: Any) -> list[list[list[str]]]:
    out: list[list[list[str]]] = []
    for page in pdf.pages:
        for raw in page.extract_tables() or []:
            norm: list[list[str]] = []
            for row in raw or []:
                cells = [_normalize_cell(c) for c in (row or [])]
                if any(cells):
                    norm.append(cells)
            norm = _pad_table(norm)
            if len(norm) >= 2:
                out.append(norm)
    return out


def _rows_from_pdf_text(pdf: Any) -> list[list[str]]:
    rows: list[list[str]] = []
    for page in pdf.pages:
        text = page.extract_text(layout=True) or page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            if not line or len(line) < 4:
                continue
            parts = re.split(r"\s{2,}|\t+", line)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 2:
                rows.append(parts)
    return rows


def _extract_statement_period(pdf: Any) -> tuple[date | None, date | None]:
    buf = []
    for page in pdf.pages[:3]:
        buf.append(page.extract_text() or "")
    text = "\n".join(buf)
    m = re.search(
        r"([A-Za-z]{3})\s+(\d{1,2}),\s*(20\d{2})\s*[-–—|]\s*([A-Za-z]{3})\s+(\d{1,2}),\s*(20\d{2})",
        text,
    )
    if not m:
        y = re.search(r"\b(20\d{2})\b", text)
        if y:
            yy = int(y.group(1))
            return date(yy, 1, 1), date(yy, 12, 31)
        return None, None
    m1, d1, y1, m2, d2, y2 = m.groups()
    try:
        ps = date(int(y1), _MONTHS[m1[:3].lower()], int(d1))
        pe = date(int(y2), _MONTHS[m2[:3].lower()], int(d2))
        return ps, pe
    except (ValueError, KeyError):
        return None, None


def _year_for_month(month: int, period_start: date | None, period_end: date | None) -> int:
    if period_start and period_end and period_start.year != period_end.year:
        if month == 12:
            return period_start.year
        return period_end.year
    if period_end:
        return period_end.year
    if period_start:
        return period_start.year
    return datetime.now().year


def _parse_date_cell(
    s: str,
    period_start: date | None,
    period_end: date | None,
) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?$", s)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if y:
            yi = int(y) if len(y) > 2 else 2000 + int(y)
        else:
            yi = _year_for_month(mo, period_start, period_end)
        try:
            return date(yi, mo, d).isoformat()
        except ValueError:
            return None
    m2 = re.match(r"^([A-Za-z]{3})\s+(\d{1,2})$", s)
    if m2:
        mon_s, ds = m2.group(1).lower(), int(m2.group(2))
        if mon_s[:3] not in _MONTHS:
            return None
        mo = _MONTHS[mon_s[:3]]
        yi = _year_for_month(mo, period_start, period_end)
        try:
            return date(yi, mo, ds).isoformat()
        except ValueError:
            return None
    return None


def _parse_money(s: str) -> float | None:
    if not s or not str(s).strip():
        return None
    t = str(s).strip()
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    t = t.replace("$", "").replace(",", "").replace(" ", "")
    if t.startswith("-"):
        neg = True
        t = t[1:]
    elif t.startswith("+"):
        t = t[1:]
    try:
        v = float(t)
        return -v if neg else v
    except ValueError:
        return None


def _clean_description(s: str) -> str:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    return " ".join(s.split()).strip()


AmountMode = Literal["signed_one_column", "debit_credit", "unknown"]


@dataclass
class UniversalLayoutResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    matched_headers: list[str] = field(default_factory=list)
    header_groups: dict[str, bool] = field(default_factory=dict)
    amount_mode: AmountMode = "unknown"
    warnings: list[str] = field(default_factory=list)


def _classify_columns(header_row: list[str]) -> tuple[dict[str, int | None], AmountMode]:
    roles: dict[str, int | None] = {
        "date": None,
        "description": None,
        "amount": None,
        "debit": None,
        "credit": None,
        "balance": None,
    }
    mode: AmountMode = "unknown"
    for i, cell in enumerate(header_row):
        low = (cell or "").strip().lower()
        if roles["date"] is None and any(t in low for t in _DATE_TOKENS):
            roles["date"] = i
        if roles["description"] is None and any(t in low for t in _DESC_TOKENS):
            roles["description"] = i
        if "debit" in low and roles["debit"] is None:
            roles["debit"] = i
        if "credit" in low and roles["credit"] is None and "card" not in low:
            roles["credit"] = i
        if roles["balance"] is None and any(t in low for t in _BALANCE_TOKENS):
            roles["balance"] = i
        if roles["amount"] is None and low == "amount":
            roles["amount"] = i

    if roles["amount"] is None and roles["debit"] is not None and roles["credit"] is not None:
        mode = "debit_credit"
    elif roles["amount"] is not None:
        mode = "signed_one_column"
    elif roles["debit"] is not None or roles["credit"] is not None:
        mode = "debit_credit"

    if roles["date"] is None:
        for i, cell in enumerate(header_row):
            if "date" in (cell or "").lower():
                roles["date"] = i
                break

    return roles, mode


def _fix_roles_when_header_merged(
    roles: dict[str, int | None],
    header_row: list[str],
    sample_data_row: list[str] | None,
) -> dict[str, int | None]:
    """If date and description mapped to the same merged header cell, use typical 4-col CC layout."""
    if (
        sample_data_row
        and len(sample_data_row) >= 4
        and roles.get("date") == roles.get("description")
        and roles.get("date") == 0
    ):
        hj = _row_text_lower(header_row)
        if "description" in hj and "amount" in hj:
            roles = dict(roles)
            roles["description"] = 2
            # Header row may list Amount in column 1 while data amounts are in column 3.
            roles["amount"] = 3
    return roles


def _pick_header_row_index(rows: list[list[str]]) -> tuple[int, str] | None:
    # Headers often appear after summary pages (e.g. Capital One).
    scan = min(120, len(rows))
    best: tuple[int, int, str] | None = None
    for i in range(scan):
        hj = _row_text_lower(rows[i])
        if _looks_like_summary_only_header(hj):
            continue
        cnt = _header_group_count(hj)
        if cnt >= 3:
            if best is None or cnt > best[1]:
                best = (i, cnt, hj)
    if best:
        return best[0], best[2]
    return None


def _parse_data_rows(
    rows: list[list[str]],
    header_idx: int,
    roles: dict[str, int | None],
    mode: AmountMode,
    period_start: date | None,
    period_end: date | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    w = max(len(r) for r in rows) if rows else 0

    def cell(row: list[str], idx: int | None) -> str:
        if idx is None or idx < 0 or idx >= len(row):
            return ""
        return (row[idx] or "").strip()

    for row in rows[header_idx + 1 :]:
        if len(row) < w:
            row = row + [""] * (w - len(row))
        ds = cell(row, roles["date"])
        desc = cell(row, roles["description"])
        if not ds and not desc:
            continue
        low_ds = (ds or "").lower()
        if roles["date"] is not None and (
            low_ds.startswith("trans date") or low_ds.startswith("post date")
        ):
            continue

        date_iso = _parse_date_cell(ds, period_start, period_end)
        if not date_iso and ds:
            continue

        amt: float | None = None
        if mode == "debit_credit":
            dv = _parse_money(cell(row, roles["debit"]))
            cv = _parse_money(cell(row, roles["credit"]))
            if dv is not None and dv != 0:
                amt = -abs(dv)
            elif cv is not None and cv != 0:
                amt = abs(cv)
        else:
            raw_a = cell(row, roles["amount"])
            if raw_a:
                amt = _parse_money(raw_a)
            if amt is None and roles["debit"] is not None:
                amt = _parse_money(cell(row, roles["debit"]))
            if amt is None and roles["credit"] is not None:
                v = _parse_money(cell(row, roles["credit"]))
                if v is not None:
                    amt = abs(v)

        if amt is None and not desc:
            continue
        if amt is None:
            amt = 0.0

        bal_raw = cell(row, roles["balance"])
        bal = _parse_money(bal_raw) if bal_raw else None

        out.append(
            {
                "date_iso": date_iso or "",
                "description": _clean_description(desc or ds or ""),
                "amount": float(amt),
                "balance": bal,
            }
        )
    return out


def _score_table_candidate(rows: list[list[str]]) -> tuple[int, int]:
    picked = _pick_header_row_index(rows)
    if not picked:
        return 0, 0
    hi, _ = picked
    sample = rows[hi + 1 : hi + 12]
    looks = 0
    for r in sample:
        j = _row_text_lower(r)
        if _DATELIKE.search(j) or re.search(
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}\b",
            j,
            re.I,
        ):
            if re.search(r"[\d$]", j):
                looks += 1
    cnt = _header_group_count(_row_text_lower(rows[hi]))
    return cnt, looks


_DATELIKE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"
)


def universal_layout_audit_credit_card_pdf(data: bytes) -> UniversalLayoutResult:
    """
    Run Universal Layout Audit on a credit card statement PDF.
    Returns normalized rows (date_iso, description, amount, balance) and metadata.
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError(
            "PDF support requires pdfplumber. Install with: pip install pdfplumber"
        ) from e

    result = UniversalLayoutResult()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        period_start, period_end = _extract_statement_period(pdf)
        candidates = _tables_from_pdf(pdf)
        if not candidates:
            candidates = [_rows_from_pdf_text(pdf)]

        best_rows: list[list[str]] | None = None
        best_key = (-1, -1)
        for tbl in candidates:
            if len(tbl) < 2:
                continue
            hj0 = _row_text_lower(tbl[0])
            if _looks_like_summary_only_header(hj0) and _header_group_count(hj0) < 3:
                continue
            key = _score_table_candidate(tbl)
            if key > best_key:
                best_key = key
                best_rows = tbl

        if not best_rows or best_key[0] < 3:
            text_fallback = _pad_table(_rows_from_pdf_text(pdf))
            if text_fallback and _score_table_candidate(text_fallback)[0] >= 3:
                best_rows = text_fallback
            elif best_rows is None:
                best_rows = text_fallback

        if not best_rows:
            result.warnings.append("No table or text lines found in PDF.")
            return result

        picked = _pick_header_row_index(best_rows)
        if not picked:
            result.warnings.append(
                "Could not find a header row with at least three of: Date, Description/Transaction, Amount, Balance."
            )
            return result

        header_idx, hj = picked
        header_cells = [(c or "").strip() for c in best_rows[header_idx] if (c or "").strip()]
        result.matched_headers = header_cells[:20]

        hd, hdesc, ha, hb = _header_groups_present(hj)
        result.header_groups = {
            "date": hd,
            "description": hdesc,
            "amount": ha,
            "balance": hb,
        }

        roles, mode = _classify_columns(best_rows[header_idx])
        sample_row = (
            best_rows[header_idx + 1]
            if header_idx + 1 < len(best_rows)
            else None
        )
        roles = _fix_roles_when_header_merged(roles, best_rows[header_idx], sample_row)
        result.amount_mode = mode

        if roles["date"] is None:
            result.warnings.append("Could not map a Date column; check the statement layout.")
        if roles["description"] is None:
            result.warnings.append("Could not map a Description column.")
        if roles["amount"] is None and (roles["debit"] is None or roles["credit"] is None):
            if roles["debit"] is None and roles["credit"] is None:
                result.warnings.append("Could not map Amount (or Debit/Credit) columns.")

        parsed = _parse_data_rows(
            best_rows, header_idx, roles, mode, period_start, period_end
        )

        if not parsed:
            text_fb = _pad_table(_rows_from_pdf_text(pdf))
            picked_fb = _pick_header_row_index(text_fb)
            if picked_fb and text_fb is not best_rows:
                hi2, hj2 = picked_fb[0], picked_fb[1]
                roles2, mode2 = _classify_columns(text_fb[hi2])
                sample2 = (
                    text_fb[hi2 + 1] if hi2 + 1 < len(text_fb) else None
                )
                roles2 = _fix_roles_when_header_merged(roles2, text_fb[hi2], sample2)
                parsed2 = _parse_data_rows(
                    text_fb, hi2, roles2, mode2, period_start, period_end
                )
                if parsed2:
                    best_rows = text_fb
                    header_idx = hi2
                    hj = hj2
                    header_cells = [
                        (c or "").strip() for c in best_rows[header_idx] if (c or "").strip()
                    ]
                    result.matched_headers = header_cells[:20]
                    hd, hdesc, ha, hb = _header_groups_present(hj)
                    result.header_groups = {
                        "date": hd,
                        "description": hdesc,
                        "amount": ha,
                        "balance": hb,
                    }
                    roles, mode = roles2, mode2
                    result.amount_mode = mode2
                    parsed = parsed2

        result.rows = parsed

        if not parsed:
            result.warnings.append("No data rows parsed below the header.")

    return result


def preview_rows_for_ui(result: UniversalLayoutResult, maximum: int = 50) -> list[dict[str, Any]]:
    """Return parsed rows capped for UI display."""
    return result.rows[:maximum]
