"""
MOTH AND MONEY — BUILT-IN PDF EXTRACT (LOGIC)
/logic/built_in_pdf_extract.py

Formal:  Dispatches bank_templates.built_in_parser_key to a PDF parser and returns a DataFrame.
Human:   Statement Upload stays dumb — the registry row chooses which code runs.

Accounting Rule:
    Preview and posting both consume the same normalized columns: posting_date_iso, payee, amount, reference.
"""

from __future__ import annotations

from decimal import Decimal

from collections.abc import Callable

import pandas

from logic.bank_templates import BUILT_IN_PDF_KIND
from logic.statement_preview_formatting import statement_preview_amount_label
from logic.pdf_parsers.capital_one_card_pdf import (
    extract_capital_one_card_statement_lines_from_pdf,
)
from logic.pdf_parsers.chase_checking_pdf import (
    extract_chase_checking_statement_lines_from_pdf,
)
from logic.pdf_parsers.chase_credit_card_pdf import (
    extract_chase_credit_card_statement_lines_from_pdf,
)

_PARSER_REGISTRY: dict[str, Callable[[bytes], list[dict]]] = {
    "capital_one_card_pdf": extract_capital_one_card_statement_lines_from_pdf,
    "chase_checking_pdf": extract_chase_checking_statement_lines_from_pdf,
    "chase_credit_card_pdf": extract_chase_credit_card_statement_lines_from_pdf,
}


def dataframe_from_built_in_pdf(*, template_row: dict, pdf_bytes: bytes) -> pandas.DataFrame:
    """
    Formal:  Runs the packaged PDF parser for this bank_templates row and returns a display frame.
    Human:   You already picked a built-in PDF driver (e.g. Chase credit card or checking) in the list.

    Accounting Rule:
        Amount column is human-formatted text for Review only; use the same ingest path’s
        transaction dicts for Decimal posting values.
    """
    if template_row.get("ingest_kind") != BUILT_IN_PDF_KIND:
        raise ValueError(
            "Internal mismatch: PDF extract was called for a template that is not built_in_pdf."
        )
    parser_key = str(template_row.get("built_in_parser_key") or "").strip()
    if parser_key not in _PARSER_REGISTRY:
        raise ValueError(
            f"No PDF parser ships for {parser_key!r} yet. Use CSV for this bank or extend the forge."
        )
    parser_callable = _PARSER_REGISTRY[parser_key]
    transaction_rows: list[dict] = parser_callable(pdf_bytes)
    frame = pandas.DataFrame(transaction_rows)
    if len(frame.columns) > 0:
        display_frame = frame.rename(
            columns={
                "posting_date_iso": "Posting date",
                "payee": "Payee / description",
                "amount": "Amount",
                "reference": "Reference",
            }
        )
        display_frame["Amount"] = display_frame["Amount"].map(statement_preview_amount_label)
        return display_frame
    return frame


def bank_statement_transactions_for_posting(
    *, template_row: dict, pdf_bytes: bytes
) -> list[dict]:
    """
    Formal:  Same parse as preview, but returns posting dicts with Decimal amounts and ISO dates.
    Human:   Commit on Statement Upload calls this after you approve the grid.

    Accounting Rule:
        Rows match ledger line factory input; duplicates blocked by source_metadata on journal header.
    """
    parser_key = str(template_row.get("built_in_parser_key") or "").strip()
    if parser_key not in _PARSER_REGISTRY:
        raise ValueError(
            f"No PDF parser ships for {parser_key!r} yet. Use CSV for this bank or extend the forge."
        )
    rows = _PARSER_REGISTRY[parser_key](pdf_bytes)
    normalized: list[dict] = []
    for row in rows:
        posting_date_iso = str(row["posting_date_iso"])
        payee = str(row["payee"])
        amount = row["amount"]
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        reference = str(row.get("reference") or "")
        normalized.append(
            {
                "posting_date_iso": posting_date_iso,
                "payee": payee,
                "amount": amount,
                "reference": reference,
            }
        )
    return normalized
