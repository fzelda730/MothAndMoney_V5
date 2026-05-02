"""
MOTH AND MONEY — CAPITAL ONE CARD PDF (LOGIC)
/logic/pdf_parsers/capital_one_card_pdf.py

Formal:  Extract dated transaction lines from Capital One Quicksilver-style PDF statements.
Human:   Statement Upload uses this when you pick the Capital One built-in PDF driver.

Accounting Rule:
    Structural parse only; posting applies liability sign rules. PDF shows purchases as
    positive dollars and payments as negative (e.g. - $1,518.22).
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import pdfplumber

_BILLING_CYCLE_RANGE_PATTERN = re.compile(
    r"([A-Za-z]+ \d{1,2}, \d{4})\s*-\s*([A-Za-z]+ \d{1,2}, \d{4})",
    flags=re.IGNORECASE,
)

_TRANSACTION_LINE_PATTERN = re.compile(
    r"^([A-Za-z]{3} \d{1,2})\s+"
    r"([A-Za-z]{3} \d{1,2})\s+"
    r"(.+?)\s+"
    r"((?:-\s*)?\$[\d,]+\.\d{2})\s*$"
)


def _parse_billing_cycle_bounds(pdf_full_text: str) -> tuple[date, date]:
    """
    Formal:  Reads the statement header “Dec 26, 2025 - Jan 25, 2026” into real dates.
    Human:   Transaction lines only show “Dec 24”; we need the cycle to pick the year.
    """
    match = _BILLING_CYCLE_RANGE_PATTERN.search(pdf_full_text)
    if not match:
        raise ValueError(
            "Could not find a Capital One billing cycle range (Month DD, YYYY - Month DD, YYYY). "
            "This file may not be a Capital One card statement."
        )
    start_raw = match.group(1).strip()
    end_raw = match.group(2).strip()
    try:
        cycle_start = datetime.strptime(start_raw, "%b %d, %Y").date()
        cycle_end = datetime.strptime(end_raw, "%b %d, %Y").date()
    except ValueError as exc:
        raise ValueError(
            "Capital One billing cycle dates in this PDF use a format we do not recognize yet."
        ) from exc
    return cycle_start, cycle_end


def _posting_date_from_abbrev_month_day(
    month_day_token: str,
    *,
    cycle_start: date,
    cycle_end: date,
) -> str:
    """
    Formal:  Resolves “Jan 15” to an ISO calendar date inside (or beside) the billing window.
    Human:   Stops silent year mistakes when the cycle crosses New Year’s.
    """
    month_day_token = str(month_day_token).strip()
    slack_start = cycle_start - timedelta(days=7)
    slack_end = cycle_end + timedelta(days=7)
    for year in range(cycle_start.year - 1, cycle_end.year + 2):
        try:
            candidate = datetime.strptime(f"{month_day_token} {year}", "%b %d %Y").date()
        except ValueError:
            continue
        if slack_start <= candidate <= slack_end:
            return candidate.isoformat()
    raise ValueError(
        f"Could not assign a year to post date {month_day_token!r} within this statement cycle."
    )


def _parse_amount_cell(amount_text: str) -> Decimal:
    """
    Formal:  Normalizes “$29.60” or “- $1,518.22” to a signed Decimal.
    Human:   Matches how Capital One prints payments versus purchases on the card PDF.
    """
    stripped = str(amount_text).strip()
    negative = False
    if stripped.lstrip().startswith("-"):
        negative = True
        stripped = stripped.lstrip()[1:].strip()
    cleaned = stripped.replace("$", "").replace(",", "").strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Could not read amount {amount_text!r}.") from exc
    return -value if negative else value


def extract_capital_one_card_statement_lines_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Formal:  Reads a Capital One card PDF and returns rows with posting_date_iso, payee,
            amount (Decimal from the PDF), reference (transaction date for traceability).
    Human:   Pick “Capital One card PDF (built-in)” on Statement Upload.

    Accounting Rule:
        Posting date is the statement **Post Date**; reference holds **Trans Date** as printed.
    """
    if len(pdf_bytes) < 8 or not pdf_bytes[:5].startswith(b"%PDF"):
        raise ValueError(
            "This file does not look like a PDF. Upload the Capital One statement export as .pdf."
        )

    buffer = io.BytesIO(pdf_bytes)
    full_text_chunks: list[str] = []

    with pdfplumber.open(buffer) as pdf_document:
        for page in pdf_document.pages:
            page_text = page.extract_text()
            if page_text:
                full_text_chunks.append(page_text)

    if len(full_text_chunks) == 0:
        raise ValueError(
            "No readable text could be pulled from this PDF. Image-only statements need a "
            "different path — try downloading the PDF again or use CSV if Capital One offers it."
        )

    full_text = "\n".join(full_text_chunks)
    cycle_start, cycle_end = _parse_billing_cycle_bounds(full_text)

    noise_substrings = (
        "trans date post date description amount",
        "total transactions",
        "total fees",
        "total interest",
    )

    lines_out: list[dict] = []

    for raw_line in full_text.splitlines():
        line = str(raw_line).strip()
        if len(line) < 12:
            continue
        lower = line.lower()
        if lower in noise_substrings:
            continue
        if lower.startswith("visit capitalone"):
            continue
        match = _TRANSACTION_LINE_PATTERN.match(line)
        if not match:
            continue
        trans_token = match.group(1).strip()
        post_token = match.group(2).strip()
        payee = str(match.group(3)).strip()
        amount_cell = match.group(4)
        if payee == "":
            continue
        try:
            posting_date_iso = _posting_date_from_abbrev_month_day(
                post_token,
                cycle_start=cycle_start,
                cycle_end=cycle_end,
            )
            amount_value = _parse_amount_cell(amount_cell)
        except ValueError:
            continue
        lines_out.append(
            {
                "posting_date_iso": posting_date_iso,
                "payee": payee[:500],
                "amount": amount_value,
                "reference": trans_token[:120],
            }
        )

    if len(lines_out) == 0:
        raise ValueError(
            "No transaction rows matched this Capital One PDF layout. The bank may have changed "
            "the export — save a redacted sample so the parser can be updated."
        )

    return lines_out
