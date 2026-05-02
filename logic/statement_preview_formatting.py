"""
MOTH AND MONEY — STATEMENT PREVIEW FORMATTING (LOGIC)
/logic/statement_preview_formatting.py

Formal:  Turns Decimal statement amounts into fixed-width, thousands-grouped strings for UI grids.
Human:   Statement Upload preview only — posting still uses Decimal, not these strings.

Accounting Rule:
    Preview is cosmetic; ledger math stays on exact Decimal from ingest.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def statement_preview_amount_label(amount_value: object) -> str:
    """
    Formal:  Returns a locale-style money label (e.g. 1,518.22 and 50.00) for Streamlit tables.
    Human:   Makes Review grids match how bank statements look.

    Accounting Rule:
        Quantize to cents for display; does not replace source Decimal on post.
    """
    if isinstance(amount_value, Decimal):
        money_decimal = amount_value
    else:
        try:
            money_decimal = Decimal(str(amount_value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"Preview could not format amount {amount_value!r}.") from exc
    quantized = money_decimal.quantize(Decimal("0.01"))
    return format(quantized, ",.2f")
