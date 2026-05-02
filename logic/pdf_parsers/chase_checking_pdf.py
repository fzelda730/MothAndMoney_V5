"""
MOTH AND MONEY — CHASE CHECKING / DEPOSIT PDF (LOGIC)
/logic/pdf_parsers/chase_checking_pdf.py

Formal:  Extract transaction lines from Chase deposit (Total Checking-style) PDF statements.
Human:   Use when Statement Upload’s driver is Chase checking PDF (built-in); Chase cards use Chase credit card PDF.

Accounting Rule:
    Structural parse only; amount is the transaction column (not running balance). Posting date is
    the statement DATE column for each line.
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import pdfplumber

# e.g. "December 06, 2025throughJanuary 08, 2026" (often no space before "through")
_DEPOSIT_STATEMENT_CYCLE_PATTERN = re.compile(
    r"([A-Za-z]+\s+\d{1,2},\s*\d{4})\s*through\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})",
    flags=re.IGNORECASE,
)

_TRANSACTION_SECTION_START = "*start*transaction detail"
_TRANSACTION_SECTION_END = "*end*transaction detail"

_TRANSACTION_NUMBER_LINE_PATTERN = re.compile(
    r"^Transaction #:\s*(.+?)\s*$",
    flags=re.IGNORECASE,
)


def _parse_money_token(token: str) -> Decimal:
    """
    Formal:  Normalizes a Chase checking amount cell with optional $ and commas.
    Human:   Matches +20.00, -15.00, -$19.96 style cells.

    Accounting Rule:
        Display-layer only; ledger posting still uses Decimal from these values.
    """
    cleaned = str(token).strip().replace("$", "").replace(",", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        inner = cleaned[1:-1].strip()
        try:
            return -Decimal(inner)
        except InvalidOperation as exc:
            raise ValueError(f"Could not read amount {token!r}.") from exc
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Could not read amount {token!r}.") from exc


def _money_token_looks_like(token: str) -> bool:
    """Formal: True if token matches a Chase currency cell pattern."""
    stripped = str(token).strip().replace("$", "").replace(",", "")
    return bool(re.fullmatch(r"-?\d+\.\d{2}", stripped))


def _parse_deposit_cycle_bounds(pdf_full_text: str) -> tuple[datetime.date, datetime.date]:
    """
    Formal:  Reads “December 06, 2025throughJanuary 08, 2026” into cycle start and end dates.
    Human:   Transaction lines only show MM/DD; this fixes the calendar year.

    Accounting Rule:
        N/A — date inference for statement period only.
    """
    match = _DEPOSIT_STATEMENT_CYCLE_PATTERN.search(pdf_full_text)
    if not match:
        raise ValueError(
            "Could not find a Chase deposit statement period (Month DD, YYYY through Month DD, YYYY). "
            "This file may be a credit card or foreign layout — pick the matching driver."
        )
    start_raw = match.group(1).strip().replace("  ", " ")
    end_raw = match.group(2).strip().replace("  ", " ")
    try:
        cycle_start = datetime.strptime(start_raw, "%B %d, %Y").date()
        cycle_end = datetime.strptime(end_raw, "%B %d, %Y").date()
    except ValueError as exc:
        raise ValueError(
            "Chase deposit statement dates in this PDF use a format we do not recognize yet."
        ) from exc
    return cycle_start, cycle_end


def _posting_date_iso_for_month_day(
    month_day: str,
    *,
    cycle_start: datetime.date,
    cycle_end: datetime.date,
) -> str:
    """
    Formal:  Resolves MM/DD to ISO date near the printed statement cycle.
    Human:   Stops wrong-year surprises when the cycle crosses January 1.

    Accounting Rule:
        Posting follows the bank’s printed transaction date column.
    """
    parts = str(month_day).strip().split("/")
    if len(parts) != 2:
        raise ValueError(f"Expected MM/DD, got {month_day!r}.")
    month = int(parts[0])
    day = int(parts[1])
    slack_before = cycle_start - timedelta(days=14)
    slack_after = cycle_end + timedelta(days=14)
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


def _extract_transaction_detail_text(pdf_full_text: str) -> str:
    """
    Formal:  Prefer text between Chase *start*transaction detail markers when present.
    Human:   Reduces accidental matches outside the transaction grid.

    Accounting Rule:
        N/A — parse boundary only.
    """
    lower_full = pdf_full_text.lower()
    start_tag = _TRANSACTION_SECTION_START.lower()
    end_tag = _TRANSACTION_SECTION_END.lower()
    start_pos = lower_full.find(start_tag)
    end_pos = lower_full.find(end_tag)
    if start_pos != -1 and end_pos != -1 and end_pos > start_pos:
        return pdf_full_text[start_pos:end_pos]
    return pdf_full_text


def _parse_transaction_detail_line(line: str) -> tuple[str, str, Decimal] | None:
    """
    Formal:  One checking detail row: MM/DD, description, amount (drops running balance).
    Human:   Chase prints DATE DESCRIPTION AMOUNT BALANCE — we keep amount, not balance.

    Accounting Rule:
        Amount signs follow the statement (deposits positive, fees negative for assets).
    """
    stripped = str(line).strip()
    match = re.match(r"^(\d{1,2}/\d{1,2})\s+(.+)$", stripped)
    if not match:
        return None
    month_day = match.group(1)
    remainder = match.group(2).strip()
    tokens = remainder.split()
    if len(tokens) < 3:
        return None
    balance_token = tokens[-1]
    amount_token = tokens[-2]
    if not _money_token_looks_like(balance_token) or not _money_token_looks_like(amount_token):
        return None
    try:
        amount_value = _parse_money_token(amount_token)
        _parse_money_token(balance_token)
    except ValueError:
        return None
    description = " ".join(tokens[:-2]).strip()
    if description == "":
        return None
    return month_day, description, amount_value


def extract_chase_checking_statement_lines_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Formal:  Reads a Chase checking / deposit PDF and returns rows with posting_date_iso, payee,
            amount (Decimal), reference (transaction number when printed on the next line).
    Human:   Pick “Chase checking PDF (built-in)” on Statement Upload.

    Accounting Rule:
        One logical transaction per grid row; a following “Transaction #:” line fills reference on
        the row above it.
    """
    if len(pdf_bytes) < 8 or not pdf_bytes[:5].startswith(b"%PDF"):
        raise ValueError(
            "This file does not look like a PDF. Upload the checking statement export from Chase."
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
            "No readable text could be pulled from this PDF. Scanned statements need another path — "
            "try CSV download, if Chase offers it."
        )

    full_text = "\n".join(full_text_chunks)
    cycle_start, cycle_end = _parse_deposit_cycle_bounds(full_text)
    section_text = _extract_transaction_detail_text(full_text)

    lines_out: list[dict] = []

    for raw_line in section_text.splitlines():
        line = str(raw_line).strip()
        lower = line.lower()

        txn_number_match = _TRANSACTION_NUMBER_LINE_PATTERN.match(line)
        if txn_number_match:
            transaction_token = str(txn_number_match.group(1)).strip()[:200]
            if len(lines_out) > 0:
                lines_out[-1]["reference"] = transaction_token
            continue

        if len(line) < 5:
            continue
        if lower in (
            "transaction detail",
            "date description amount balance",
            "date description amount",
        ):
            continue
        if lower.startswith("beginning balance") or lower.startswith("ending balance"):
            continue

        parsed = _parse_transaction_detail_line(line)
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

        lines_out.append(
            {
                "posting_date_iso": posting_date_iso,
                "payee": description[:500],
                "amount": amount_value,
                "reference": "",
            }
        )

    if len(lines_out) == 0:
        raise ValueError(
            "No transaction rows matched this Chase checking PDF layout. The export format may "
            "have changed — use CSV for now or share a redacted sample so the parser can be extended."
        )

    return lines_out
