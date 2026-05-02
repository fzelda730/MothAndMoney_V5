"""
MOTH AND MONEY — CSV STATEMENT EXTRACT (LOGIC)
/logic/csv_statement_extract.py

Formal:  Maps a saved bank_templates csv_headers row onto a full CSV upload for posting.
Human:   Statement Upload uses the same column names you trained in Template Manager.

Accounting Rule:
    Dates normalized to ISO; amounts as Decimal; empty reference allowed.
"""

from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation

import pandas

from logic.bank_templates import CSV_HEADERS_KIND
from logic.statement_preview_formatting import statement_preview_amount_label


def transaction_dicts_from_csv_template(*, template_row: dict, csv_bytes: bytes) -> list[dict]:
    """
    Formal:  Reads an entire CSV using template_row date_col, payee_col, amount_col, reference_col.
    Human:   One row per bank line becomes one transaction for Review-and-post.

    Accounting Rule:
        Skips blank dates; raises on unusable money cells so the ledger never silently corrupts.
    """
    if template_row.get("ingest_kind") != CSV_HEADERS_KIND:
        raise ValueError("CSV statement extract requires a csv_headers template row.")

    date_column = str(template_row.get("date_col") or "").strip()
    payee_column = str(template_row.get("payee_col") or "").strip()
    amount_column = str(template_row.get("amount_col") or "").strip()
    reference_column = str(template_row.get("reference_col") or "").strip()

    buffer = io.BytesIO(csv_bytes)
    try:
        statement_frame = pandas.read_csv(buffer)
    except Exception as parse_error:
        raise ValueError(
            "Could not read this CSV. Export again as UTF-8 with commas, then retry."
        ) from parse_error

    for required_label in (date_column, payee_column, amount_column):
        if required_label not in statement_frame.columns:
            raise ValueError(
                f"Column {required_label!r} is missing from this file — it no longer matches this template."
            )

    if reference_column != "" and reference_column not in statement_frame.columns:
        raise ValueError(
            f"Reference column {reference_column!r} is missing from this file — re-export or adjust the template."
        )

    def _parse_amount_cell(raw_amount: object) -> Decimal:
        """
        Formal:  Strip currency decoration and parentheses-for-negative from CSV cells.
        Human:   Matches how exports often wrap debits.

        Accounting Rule:
            Structural normalization; posting still uses Decimal end-to-end.
        """
        amount_text = str(raw_amount).strip().replace(",", "").replace("$", "")
        if amount_text.startswith("(") and amount_text.endswith(")"):
            amount_text = "-" + amount_text[1:-1].strip()
        try:
            return Decimal(amount_text)
        except InvalidOperation as exc:
            raise ValueError(
                f"Could not read amount {raw_amount!r} as money."
            ) from exc

    transactions: list[dict] = []
    for _, row in statement_frame.iterrows():
        raw_date = row[date_column]
        if pandas.isna(raw_date) or str(raw_date).strip() == "":
            continue
        parsed_timestamp = pandas.to_datetime(raw_date, errors="coerce")
        if pandas.isna(parsed_timestamp):
            raise ValueError(
                f"Could not read posting date {raw_date!r}. Fix the CSV or widen the date format."
            )
        posting_date_iso = parsed_timestamp.date().isoformat()

        payee_cell = row[payee_column]
        payee_text = "" if pandas.isna(payee_cell) else str(payee_cell).strip()

        raw_amount = row[amount_column]
        if pandas.isna(raw_amount):
            continue
        amount_value = _parse_amount_cell(raw_amount)

        reference_text = ""
        if reference_column != "":
            reference_cell = row[reference_column]
            if not pandas.isna(reference_cell):
                reference_text = str(reference_cell).strip()

        transactions.append(
            {
                "posting_date_iso": posting_date_iso,
                "payee": payee_text[:500],
                "amount": amount_value,
                "reference": reference_text[:500],
            }
        )

    if len(transactions) == 0:
        raise ValueError(
            "No usable rows were found (check dates and column mapping against this export)."
        )

    return transactions


def dataframe_from_csv_statement_transactions(transactions: list[dict]) -> pandas.DataFrame:
    """
    Formal:  Same rows as posting dicts, renamed for Streamlit preview tables.
    Human:   Matches the PDF preview column titles for one consistent Review grid.

    Accounting Rule:
        Amount column uses thousands separators and two decimals for display; posting still
        reads Decimal from transaction_dicts_from_csv_template, not this frame.
    """
    frame = pandas.DataFrame(transactions)
    if len(frame.columns) == 0:
        return frame
    renamed = frame.rename(
        columns={
            "posting_date_iso": "Posting date",
            "payee": "Payee / description",
            "amount": "Amount",
            "reference": "Reference",
        }
    )
    renamed["Amount"] = renamed["Amount"].map(statement_preview_amount_label)
    return renamed
