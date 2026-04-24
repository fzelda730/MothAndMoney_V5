"""
CSV helpers for credit card statement template: headers, suggestions, preview, payee mining.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

CC_COLUMN_NOT_USED = "— Not used —"

CC_FIELD_DATE = "date"
CC_FIELD_TRANSACTION_TYPE = "transaction_type"
CC_FIELD_PAYEE = "payee"
CC_FIELD_AMOUNT = "amount"
CC_FIELD_ACCOUNT = "account"
CC_FIELD_DESCRIPTION = "description"

CC_MAP_FIELD_KEYS: tuple[str, ...] = (
    CC_FIELD_DATE,
    CC_FIELD_TRANSACTION_TYPE,
    CC_FIELD_PAYEE,
    CC_FIELD_AMOUNT,
    CC_FIELD_ACCOUNT,
    CC_FIELD_DESCRIPTION,
)

# Phrase keywords (not bare "date") so summary lines are less likely to match.
_CC_STATEMENT_HEADER_KEYWORDS: tuple[str, ...] = (
    "trans date",
    "post date",
    "transaction date",
    "description",
    "amount",
    "merchant",
    "payee",
    "debits",
    "credits",
)

# Reject PDF disclaimer rows split into columns (long cells); real headers stay short.
_CC_HEADER_MIN_CELLS = 3
_CC_HEADER_CELL_MAX_LEN = 56
_CC_HEADER_AVG_MAX_LEN = 40

# Prefer a real transaction table header (Chase PDFs prepend many rows; naive "first plausible" picked CHASE branding).
_CC_TRANSACTION_HEADER_MIN_SCORE = 6
_CC_HEADER_SCAN_MAX = 120

# Parse merged PDF text like "Trans Date Post Date Description" + "Amount" (two cells).
_MERGED_HEADER_LABEL_ORDER = (
    "Trans Date",
    "Post Date",
    "Transaction Date",
    "Posting Date",
    "Description",
)

_MONEYISH_HEADER_CELL = re.compile(
    r"^[\+\-]?\s*[$€£]?\s*[\d,]+\.?\d*\s*$|^[\+\-]?\s*[$€£]\s*[\d,]+\.\d{2}\s*$"
)


def _cell_looks_like_money_amount(c: str) -> bool:
    t = (c or "").strip().replace(",", "").replace(" ", "")
    if not t or re.search(r"[A-Za-z]{3,}", (c or "").strip()):
        return False
    return bool(_MONEYISH_HEADER_CELL.match((c or "").strip().replace(",", "")))


def _nonempty_cells(row: list[str]) -> list[str]:
    return [(c or "").strip() for c in row if (c or "").strip()]


def expand_chase_cc_pdf_header_row(row: list[str]) -> list[str] | None:
    """
    Chase card PDF table extraction often yields::
        ['Transaction', 'Merchant Name or Transaction Description $ Amount', '', ...]
    Split the second cell into description + Amount for mapping and preview.
    """
    nonempty = [(c or "").strip() for c in row if (c or "").strip()]
    if len(nonempty) < 2:
        return None
    c0, c1 = nonempty[0], nonempty[1]
    if c0.lower() != "transaction":
        return None
    m = re.match(r"(?is)^(.+?)\s*\$\s*amount\s*$", c1.strip())
    if not m:
        return None
    desc = (m.group(1) or "").strip()
    if not desc:
        return None
    return [c0, desc, "Amount"]


def expand_merged_cc_header_row(row: list[str]) -> list[str] | None:
    """
    If extract_text merged several labels into one cell (e.g. Capital One), return 4 logical headers.
    """
    cells = _nonempty_cells(row)
    if len(cells) != 2:
        return None
    left, right = cells[0], cells[1]
    if right.strip().lower() != "amount":
        return None
    rem = left.strip()
    parts: list[str] = []
    while rem:
        low = rem.lower()
        hit: str | None = None
        for label in _MERGED_HEADER_LABEL_ORDER:
            lw = label.lower()
            if low.startswith(lw) and (len(rem) == len(label) or rem[len(label) : len(label) + 1].isspace()):
                hit = label
                break
        if hit is None:
            return None
        parts.append(rem[: len(hit)])
        rem = rem[len(hit) :].strip()
    if len(parts) < 2:
        return None
    parts.append(right.strip())
    return parts


def row_is_plausible_cc_column_header(row: list[str]) -> bool:
    """True if row could be CSV/PDF column titles (not multi-sentence cells)."""
    cells = _nonempty_cells(row)
    if len(cells) < 2:
        return False
    lengths = [len(c) for c in cells]
    if max(lengths) > _CC_HEADER_CELL_MAX_LEN:
        return False
    if sum(lengths) / len(lengths) > _CC_HEADER_AVG_MAX_LEN:
        return False
    money = sum(1 for c in cells if _cell_looks_like_money_amount(c))
    if len(cells) == 2:
        return money == 0
    if len(cells) >= _CC_HEADER_MIN_CELLS:
        return money <= 1
    return money == 0


def row_looks_like_cc_statement_header(row: list[str]) -> bool:
    """True if row resembles a credit card transaction table header (e.g. Capital One PDFs)."""
    if expand_chase_cc_pdf_header_row(row) is not None:
        return row_is_plausible_cc_column_header(row)
    if not row_is_plausible_cc_column_header(row):
        return False
    cells = _nonempty_cells(row)
    joined = " ".join(c.lower() for c in cells)
    hits = sum(1 for kw in _CC_STATEMENT_HEADER_KEYWORDS if kw in joined)
    if len(cells) == 2:
        return hits >= 3 and expand_merged_cc_header_row(row) is not None
    if len(cells) >= _CC_HEADER_MIN_CELLS:
        return hits >= 2
    return False


def _cc_transaction_header_score(hdr: list[str]) -> int:
    """Heuristic score for a row being the posted-transactions table header (PDF or CSV)."""
    nonempty_hdr = [(h or "").strip() for h in hdr if (h or "").strip()]
    if len(nonempty_hdr) < 2:
        return 0
    blob = " ".join(h.lower() for h in nonempty_hdr)
    score = 0
    if re.search(r"\b(trans\s*date|post(ing)?\s*date|transaction\s*date)\b", blob):
        score += 4
    elif (
        len(nonempty_hdr) >= 3
        and nonempty_hdr[0].lower() == "transaction"
        and nonempty_hdr[-1].lower() == "amount"
    ):
        score += 4
    elif re.search(r"\bdate\b", blob):
        score += 2
    if re.search(r"\b(description|merchant|memo|payee|narrative)\b", blob) or "merchant name" in blob:
        score += 3
    if re.search(r"\bamount\b", blob) or re.search(r"\$\s*amount\b", blob):
        score += 2
    if re.search(r"\b(debit|credit|dr/cr|type)\b", blob):
        score += 1
    return score


def _normalize_cc_header_row(row: list[str]) -> list[str]:
    """Apply issuer-specific merged-header expansion; otherwise strip cells."""
    ch = expand_chase_cc_pdf_header_row(row)
    if ch is not None:
        return ch
    cap = expand_merged_cc_header_row(row)
    if cap is not None:
        return cap
    return [(c or "").strip() for c in row]


def _parse_money(cell: str) -> float:
    if cell is None:
        return 0.0
    s = str(cell).replace("$", "").replace(",", "").replace("\t", "").strip()
    if not s:
        return 0.0
    # e.g. Capital One "- $1,518.22" -> "- 1518.22" after $ strip; collapse so float() accepts
    s = re.sub(r"\s+", "", s)
    try:
        return float(s)
    except ValueError:
        return 0.0


def iter_cc_csv_rows(data: bytes) -> list[list[str]]:
    text = io.StringIO(data.decode("utf-8-sig", errors="replace"))
    return list(csv.reader(text))


def detect_cc_header_row(rows: list[list[str]]) -> tuple[list[str], int]:
    if not rows:
        return [], 0
    scan = min(_CC_HEADER_SCAN_MAX, len(rows))
    best_i: int | None = None
    best_hdr: list[str] | None = None
    best_score = -1
    for i in range(scan):
        row = rows[i]
        if not row or not any((c or "").strip() for c in row):
            continue
        norm = _normalize_cc_header_row(row)
        sc = _cc_transaction_header_score(norm)
        if sc > best_score:
            best_score = sc
            best_i = i
            best_hdr = norm

    if best_i is not None and best_hdr is not None and best_score >= _CC_TRANSACTION_HEADER_MIN_SCORE:
        return best_hdr, best_i

    scan_legacy = min(80, len(rows))
    for i in range(scan_legacy):
        row = rows[i]
        if not row:
            continue
        hdr = [(c or "").strip() for c in row]
        if not any(hdr):
            continue
        if row_looks_like_cc_statement_header(row):
            expanded = expand_chase_cc_pdf_header_row(row)
            if expanded is not None:
                return expanded, i
            expanded = expand_merged_cc_header_row(row)
            if expanded is not None:
                return expanded, i
            return [(c or "").strip() for c in row], i
    for i, row in enumerate(rows[:40]):
        if not row:
            continue
        hdr = [(c or "").strip() for c in row]
        if not any(hdr) or not row_is_plausible_cc_column_header(row):
            continue
        money = sum(1 for c in hdr if c and _cell_looks_like_money_amount(c))
        if money > 1:
            continue
        joined = " ".join((h or "").lower() for h in hdr if h)
        hits = sum(1 for kw in _CC_STATEMENT_HEADER_KEYWORDS if kw in joined)
        if hits >= 2 or _cc_transaction_header_score(hdr) >= 4:
            return hdr, i
    return [], 0


def credit_card_csv_headers_from_bytes(data: bytes) -> tuple[list[str], int]:
    return detect_cc_header_row(iter_cc_csv_rows(data))


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


def _cell_looks_like_cc_statement_date(cell: str) -> bool:
    """US-style statement posting dates (Chase, many issuers). Skips APR / summary rows after the txn table."""
    s = (cell or "").strip()
    return bool(re.match(r"^\d{1,2}/\d{1,2}(?:/\d{2,4})?$", s))


def suggest_credit_card_column_mapping(headers: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}

    def norm(h: str) -> str:
        return (h or "").strip()

    def low(h: str) -> str:
        return norm(h).lower()

    for h in headers:
        l = low(h)
        if CC_FIELD_DATE not in out and (
            l == "date"
            or "transaction date" in l
            or (l.endswith(" date") and "post" not in l)
            or l == "post date"
            or "value date" in l
        ):
            out[CC_FIELD_DATE] = norm(h)

    # Chase PDF: first column title is "Transaction" (transaction date); last column is "Amount".
    if CC_FIELD_DATE not in out and len(headers) >= 3:
        if (headers[0] or "").strip().lower() == "transaction" and (headers[-1] or "").strip().lower() == "amount":
            out[CC_FIELD_DATE] = norm(headers[0])

    for h in headers:
        l = low(h)
        if CC_FIELD_TRANSACTION_TYPE not in out and (
            l in ("type", "dr/cr", "debit/credit")
            or "transaction type" in l
            or l.startswith("debit")
            or l.startswith("credit")
        ):
            out[CC_FIELD_TRANSACTION_TYPE] = norm(h)

    for h in headers:
        l = low(h)
        if CC_FIELD_PAYEE not in out and (
            l in ("description", "payee", "merchant", "narrative", "name", "vendor")
            or "memo" in l
            or "merchant" in l
            or ("description" in l and "transaction" in l)
        ):
            out[CC_FIELD_PAYEE] = norm(h)

    for h in headers:
        l = low(h)
        if CC_FIELD_AMOUNT not in out and (
            l == "amount"
            or "amount" in l
            or l in ("value", "net amount", "transaction amount")
        ):
            out[CC_FIELD_AMOUNT] = norm(h)

    for h in headers:
        l = low(h)
        if CC_FIELD_ACCOUNT not in out and (
            ("account" in l and "number" in l)
            or l in ("category", "gl code", "account code", "class", "account")
            or "chart" in l
        ):
            out[CC_FIELD_ACCOUNT] = norm(h)

    for h in headers:
        l = low(h)
        if CC_FIELD_DESCRIPTION not in out and l in (
            "note",
            "reference",
            "details",
            "detail",
            "memo",
        ):
            out[CC_FIELD_DESCRIPTION] = norm(h)

    return out


def build_cc_preview_rows(
    headers: list[str],
    header_idx: int,
    mapping: dict[str, str],
    *,
    data: bytes | None = None,
    grid_rows: list[list[str]] | None = None,
    not_used: str = CC_COLUMN_NOT_USED,
    max_rows: int = 3,
) -> list[dict[str, Any]]:
    """
    First max_rows data rows. Each dict: date, payee, sub (secondary line), account, amount.
    Pass either ``data`` (CSV bytes) or ``grid_rows`` (e.g. from PDF table extraction).
    """
    i_date = _col_index(headers, mapping.get(CC_FIELD_DATE), not_used)
    i_payee = _col_index(headers, mapping.get(CC_FIELD_PAYEE), not_used)
    i_amt = _col_index(headers, mapping.get(CC_FIELD_AMOUNT), not_used)
    i_acct = _col_index(headers, mapping.get(CC_FIELD_ACCOUNT), not_used)
    i_desc = _col_index(headers, mapping.get(CC_FIELD_DESCRIPTION), not_used)

    if grid_rows is not None:
        rows = grid_rows
    elif data is not None:
        rows = iter_cc_csv_rows(data)
    else:
        rows = []
    out: list[dict[str, Any]] = []
    for row in rows[header_idx + 1 :]:
        if len(out) >= max_rows:
            break
        if not row or not any((c or "").strip() for c in row):
            continue
        if i_date is not None and not _cell_looks_like_cc_statement_date(_cell(row, i_date)):
            continue
        payee = _cell(row, i_payee)
        desc = _cell(row, i_desc) if i_desc is not None else ""
        if not payee and desc:
            payee = desc
            desc = ""
        sub = ""
        if desc and payee and desc.lower() != payee.lower():
            sub = desc
        elif not payee and desc:
            payee = desc
        amt = _parse_money(_cell(row, i_amt))
        acct = _cell(row, i_acct)
        date_s = _cell(row, i_date)
        out.append(
            {
                "date": date_s or "—",
                "payee": payee or "—",
                "sub": sub,
                "account": acct or "—",
                "amount": amt,
            }
        )
    return out


def parse_credit_card_csv_all_rows(
    data: bytes,
    column_map: dict[str, str],
    *,
    grid_rows: list[list[str]] | None = None,
    not_used: str = CC_COLUMN_NOT_USED,
    max_rows: int = 100_000,
) -> list[dict[str, Any]]:
    """
    Parse every data row from a credit card CSV.
    When the type column is blank: positive amount = charge (debit), negative = payment (credit).
    When type is present, use the same keyword rules as bank CSV via _display_type_from_row.
    Each dict: date_raw, payee, description, debit_amount, credit_amount.
    Pass ``grid_rows`` when the source is a PDF (tabular extraction) instead of CSV bytes.
    """
    from data.bank_statement_csv import _display_type_from_row

    rows_grid = grid_rows if grid_rows is not None else iter_cc_csv_rows(data)
    headers, header_idx = detect_cc_header_row(rows_grid)
    if not headers:
        return []

    i_date = _col_index(headers, column_map.get(CC_FIELD_DATE), not_used)
    i_tt = _col_index(headers, column_map.get(CC_FIELD_TRANSACTION_TYPE), not_used)
    i_payee = _col_index(headers, column_map.get(CC_FIELD_PAYEE), not_used)
    i_amt = _col_index(headers, column_map.get(CC_FIELD_AMOUNT), not_used)
    i_desc = _col_index(headers, column_map.get(CC_FIELD_DESCRIPTION), not_used)

    out: list[dict[str, Any]] = []
    for row in rows_grid[header_idx + 1 :]:
        if len(out) >= max_rows:
            break
        if not row or not any((c or "").strip() for c in row):
            continue
        if i_date is not None and not _cell_looks_like_cc_statement_date(_cell(row, i_date)):
            continue
        payee = _cell(row, i_payee)
        desc = _cell(row, i_desc) if i_desc is not None else ""
        if not payee and desc:
            payee = desc
            desc = ""
        sub = ""
        if desc and payee and desc.lower() != payee.lower():
            sub = desc
        elif not payee and desc:
            payee = desc
        amt = _parse_money(_cell(row, i_amt))
        if abs(amt) < 1e-12:
            continue
        type_raw = _cell(row, i_tt)
        if (type_raw or "").strip():
            disp = _display_type_from_row(amt, type_raw)
        else:
            disp = "DEBIT" if amt > 0 else "CREDIT"
        date_s = _cell(row, i_date)
        if disp == "DEBIT":
            debit, credit = abs(amt), 0.0
        else:
            debit, credit = 0.0, abs(amt)
        out.append(
            {
                "date_raw": date_s,
                "payee": payee or "",
                "description": sub or "",
                "debit_amount": debit,
                "credit_amount": credit,
            }
        )
    return out


def normalize_payee_for_rule(s: str) -> str:
    return " ".join((s or "").split()).strip().lower()


def unique_payee_candidates_from_bytes(
    headers: list[str],
    header_idx: int,
    mapping: dict[str, str],
    *,
    data: bytes | None = None,
    grid_rows: list[list[str]] | None = None,
    not_used: str = CC_COLUMN_NOT_USED,
    max_data_rows: int = 200,
    max_unique: int = 100,
) -> list[tuple[str, str]]:
    i_payee = _col_index(headers, mapping.get(CC_FIELD_PAYEE), not_used)
    i_desc = _col_index(headers, mapping.get(CC_FIELD_DESCRIPTION), not_used)
    i_date_m = _col_index(headers, mapping.get(CC_FIELD_DATE), not_used)
    if i_payee is None and i_desc is None:
        return []

    if grid_rows is not None:
        rows = grid_rows
    elif data is not None:
        rows = iter_cc_csv_rows(data)
    else:
        rows = []
    seen: dict[str, str] = {}
    n_scanned = 0
    for row in rows[header_idx + 1 :]:
        if n_scanned >= max_data_rows:
            break
        if not row or not any((c or "").strip() for c in row):
            continue
        if i_date_m is not None and not _cell_looks_like_cc_statement_date(_cell(row, i_date_m)):
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
