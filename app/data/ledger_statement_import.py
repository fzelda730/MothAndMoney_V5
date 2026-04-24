"""
Ledger CSV/PDF import: parse rows with account template column_map, normalize dates, filter by period.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from data.bank_statement_csv import parse_bank_statement_csv_all_rows
from data.credit_card_statement_csv import parse_credit_card_csv_all_rows


def extract_statement_grid_from_pdf(_template_type: str, file_bytes: bytes) -> list[list[str]]:
    """
    Turn a statement PDF into a row/column grid (pdfplumber).
    Bank statement PDFs use embedded tables even when headers are not CC-shaped; credit card
    PDFs keep the stricter table-vs-text logic from Credit Card Config.
    """
    t = (_template_type or "").strip().lower()
    if t == "bank_statement":
        from data.credit_card_statement_pdf import bank_statement_grid_from_pdf_bytes

        return bank_statement_grid_from_pdf_bytes(file_bytes)
    from data.credit_card_statement_pdf import credit_card_grid_from_pdf_bytes

    return credit_card_grid_from_pdf_bytes(file_bytes)


def parse_date_cell(date_raw: str, *, default_year: int | None = None) -> date | None:
    """
    Best-effort parse for common bank/CC export formats, including Capital One PDF-style
    month names and yearless transaction dates (year from statement range via default_year).
    Chase checking PDFs often merge date + description in one cell (e.g. "01/08 Monthly Service Fee").
    """
    s = (date_raw or "").strip()
    if not s:
        return None
    s = re.sub(r"\s+", " ", s)
    # Leading M/D or M/D/Y (or YY/YYYY) before more text — common on Chase text-extracted lines.
    m_lead = re.match(r"^(\d{1,2}/\d{1,2})(?:/(\d{2,4}))?(?=\s|$)", s)
    if m_lead:
        md, yrest = m_lead.group(1), m_lead.group(2)
        try:
            if yrest:
                if len(yrest) == 4:
                    return datetime.strptime(f"{md}/{yrest}", "%m/%d/%Y").date()
                return datetime.strptime(f"{md}/{yrest}", "%m/%d/%y").date()
            if default_year is not None:
                part = datetime.strptime(md, "%m/%d")
                return date(default_year, part.month, part.day)
        except ValueError:
            pass

    s_ord = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)
    tokens = s_ord.split()

    numeric_formats = (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%m-%d-%Y",
        "%d-%m-%Y",
    )
    cands: list[str] = [s_ord]
    if tokens and tokens[0][:1].isdigit() and len(tokens) > 1:
        cands.insert(0, tokens[0])
    for cand in cands:
        if not cand:
            continue
        for fmt in numeric_formats:
            try:
                return datetime.strptime(cand[:19], fmt).date()
            except ValueError:
                continue
        try:
            return date.fromisoformat(cand[:10])
        except ValueError:
            pass
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", cand)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

    month_year_formats = (
        "%b %d, %Y",
        "%b %d %Y",
        "%B %d, %Y",
        "%B %d %Y",
        "%d-%b-%Y",
        "%d %b %Y",
    )
    for fmt in month_year_formats:
        try:
            return datetime.strptime(s_ord, fmt).date()
        except ValueError:
            continue

    if default_year is not None:
        t = s_ord.rstrip(",").strip()
        for fmt in ("%b %d", "%B %d"):
            try:
                dt = datetime.strptime(t, fmt)
                return date(default_year, dt.month, dt.day)
            except ValueError:
                continue

    return None


def _adjust_yearless_to_import_range(
    d: date,
    raw: str,
    *,
    date_start: date | None,
    date_end: date | None,
) -> date:
    """
    If date_raw had no year, the inferred year may be off for statements that span calendar years
    (e.g. December activity on a January-dated closing statement). Nudge the year so the date
    is plausibly inside [date_start, date_end] when possible.
    """
    s = (raw or "").strip()
    if re.search(r"\b(19|20)\d{2}\b", s):
        return d
    out = d
    if date_end is not None and out > date_end:
        try:
            out = date(out.year - 1, out.month, out.day)
        except ValueError:
            pass
    if date_start is not None and out < date_start:
        try:
            out = date(out.year + 1, out.month, out.day)
        except ValueError:
            pass
    return out


def format_ledger_parse_failure_message(
    diag: dict[str, Any],
    date_start: date | None,
    date_end: date | None,
) -> str:
    """User-facing explanation when parse_ledger_csv_rows returns no rows."""
    raw = int(diag.get("raw_row_count") or 0)
    if raw == 0:
        return (
            "No data rows found after the header. Check the file and column mapping "
            "(Date, Amount, Payee)."
        )
    fmin = diag.get("file_date_min")
    fmax = diag.get("file_date_max")
    if (
        fmin is not None
        and fmax is not None
        and date_start is not None
        and date_end is not None
    ):
        if fmax < date_start or fmin > date_end:
            return (
                f"No transactions fall between {date_start} and {date_end}. "
                f"Dates in this file run from {fmin} to {fmax}. Adjust the start or end date."
            )
    samples = diag.get("sample_bad_dates") or []
    sample_note = ""
    if isinstance(samples, list) and samples:
        quoted = "; ".join(repr(x) for x in samples[:3])
        sample_note = f" Sample values from the mapped Date column: {quoted}."
    template_hint = (
        " In the import template, map **Date** to the column that actually contains transaction dates "
        "(credit card PDFs: often **Trans Date**), not description or other text."
    )
    if int(diag.get("skipped_unparsed_date") or 0) >= raw:
        return (
            "Could not parse dates in the Date column. Check that the Date field maps to the "
            "correct template column." + sample_note + template_hint
        )
    if int(diag.get("skipped_unparsed_date") or 0) > 0:
        return (
            f"Many rows have unparseable dates ({diag.get('skipped_unparsed_date')} of {raw}). "
            "Check the Date column mapping." + sample_note + template_hint
        )
    parts = []
    if int(diag.get("skipped_before_range") or 0) or int(diag.get("skipped_after_range") or 0):
        parts.append(
            f"outside selected date range ({diag.get('skipped_before_range', 0)} before, "
            f"{diag.get('skipped_after_range', 0)} after)"
        )
    if int(diag.get("skipped_empty_payee") or 0):
        parts.append(f"empty payee ({diag.get('skipped_empty_payee')})")
    if int(diag.get("skipped_zero_amount") or 0):
        parts.append(f"zero amount ({diag.get('skipped_zero_amount')})")
    if parts:
        return (
            "No transactions left after filtering: " + ", ".join(parts) + ". "
            "Check Payee and Amount column mapping and the date range."
        )
    return (
        "No transactions in range. Check the file, template mapping, and start/end dates."
    )


def parse_ledger_csv_rows(
    *,
    file_bytes: bytes,
    template_type: str,
    column_map: dict[str, Any],
    date_start: date | None,
    date_end: date | None,
    grid_rows: list[list[str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Parse CSV bytes (or a pre-extracted PDF grid) into row dicts ready for DB (after COA resolution elsewhere).
    template_type: bank_statement | credit_card
    Each row: date, payee, payee_normalized, debit_amount, credit_amount, description, source

    Second return value is diagnostics for error messages.
    """
    tt = (template_type or "").strip()
    cm = {k: (v if isinstance(v, str) else str(v)) for k, v in (column_map or {}).items()}

    if tt == "credit_card":
        raw_rows = parse_credit_card_csv_all_rows(
            file_bytes, cm, grid_rows=grid_rows
        )
        source = "credit_card_import"
    else:
        raw_rows = parse_bank_statement_csv_all_rows(
            file_bytes, cm, grid_rows=grid_rows
        )
        source = "bank_import"

    diag: dict[str, Any] = {
        "raw_row_count": len(raw_rows),
        "file_date_min": None,
        "file_date_max": None,
        "skipped_unparsed_date": 0,
        "skipped_before_range": 0,
        "skipped_after_range": 0,
        "skipped_empty_payee": 0,
        "skipped_zero_amount": 0,
        "sample_bad_dates": [],
    }

    default_year = (
        date_end.year
        if date_end is not None
        else (date_start.year if date_start is not None else None)
    )

    def _bad_date_sample(dr: str) -> None:
        samples: list[str] = diag["sample_bad_dates"]
        if len(samples) >= 3:
            return
        clip = (dr or "").strip()[:100]
        if clip and clip not in samples:
            samples.append(clip)

    file_dates: list[date] = []
    for r in raw_rows:
        dr = r.get("date_raw") or ""
        d = parse_date_cell(dr, default_year=default_year)
        if d is not None:
            d = _adjust_yearless_to_import_range(
                d, dr, date_start=date_start, date_end=date_end
            )
            file_dates.append(d)
    if file_dates:
        diag["file_date_min"] = min(file_dates)
        diag["file_date_max"] = max(file_dates)

    out: list[dict[str, Any]] = []
    for r in raw_rows:
        dr = r.get("date_raw") or ""
        d = parse_date_cell(dr, default_year=default_year)
        if d is not None:
            d = _adjust_yearless_to_import_range(
                d, dr, date_start=date_start, date_end=date_end
            )
        if d is None:
            diag["skipped_unparsed_date"] += 1
            _bad_date_sample(str(dr))
            continue
        if date_start is not None and d < date_start:
            diag["skipped_before_range"] += 1
            continue
        if date_end is not None and d > date_end:
            diag["skipped_after_range"] += 1
            continue
        payee = (r.get("payee") or "").strip()
        if not payee:
            diag["skipped_empty_payee"] += 1
            continue
        desc = (r.get("description") or "").strip()
        debit = float(r.get("debit_amount") or 0)
        credit = float(r.get("credit_amount") or 0)
        if debit <= 0 and credit <= 0:
            diag["skipped_zero_amount"] += 1
            continue
        pn = " ".join(payee.split()).strip().lower()
        out.append(
            {
                "date": d,
                "payee": payee[:500],
                "payee_normalized": pn[:500],
                "debit_amount": debit,
                "credit_amount": credit,
                "description": desc[:2000] if desc else None,
                "source": source,
            }
        )
    return out, diag
