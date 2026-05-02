"""
MOTH AND MONEY — CHASE CREDIT CARD PDF (LOGIC)
/logic/pdf_parsers/chase_credit_card_pdf.py

Formal:  Extract transaction lines from Chase credit card PDFs (Ultimate Rewards / card layout).
Human:   Statement Upload — pick “Chase credit card PDF (built-in)”. Checking uses Chase checking PDF.

Accounting Rule:
    Structural parse only; liability posting uses is_liability on the template row. Amounts follow
    the statement (purchases positive, payments negative).
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import pdfplumber

_OPENING_CLOSING_PATTERN = re.compile(
    r"Opening/Closing Date\s+(\d{1,2}/\d{1,2}/\d{2})\s*-\s*(\d{1,2}/\d{1,2}/\d{2})",
    flags=re.IGNORECASE,
)


def _parse_money_token(token: str) -> Decimal:
    """
    Formal:  Chase card activity amount cell with optional $ and commas; parentheses optional.
    Human:   Matches -14.99 and 187.20 style cells.

    Accounting Rule:
        Signed amounts only; no float.
    """
    cleaned = str(token).strip().replace("$", "").replace(",", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        inner = cleaned[1:-1].strip()
        return -Decimal(inner)
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Could not read amount {token!r}.") from exc


def _money_tail_token_looks_like(token: str) -> bool:
    """
    Formal:  True when a whitespace token matches a signed money cell (e.g. -14.99).
    Human:   Lets us treat the last token as amount on ACCOUNT ACTIVITY lines.

    Accounting Rule:
        Structural check only — posting still uses Decimal from _parse_money_token.
    """
    cleaned = str(token).strip().replace("$", "").replace(",", "")
    return bool(re.fullmatch(r"-?\d+\.\d{2}", cleaned))


def _cycle_bounds_from_opening_closing(pdf_full_text: str) -> tuple[datetime.date, datetime.date]:
    """
    Formal:  Parses “Opening/Closing Date 12/02/25 - 01/01/26” into cycle start and end dates.
    Human:   Transaction lines show MM/DD only; this pins the year.

    Accounting Rule:
        N/A — date scaffolding for posting_date_iso.
    """
    match = _OPENING_CLOSING_PATTERN.search(pdf_full_text)
    if not match:
        raise ValueError(
            "Could not find Chase card Opening/Closing Date range. This PDF may be a non-card layout "
            "— pick Chase checking PDF or another driver."
        )
    try:
        cycle_start = datetime.strptime(match.group(1).strip(), "%m/%d/%y").date()
        cycle_end = datetime.strptime(match.group(2).strip(), "%m/%d/%y").date()
    except ValueError as exc:
        raise ValueError(
            "Opening/Closing dates on this Chase PDF use a format we do not recognize yet."
        ) from exc
    return cycle_start, cycle_end


def _posting_date_iso_for_month_day(
    month_day: str,
    *,
    cycle_start: datetime.date,
    cycle_end: datetime.date,
) -> str:
    """
    Formal:  Resolves MM/DD to ISO date near the printed billing window.
    Human:   Avoids wrong calendar year when December and January both appear.

    Accounting Rule:
        Posting follows the bank’s printed Date of Transaction column.
    """
    parts = str(month_day).strip().split("/")
    if len(parts) != 2:
        raise ValueError(f"Expected MM/DD, got {month_day!r}.")
    month = int(parts[0])
    day = int(parts[1])
    slack_before = cycle_start - timedelta(days=7)
    slack_after = cycle_end + timedelta(days=7)
    for year in range(cycle_start.year - 1, cycle_end.year + 2):
        try:
            candidate = datetime(year, month, day).date()
        except ValueError:
            continue
        if slack_before <= candidate <= slack_after:
            return candidate.isoformat()
    raise ValueError(
        f"Could not assign a year to transaction date {month_day!r} within this statement cycle."
    )


def _parse_account_activity_line(line: str) -> tuple[str, str, Decimal] | None:
    """
    Formal:  One “Date of Transaction / Merchant / Amount” row from ACCOUNT ACTIVITY.
    Human:   Amount is always the last whitespace-separated token.

    Accounting Rule:
        One bank line → one ledger input row downstream.
    """
    stripped = str(line).strip()
    date_prefix = re.match(r"^(\d{1,2}/\d{1,2})\s+", stripped)
    if not date_prefix:
        return None
    month_day = date_prefix.group(1)
    remainder = stripped[date_prefix.end() :].strip()
    parts = remainder.split()
    if len(parts) < 2:
        return None
    amount_token = parts[-1]
    if not _money_tail_token_looks_like(amount_token):
        return None
    try:
        amount_value = _parse_money_token(amount_token)
    except ValueError:
        return None
    description = " ".join(parts[:-1]).strip()
    if description == "":
        return None
    return month_day, description, amount_value


def extract_chase_credit_card_statement_lines_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Formal:  Reads a Chase credit card PDF and returns rows: posting_date_iso, payee, amount, reference.
    Human:   Use with “Chase credit card PDF (built-in)” on Statement Upload.

    Accounting Rule:
        Returns Decimal amounts and ISO dates for statement-import posting.
    """
    if len(pdf_bytes) < 8 or not pdf_bytes[:5].startswith(b"%PDF"):
        raise ValueError(
            "This file does not look like a PDF. Upload the Chase card statement as exported from Chase."
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
            "No readable text could be pulled from this PDF. Image-only statements need another path."
        )

    full_text = "\n".join(full_text_chunks)
    cycle_start, cycle_end = _cycle_bounds_from_opening_closing(full_text)

    noise_prefixes = (
        "date of",
        "transaction merchant",
        "transactions this cycle",
        "including payments received",
        "year-to-date",
        "year--to--date",
        "total fees charged",
        "total interest charged",
        "interest charge",
        "balance type",
        "annual balance",
        "purchases ",
        "cash advances",
        "balance transfers",
        "my chase loan",
        "page ",
    )

    lines_out: list[dict] = []

    for raw_line in full_text.splitlines():
        line = str(raw_line).strip()
        if len(line) < 6:
            continue
        lower = line.lower()
        if any(lower.startswith(prefix) for prefix in noise_prefixes):
            continue
        if re.match(r"^\d+\s+Days in Billing", line, re.I):
            continue

        parsed = _parse_account_activity_line(line)
        if parsed is None:
            continue
        month_day, description, amount_value = parsed
        try:
            posting_date_iso = _posting_date_iso_for_month_day(
                month_day,
                cycle_start=cycle_start,
                cycle_end=cycle_end,
            )
        except ValueError:
            continue
        if len(description) > 500:
            description = description[:500]

        lines_out.append(
            {
                "posting_date_iso": posting_date_iso,
                "payee": description,
                "amount": amount_value,
                "reference": "",
            }
        )

    if len(lines_out) == 0:
        raise ValueError(
            "No transaction rows matched this Chase credit card PDF layout. The export may have changed — "
            "try CSV if available, or share a redacted sample to extend the parser."
        )

    return lines_out
