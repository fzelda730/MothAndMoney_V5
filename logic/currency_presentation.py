"""
MOTH AND MONEY — CURRENCY PRESENTATION (DISPLAY STRINGS)
/logic/currency_presentation.py

Formal:  Builds human-facing currency strings for reports and stat cards (US grouping).
Human:   Standard English-style money: commas between thousands, two cent digits.

Accounting Rule:
    Uses quantize to two decimal places; display only — never use these strings for math.
"""

from __future__ import annotations

from decimal import Decimal


def _insert_comma_thousands_grouping(integer_digits: str) -> str:
    """
    Formal:  Inserts a comma every three digits from the right for the whole-dollar part.
    Human:   Turns 8770 into 8,770 so large balances scan like bank statements.

    Accounting Rule:
        Display helper only; does not change ledger precision.
    """
    digit_run = integer_digits.lstrip("0") or "0"
    if len(digit_run) <= 3:
        return digit_run
    grouped_chunks: list[str] = []
    remaining = digit_run
    while remaining:
        grouped_chunks.append(remaining[-3:])
        remaining = remaining[:-3]
    grouped_chunks.reverse()
    return ",".join(grouped_chunks)


def format_currency_standard_us(
    ledger_amount: Decimal | float | str | int,
) -> str:
    """
    Formal:  Returns a dollar-prefixed string with comma thousands and a decimal point
             before cents (example: 8770.00 becomes \"$8,770.00\").
    Human:   The usual U.S. number shape for accountants and banks.

    Accounting Rule:
        Quantizes to cents; negative amounts get a leading minus before the dollar sign.
    """
    quantized_amount = Decimal(str(ledger_amount)).quantize(Decimal("0.01"))
    is_negative = quantized_amount < 0
    absolute_amount = abs(quantized_amount)
    cents_string = format(absolute_amount, "f")
    whole_part, fractional_part = cents_string.split(".", maxsplit=1)
    comma_grouped_whole = _insert_comma_thousands_grouping(whole_part)
    body = f"${comma_grouped_whole}.{fractional_part}"
    if is_negative:
        return f"-{body}"
    return body
