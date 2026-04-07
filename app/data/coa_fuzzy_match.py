"""
Fuzzy match trial balance line labels (e.g. CSV \"Full name\") to chart of accounts.
Uses stdlib only (difflib + regex).
"""

from __future__ import annotations

import csv
import io
import re
from difflib import SequenceMatcher
from typing import Any


def _normalize(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _leading_account_code(full_name: str) -> str | None:
    """Match leading digits like '4199 - Relay' or '1100 Cash'."""
    m = re.match(r"^\s*(\d{3,6})\s*[-–:\s]", full_name.strip())
    if m:
        return m.group(1)
    m2 = re.match(r"^\s*(\d{3,6})\s*$", full_name.strip())
    if m2:
        return m2.group(1)
    return None


def best_coa_match_for_line(full_name: str, coa_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Return best-guess COA number, display label, account type, and match score.

    coa_rows: items with keys number, name, type (and optional subtype).
    """
    raw = (full_name or "").strip()
    if not raw:
        return {
            "coa_number": "",
            "coa_label": "",
            "account_type": "",
            "match_score": 0.0,
            "confidence": "low",
        }

    n_full = _normalize(raw)
    best_score = 0.0
    best_num = ""
    best_label = ""
    best_type = ""

    lead = _leading_account_code(raw)

    for row in coa_rows:
        num = str(row.get("number", "")).strip()
        name = str(row.get("name", "")).strip()
        atype = str(row.get("type", "")).strip()

        candidates = [
            _normalize(f"{num} {name}"),
            _normalize(name),
            _normalize(f"{num} - {name}"),
            _normalize(f"{num}: {name}"),
        ]

        score = max((_ratio(n_full, c) for c in candidates if c), default=0.0)

        if lead and num and lead == num:
            score = max(score, 0.92)

        if score > best_score:
            best_score = score
            best_num = num
            best_label = f"{num} — {name}" if num else name
            best_type = atype

    if best_score <= 0:
        return {
            "coa_number": "",
            "coa_label": "",
            "account_type": "",
            "match_score": 0.0,
            "confidence": "low",
        }

    if best_score >= 0.72:
        conf = "high"
    elif best_score >= 0.5:
        conf = "medium"
    else:
        conf = "low"

    return {
        "coa_number": best_num,
        "coa_label": best_label,
        "account_type": best_type,
        "match_score": round(min(1.0, best_score), 3),
        "confidence": conf,
    }


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


TB_COLUMN_NOT_USED = "— Not used —"

TB_FIELD_COA_NUMBER = "coa_number"
TB_FIELD_COA_NAME = "coa_name"
TB_FIELD_ACCOUNT_TYPE = "account_type"
TB_FIELD_DEBITS = "debits"
TB_FIELD_CREDITS = "credits"

TB_MAP_FIELD_KEYS: tuple[str, ...] = (
    TB_FIELD_COA_NUMBER,
    TB_FIELD_COA_NAME,
    TB_FIELD_ACCOUNT_TYPE,
    TB_FIELD_DEBITS,
    TB_FIELD_CREDITS,
)


def iter_trial_balance_csv_rows(data: bytes) -> list[list[str]]:
    text = io.StringIO(data.decode("utf-8-sig", errors="replace"))
    return list(csv.reader(text))


def detect_trial_balance_csv_header(
    all_rows: list[list[str]],
) -> tuple[int, list[str]]:
    """
    Pick the most likely header row (prefers rows containing debit/credit/account).
    Returns (row_index, stripped header cell strings).
    """
    if not all_rows:
        return 0, []

    def score_row(row: list[str]) -> float:
        if not row:
            return 0.0
        parts = [((c or "").strip().lower()) for c in row]
        joined = " ".join(parts)
        sc = 0.0
        if "debit" in joined:
            sc += 3.0
        if "credit" in joined:
            sc += 3.0
        if "account" in joined:
            sc += 1.5
        if "name" in joined or "description" in joined:
            sc += 1.0
        if any("full" in p and "name" in p for p in parts):
            sc += 2.0
        non_empty = sum(1 for p in parts if p)
        sc += min(non_empty, 10) * 0.15
        return sc

    best_i, best_s = 0, -1.0
    for i, row in enumerate(all_rows[:60]):
        s = score_row(row)
        if s > best_s:
            best_s, best_i = s, i

    if best_s < 0.5:
        for i, row in enumerate(all_rows[:25]):
            if row and any((c or "").strip() for c in row):
                best_i = i
                break

    hdr = [(c or "").strip() for c in all_rows[best_i]]
    return best_i, hdr


def trial_balance_csv_headers_from_bytes(data: bytes) -> tuple[list[str], int]:
    """Return (header_cells, header_row_index)."""
    rows = iter_trial_balance_csv_rows(data)
    if not rows:
        return [], 0
    idx, hdr = detect_trial_balance_csv_header(rows)
    return hdr, idx


def suggest_trial_balance_column_mapping(headers: list[str]) -> dict[str, str]:
    """Map logical field keys to a header name from the file (best effort)."""
    out: dict[str, str] = {}

    def low(s: str) -> str:
        return (s or "").strip().lower()

    def pick(
        predicate,
    ) -> str | None:
        for h in headers:
            if predicate(low(h)):
                return h
        return None

    for h in headers:
        l = low(h)
        if "debit" in l and "credit" not in l:
            out[TB_FIELD_DEBITS] = h
            break
    if TB_FIELD_DEBITS not in out:
        d = pick(lambda x: x == "dr" or x.endswith(" debit") or x.startswith("debit"))
        if d:
            out[TB_FIELD_DEBITS] = d

    for h in headers:
        l = low(h)
        if "credit" in l and "debit" not in l:
            out[TB_FIELD_CREDITS] = h
            break
    if TB_FIELD_CREDITS not in out:
        c = pick(lambda x: x == "cr" or x.endswith(" credit") or x.startswith("credit"))
        if c:
            out[TB_FIELD_CREDITS] = c

    for h in headers:
        l = low(h)
        if ("number" in l or l.endswith(" #") or "#" in l) and "account" in l:
            out[TB_FIELD_COA_NUMBER] = h
            break
    if TB_FIELD_COA_NUMBER not in out:
        for h in headers:
            l = low(h)
            if l in ("no", "no.", "number", "acct", "account no", "account no.",
                     "account number", "gl", "gl code", "account code", "code"):
                out[TB_FIELD_COA_NUMBER] = h
                break
    if TB_FIELD_COA_NUMBER not in out:
        d = pick(
            lambda x: (
                "account" in x
                and "name" not in x
                and "type" not in x
                and "debit" not in x
                and "credit" not in x
            )
        )
        if d:
            out[TB_FIELD_COA_NUMBER] = d

    for h in headers:
        l = low(h)
        if "name" in l and "account" in l:
            out[TB_FIELD_COA_NAME] = h
            break
    if TB_FIELD_COA_NAME not in out:
        for h in headers:
            l = low(h)
            if l in ("name", "description", "account name", "memo", "detail"):
                out[TB_FIELD_COA_NAME] = h
                break
    if TB_FIELD_COA_NAME not in out:
        d = pick(
            lambda x: (
                ("description" in x or "name" in x)
                and "account" not in x
                and "debit" not in x
                and "credit" not in x
            )
        )
        if d:
            out[TB_FIELD_COA_NAME] = d

    for h in headers:
        l = low(h)
        if l in ("type", "account type", "category", "classification", "class"):
            out[TB_FIELD_ACCOUNT_TYPE] = h
            break
    if TB_FIELD_ACCOUNT_TYPE not in out:
        d = pick(
            lambda x: x == "type"
            or (x.endswith(" type") and "account" in x)
        )
        if d:
            out[TB_FIELD_ACCOUNT_TYPE] = d

    return out


def _tb_col_index(
    headers: list[str],
    choice: str | None,
    not_used: str,
) -> int | None:
    if choice is None or (choice or "").strip() == not_used.strip():
        return None
    c = (choice or "").strip()
    for i, h in enumerate(headers):
        if (h or "").strip() == c:
            return i
    return None


def _tb_cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx < 0:
        return ""
    if idx >= len(row):
        return ""
    return row[idx] if row[idx] is not None else ""


def parse_trial_balance_csv_with_mapping(
    data: bytes,
    mapping: dict[str, str],
    not_used: str = TB_COLUMN_NOT_USED,
) -> tuple[list[dict[str, Any]], int | None, str | None, bool]:
    """
    Parse trial balance rows using column mapping (actual CSV header names).
    Each row dict: full_name, debit, credit, optional account_type_csv.

    Returns (rows, header_row_index, error_message, used_legacy_parser).
    used_legacy_parser is True only when rows come from the classic Full name +
    Debit + Credit layout (parse_trial_balance_csv_bytes); column mapping does not
    apply to those rows.
    """
    all_rows = iter_trial_balance_csv_rows(data)
    if not all_rows:
        return [], None, "CSV is empty.", False

    header_idx, headers = detect_trial_balance_csv_header(all_rows)
    if not headers or not any(headers):
        legacy_rows, legacy_hdr = parse_trial_balance_csv_bytes(data)
        if legacy_rows:
            return legacy_rows, legacy_hdr, None, True
        return (
            [],
            legacy_hdr,
            "Could not detect a usable header row. For column mapping, use a row with "
            "your account and amount column names. Classic files can use Full name, Debit, Credit.",
            False,
        )

    i_deb = _tb_col_index(headers, mapping.get(TB_FIELD_DEBITS), not_used)
    i_crd = _tb_col_index(headers, mapping.get(TB_FIELD_CREDITS), not_used)
    i_num = _tb_col_index(headers, mapping.get(TB_FIELD_COA_NUMBER), not_used)
    i_name = _tb_col_index(headers, mapping.get(TB_FIELD_COA_NAME), not_used)
    i_type = _tb_col_index(headers, mapping.get(TB_FIELD_ACCOUNT_TYPE), not_used)

    if i_deb is None or i_crd is None:
        return (
            [],
            header_idx,
            "Map Debits and Credits to columns from your file.",
            False,
        )

    if i_num is None and i_name is None:
        return (
            [],
            header_idx,
            "Map at least one of Chart of Account (number) or Chart of Account (name).",
            False,
        )

    out: list[dict[str, Any]] = []
    for row in all_rows[header_idx + 1 :]:
        if not row:
            continue
        num = (_tb_cell(row, i_num)).strip()
        name = (_tb_cell(row, i_name)).strip()
        if num and name:
            full_name = f"{num} — {name}"
        elif num:
            full_name = num
        else:
            full_name = name
        if not full_name:
            continue
        if full_name.upper() == "TOTAL" or full_name.startswith("TOTAL"):
            continue
        deb = _parse_money(_tb_cell(row, i_deb))
        crd = _parse_money(_tb_cell(row, i_crd))
        rec: dict[str, Any] = {
            "full_name": full_name,
            "debit": deb,
            "credit": crd,
        }
        if num:
            rec["csv_account_number"] = num
        if i_type is not None:
            tcsv = (_tb_cell(row, i_type)).strip()
            if tcsv:
                rec["account_type_csv"] = tcsv
        out.append(rec)

    if not out:
        return (
            [],
            header_idx,
            "No data rows for this mapping. Check Debit/Credit columns for amounts and "
            "COA columns so each line has an account number or name.",
            False,
        )

    return out, header_idx, None, False


def parse_trial_balance_csv_bytes(data: bytes) -> tuple[list[dict[str, Any]], int | None]:
    """
    Parse a CSV with columns like Full name, Debit, Credit (header row detected).
    Skips preamble rows and TOTAL row.

    Returns (rows, header_row_index or None if not found).
    Each row: full_name, debit, credit (floats).
    """
    text = io.StringIO(data.decode("utf-8-sig", errors="replace"))
    reader = csv.reader(text)
    all_rows = list(reader)

    header_idx: int | None = None
    for i, row in enumerate(all_rows):
        if not row:
            continue
        c0 = (row[0] or "").strip().lower()
        c1 = (row[1] or "").strip().lower() if len(row) > 1 else ""
        if "full" in c0 and "name" in c0 and "debit" in c1:
            header_idx = i
            break

    if header_idx is None:
        return [], None

    out: list[dict[str, Any]] = []
    for row in all_rows[header_idx + 1 :]:
        if not row or not (row[0] or "").strip():
            continue
        name = (row[0] or "").strip()
        if name.upper() == "TOTAL" or name.startswith("TOTAL"):
            continue
        debit_s = row[1] if len(row) > 1 else ""
        credit_s = row[2] if len(row) > 2 else ""
        deb = _parse_money(debit_s)
        crd = _parse_money(credit_s)
        out.append({"full_name": name, "debit": deb, "credit": crd})
    return out, header_idx


def build_tb_preview_from_csv(
    parsed_rows: list[dict[str, Any]],
    coa_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """
    Build preview rows for UI: fuzzy COA + totals.
    """
    preview: list[dict[str, Any]] = []
    total_deb = 0.0
    total_crd = 0.0

    for pr in parsed_rows:
        fn = pr["full_name"]
        deb = float(pr["debit"])
        crd = float(pr["credit"])
        total_deb += deb
        total_crd += crd

        m = best_coa_match_for_line(fn, coa_rows)
        low = m["confidence"] == "low" or m["match_score"] < 0.45
        chart_type = (m["account_type"] or "").strip()
        csv_acct_type = str(pr.get("account_type_csv") or "").strip()
        disp_type = chart_type or csv_acct_type or "—"
        csv_num = str(pr.get("csv_account_number") or "").strip()
        if not csv_num:
            lead = _leading_account_code(fn)
            csv_num = (lead or "").strip()
        num_for_pick = csv_num if csv_num else (m["coa_number"] or "").strip()
        preview.append(
            {
                "bank_account": fn,
                "coa": m["coa_label"] or "—",
                "coa_number": num_for_pick,
                "csv_account_number": csv_num,
                "account_type_csv": csv_acct_type,
                "account_type": disp_type,
                "match_score": m["match_score"],
                "match_confidence": m["confidence"],
                "debits": deb,
                "credits": crd,
                "error": low,
            }
        )

    variance = abs(total_deb - total_crd)
    totals = {
        "total_debits": total_deb,
        "total_credits": total_crd,
        "is_balanced": variance < 0.02,
        "variance": variance,
    }
    return preview, totals
