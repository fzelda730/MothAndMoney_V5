"""
Extract a tabular grid from credit card statement PDFs for template mapping (pdfplumber).
"""

from __future__ import annotations

import io
import re
from typing import Any

from data.credit_card_statement_csv import row_looks_like_cc_statement_header

# Prefer transaction tables whose header row matches known CC column labels.
_CC_TABLE_HEADER_BONUS = 500

_MONEYISH = re.compile(
    r"^[$€£]?\s*[\(-]?\s*[\d,]+\.?\d*\s*\)?$|^[\(-]?\s*[\d,]+\.\d{2}\s*\)?$"
)
_DATELIKE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"
)

# Checking/savings PDF text lines (Chase): transaction rows are often single-spaced so
# split-on-multi-space yields one segment and the row was dropped. Parse M/D prefix + trailing amounts.
_BANK_LINE_DATE_PREFIX = re.compile(r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.+)$")
_BANK_MONEY_TOKEN = re.compile(
    r"(?<![\d.])(-?\$?\s*(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})(?!\d)"
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


def _table_has_transaction_header_row(rows: list[list[str]]) -> bool:
    """extract_tables() can return payoff/disclosure grids with short cells; require real CC header keywords."""
    if not rows:
        return False
    if row_looks_like_cc_statement_header(rows[0]):
        return True
    if len(rows) > 1 and row_looks_like_cc_statement_header(rows[1]):
        return True
    return False


def _score_table(rows: list[list[str]]) -> tuple[int, int]:
    """Heuristic: prefer large tables with date- or amount-like cells."""
    if not rows:
        return 0, 0
    nonempty = 0
    hints = 0
    for row in rows:
        cells = [(c or "").strip() for c in row if (c or "").strip()]
        if len(cells) < 2:
            continue
        nonempty += 1
        joined = " ".join(cells)
        if _DATELIKE.search(joined):
            hints += 2
        for c in cells:
            c2 = c.replace(",", "")
            if _MONEYISH.match(c2):
                hints += 2
                break
    base = nonempty * 2 + hints
    bonus = 0
    if rows and row_looks_like_cc_statement_header(rows[0]):
        bonus = _CC_TABLE_HEADER_BONUS
    elif len(rows) > 1 and row_looks_like_cc_statement_header(rows[1]):
        bonus = _CC_TABLE_HEADER_BONUS
    return base + bonus, len(rows)


def _tables_from_pdf_pages(pdf: Any) -> list[list[list[str]]]:
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
    """Fallback when vector tables are missing: split text lines on gaps."""
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


def _is_plausible_bank_amount_token(tok: str) -> bool:
    """Avoid treating YYYY.MM-style numbers in narrative text as currency."""
    s = re.sub(r"\s+", "", (tok or "").replace("$", "").replace(",", "").strip())
    m = re.fullmatch(r"-?(\d+)\.(\d{2})", s)
    if not m:
        return False
    whole_s, frac_s = m.group(1), m.group(2)
    whole, frac = int(whole_s), int(frac_s)
    if len(whole_s) == 4 and 1900 <= whole <= 2100 and frac <= 31:
        return False
    return True


def _expand_bank_text_line_to_row(line: str) -> list[str] | None:
    """
    One-line transaction row: ``MM/DD description ... amount [balance]`` with only single spaces
    (common for long Chase descriptions). Returns four cells when balance is present.
    """
    s = line.strip()
    if len(s) < 6:
        return None
    m = _BANK_LINE_DATE_PREFIX.match(s)
    if not m:
        return None
    date, rest = m.group(1), m.group(2).strip()
    tokens = list(_BANK_MONEY_TOKEN.finditer(rest))
    if not tokens:
        return None
    if any(not _is_plausible_bank_amount_token(t.group(1)) for t in tokens):
        return None
    if len(tokens) >= 2:
        amt_m, bal_m = tokens[-2], tokens[-1]
        desc = rest[: amt_m.start()].strip()
        amt = amt_m.group(1).strip()
        bal = bal_m.group(1).strip()
    else:
        t = tokens[-1]
        desc = rest[: t.start()].strip()
        amt = t.group(1).strip()
        bal = ""
    if not desc:
        return None
    return [date, desc, amt, bal]


def _rows_from_bank_pdf_text(pdf: Any) -> list[list[str]]:
    """
    Like ``_rows_from_pdf_text`` but recover Chase-style lines that do not have multi-space column gaps.
    """
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
            else:
                expanded = _expand_bank_text_line_to_row(parts[0] if parts else line)
                if expanded:
                    rows.append(expanded)
    return rows


def bank_statement_grid_from_pdf_bytes(data: bytes) -> list[list[str]]:
    """
    Extract a row grid from checking/savings-style PDFs (e.g. Chase).
    Unlike credit cards, we do not require a CC-style header row: many bank tables use
    "Date", "Description", "Amount" and would be discarded by the CC-only filter.
    Prefer the highest-scoring embedded table; fall back to text-line splitting only if
    pdfplumber finds no tables.
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError(
            "PDF support requires pdfplumber. Install with: pip install pdfplumber"
        ) from e

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        candidates = _tables_from_pdf_pages(pdf)
        if candidates:
            best = max(candidates, key=_score_table)
            return _pad_table(best)
        return _pad_table(_rows_from_bank_pdf_text(pdf))


def credit_card_grid_from_pdf_bytes(data: bytes) -> list[list[str]]:
    """
    Return the best-scoring table (rows of string cells) for column mapping / preview.
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError(
            "PDF support requires pdfplumber. Install with: pip install pdfplumber"
        ) from e

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        candidates = _tables_from_pdf_pages(pdf)
        txn_tables = [t for t in candidates if _table_has_transaction_header_row(t)]
        if txn_tables:
            best = max(txn_tables, key=_score_table)
        elif candidates:
            # Avoid Minimum Payment-style tables: use full text lines for header detection.
            best = _rows_from_pdf_text(pdf)
        else:
            best = _rows_from_pdf_text(pdf)

    return _pad_table(best)
