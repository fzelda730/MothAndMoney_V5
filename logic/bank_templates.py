"""
MOTH AND MONEY — BANK TEMPLATES (LOGIC)
/logic/bank_templates.py

Formal:  Validation and orchestration for bank_templates saves and ingest listing.
Human:   Keeps Template Manager honest before anything touches the database.
"""

from __future__ import annotations

import io

import pandas

from database.bank_template_chart_links_repository import (
    list_linked_account_numbers_for_template,
    replace_linked_account_numbers_for_template,
)
from database.bank_templates_repository import (
    count_bank_templates_by_normalized_name,
    fetch_all_bank_templates_ordered_for_menu,
    fetch_bank_template_row_by_identifier,
    insert_bank_template_row,
    retire_legacy_chase_pdf_builtin_template_row,
    seed_capital_one_card_built_in_template_row,
    seed_chase_checking_built_in_template_row,
    seed_chase_credit_card_built_in_template_row,
)
from database.chart_of_accounts_repository import (
    fetch_active_chart_accounts_ordered,
    fetch_all_chart_accounts_ordered,
)
from database.connection import open_database_session

CSV_HEADERS_KIND = "csv_headers"
BUILT_IN_PDF_KIND = "built_in_pdf"


def load_linked_chart_account_numbers_for_bank_template(
    bank_template_identifier: int,
) -> list[int]:
    """
    Formal:  Account numbers in bank_template_chart_links for this template, sorted ascending.
    Human:   Empty list means Statement Upload may offer every active chart account.

    Accounting Rule:
        Read-only; does not validate that accounts stay active.
    """
    with open_database_session() as database_session:
        return list_linked_account_numbers_for_template(
            database_session, bank_template_id=int(bank_template_identifier)
        )


def describe_linked_chart_accounts_for_bank_template_catalog(
    bank_template_identifier: int,
) -> str:
    """
    Formal:  One display string for Template Manager (and messages): linked account numbers
            resolved to names via chart_of_accounts, including inactive rows.

    Human:   Confirm which buckets you attached to this template without opening the expander.

    Accounting Rule:
        Read-only snapshot; missing chart rows still show the account number.
    """
    with open_database_session() as database_session:
        linked_account_numbers = list_linked_account_numbers_for_template(
            database_session, bank_template_id=int(bank_template_identifier)
        )
        if len(linked_account_numbers) == 0:
            return "— (any active account on Statement Upload)"

        all_chart_rows = fetch_all_chart_accounts_ordered(database_session)
        chart_row_by_account_number: dict[int, dict] = {
            int(chart_row["account_number"]): chart_row for chart_row in all_chart_rows
        }

        display_fragments: list[str] = []
        for account_number in linked_account_numbers:
            chart_row = chart_row_by_account_number.get(int(account_number))
            if chart_row is None:
                display_fragments.append(f"{int(account_number)} (not on chart)")
                continue
            account_label = str(chart_row["account_name"]).strip()
            inactive_note = (
                ""
                if int(chart_row.get("is_active") or 0) == 1
                else " (inactive)"
            )
            display_fragments.append(
                f"{int(account_number)} — {account_label}{inactive_note}"
            )
        return "; ".join(display_fragments)


def save_linked_chart_accounts_for_bank_template(
    *,
    bank_template_identifier: int,
    chart_account_numbers: list[int],
) -> None:
    """
    Formal:  Replaces all bank_template_chart_links rows for one csv_headers or built_in_pdf template.
    Human:   Template Manager “allowed accounts” save for CSV maps and packaged PDF drivers.

    Accounting Rule:
        Only csv_headers and built_in_pdf rows; chart accounts must exist or the database rejects the link.
    """
    with open_database_session() as database_session:
        template_row = fetch_bank_template_row_by_identifier(
            database_session, bank_template_id=int(bank_template_identifier)
        )
        if template_row is None:
            raise ValueError(
                "That template was not found. Refresh Template Manager and try again."
            )
        ingest_kind = str(template_row.get("ingest_kind") or "")
        if ingest_kind not in (CSV_HEADERS_KIND, BUILT_IN_PDF_KIND):
            raise ValueError(
                "Only CSV column maps and built-in PDF drivers can use a chart-account short list."
            )
        replace_linked_account_numbers_for_template(
            database_session,
            bank_template_id=int(bank_template_identifier),
            account_numbers=list(chart_account_numbers),
        )


def save_linked_chart_accounts_for_csv_bank_template(
    *,
    bank_template_identifier: int,
    chart_account_numbers: list[int],
) -> None:
    """
    Formal:  Backward-compatible name for save_linked_chart_accounts_for_bank_template.
    Human:   Prefer save_linked_chart_accounts_for_bank_template in new code.

    Accounting Rule:
        Same as save_linked_chart_accounts_for_bank_template.
    """
    save_linked_chart_accounts_for_bank_template(
        bank_template_identifier=bank_template_identifier,
        chart_account_numbers=chart_account_numbers,
    )


def statement_upload_chart_account_rows_respecting_template_links(
    *,
    chosen_template_row: dict,
    all_active_chart_account_rows: list[dict],
) -> tuple[list[dict], str | None]:
    """
    Formal:  Narrows active chart rows to bank_template_chart_links when the template has links.
    Human:   Short list for CSV maps and built-in PDF drivers (e.g. several Chase buckets, one parser).

    Accounting Rule:
        Templates without links, or unknown ingest_kind, leave the full active list. If every linked
        account is inactive, fall back to the full active list and return a warning message for the UI.
    """
    ingest_kind = str(chosen_template_row.get("ingest_kind") or "")
    if ingest_kind not in (CSV_HEADERS_KIND, BUILT_IN_PDF_KIND):
        return all_active_chart_account_rows, None

    template_primary_key = int(chosen_template_row["id"])
    linked_account_numbers = load_linked_chart_account_numbers_for_bank_template(
        template_primary_key
    )
    if len(linked_account_numbers) == 0:
        return all_active_chart_account_rows, None

    allowed_account_numbers = set(linked_account_numbers)
    filtered_rows = [
        chart_row
        for chart_row in all_active_chart_account_rows
        if int(chart_row["account_number"]) in allowed_account_numbers
    ]
    if len(filtered_rows) == 0:
        return (
            all_active_chart_account_rows,
            "None of the linked chart accounts are active right now — showing every active account "
            "so you can still post. Update links under Template Manager or reactivate an account.",
        )
    return filtered_rows, None


def load_active_chart_accounts_for_template_picker() -> list[dict]:
    """
    Formal:  Active chart_of_accounts rows for linking a bank CSV template.
    Human:   Pick which bucket this bank file feeds.

    Accounting Rule:
        Retired accounts (is_active = 0) never appear in the picker.
    """
    with open_database_session() as database_session:
        return fetch_active_chart_accounts_ordered(database_session)


def ensure_builtin_bank_template_rows() -> None:
    """
    Formal:  Registers built-in PDF drivers (Chase credit card, Chase checking, Capital One card)
             idempotently; drops the legacy “Chase PDF (built-in)” row if it still exists.
    Human:   Statement Upload always sees them in the same dropdown as CSV maps.

    Accounting Rule:
        Built-in rows carry no CSV columns; parsing is bound by built_in_parser_key.
    """
    with open_database_session() as database_session:
        retire_legacy_chase_pdf_builtin_template_row(database_session)
        seed_chase_credit_card_built_in_template_row(database_session)
        seed_chase_checking_built_in_template_row(database_session)
        seed_capital_one_card_built_in_template_row(database_session)


def list_bank_templates_for_ingest_menu() -> list[dict]:
    """
    Formal:  All bank_templates rows ordered for UI select controls.
    Human:   One list for Template Manager review and Statement Upload.

    Accounting Rule:
        Includes both csv_headers maps and built_in_pdf registry entries.
    """
    with open_database_session() as database_session:
        return fetch_all_bank_templates_ordered_for_menu(database_session)


def ingest_menu_display_label(template_row: dict) -> str:
    """
    Formal:  Single-line label for selectboxes (includes kind hint for built-ins).
    Human:   You can tell a parser from your own CSV map at a glance.
    """
    template_name = str(template_row["name"]).strip()
    if template_row.get("ingest_kind") == BUILT_IN_PDF_KIND:
        return f"{template_name} — built-in PDF"
    return template_name


def read_csv_header_labels_from_bytes(csv_bytes: bytes) -> list[str]:
    """
    Formal:  Parses the first row of a CSV byte string into trimmed column headers.
    Human:   Upload a sample so the forge can match Date / Payee / Amount.

    Accounting Rule:
        Structural parse only — no dollar normalization here.
    """
    buffer = io.BytesIO(csv_bytes)
    header_only_dataframe = pandas.read_csv(buffer, nrows=0)
    labels = [str(column_label).strip() for column_label in header_only_dataframe.columns]
    if len(labels) == 0:
        raise ValueError(
            "This CSV has no header row with column names. Export again with headers, then retry."
        )
    return labels


def build_bank_csv_template_preview_dataframe(
    csv_bytes: bytes,
    *,
    date_col: str,
    payee_col: str,
    amount_col: str,
    reference_col: str = "",
    max_data_rows: int = 5,
) -> pandas.DataFrame:
    """
    Formal:  Reads up to max_data_rows from a CSV byte string and projects
            bank_templates date_col, payee_col, amount_col, and optional reference_col.
    Human:   Lets you eyeball whether the mapped headers point at sensible cells
            before saving the template.

    Accounting Rule:
        Preview only: raw CSV cells are shown — no journal lines, no Decimal normalization,
        and no posting. Ingest will reuse the same structural read (pandas.read_csv).
    """
    if max_data_rows < 1:
        raise ValueError("Preview needs at least one data row to read.")

    date_col_stripped = str(date_col).strip()
    payee_col_stripped = str(payee_col).strip()
    amount_col_stripped = str(amount_col).strip()
    reference_col_stripped = str(reference_col).strip()
    if date_col_stripped == "" or payee_col_stripped == "" or amount_col_stripped == "":
        raise ValueError(
            "Date column, Payee column, and Amount column must each pick a real CSV header."
        )

    distinct_required = {date_col_stripped, payee_col_stripped, amount_col_stripped}
    if len(distinct_required) < 3:
        raise ValueError(
            "Date, Payee, and Amount must be three different columns from your sample file."
        )
    if reference_col_stripped != "":
        if reference_col_stripped in distinct_required:
            raise ValueError(
                "Reference column must be different from Date, Payee, and Amount."
            )

    try:
        buffer = io.BytesIO(csv_bytes)
        sample_frame = pandas.read_csv(buffer, nrows=max_data_rows)
    except Exception as parse_error:
        raise ValueError(
            "Could not read sample rows from this CSV. Check encoding and commas, then retry."
        ) from parse_error

    check_pairs: list[tuple[str, str]] = [
        (date_col_stripped, "Date"),
        (payee_col_stripped, "Payee"),
        (amount_col_stripped, "Amount"),
    ]
    if reference_col_stripped != "":
        check_pairs.append((reference_col_stripped, "Reference"))

    missing_labels: list[str] = []
    for column_name, friendly in check_pairs:
        if column_name not in sample_frame.columns:
            missing_labels.append(f"{friendly} ({column_name!r})")
    if len(missing_labels) > 0:
        raise ValueError(
            "These mapped columns are missing from the parsed file: "
            + ", ".join(missing_labels)
            + ". Re-pick headers or use a sample that matches this export shape."
        )

    source_column_names = [
        date_col_stripped,
        payee_col_stripped,
        amount_col_stripped,
    ]
    display_column_names = [
        "Transaction date",
        "Payee / description",
        "Amount",
    ]
    if reference_col_stripped != "":
        source_column_names.append(reference_col_stripped)
        display_column_names.append("Reference")

    column_slice = sample_frame[source_column_names].copy()
    column_slice.columns = display_column_names
    return column_slice


def save_user_csv_bank_template(
    *,
    template_name: str,
    date_col: str,
    payee_col: str,
    amount_col: str,
    reference_col: str = "",
    is_liability: bool,
) -> None:
    """
    Formal:  Validates and inserts a csv_headers bank_templates row with no linked chart account.
    Human:   Save Template stores your column map only; you choose the money bucket on Statement Upload.

    Accounting Rule:
        linked_account_number is always NULL for user-defined CSV maps. Date, Payee, and Amount
        columns must differ; optional reference_col must differ from those three when set.
    """
    cleaned_name = str(template_name).strip()
    if cleaned_name == "":
        raise ValueError("Template name cannot be empty.")

    date_col_stripped = str(date_col).strip()
    payee_col_stripped = str(payee_col).strip()
    amount_col_stripped = str(amount_col).strip()
    reference_col_stripped = str(reference_col).strip()
    if date_col_stripped == "" or payee_col_stripped == "" or amount_col_stripped == "":
        raise ValueError(
            "Date column, Payee column, and Amount column must each pick a real CSV header."
        )
    if len({date_col_stripped, payee_col_stripped, amount_col_stripped}) < 3:
        raise ValueError(
            "Date, Payee, and Amount must be three different columns from your sample file."
        )
    if reference_col_stripped != "":
        if reference_col_stripped in {
            date_col_stripped,
            payee_col_stripped,
            amount_col_stripped,
        }:
            raise ValueError(
                "Reference column must be different from Date, Payee, and Amount."
            )

    liability_flag = 1 if is_liability else 0

    with open_database_session() as database_session:
        if count_bank_templates_by_normalized_name(database_session, cleaned_name) > 0:
            raise ValueError(
                "Another template already uses this name. Pick a unique template name."
            )
        insert_bank_template_row(
            database_session,
            template_name=cleaned_name,
            linked_account_number=None,
            date_col=date_col_stripped,
            payee_col=payee_col_stripped,
            amount_col=amount_col_stripped,
            reference_col=reference_col_stripped,
            is_liability=liability_flag,
            ingest_kind=CSV_HEADERS_KIND,
            built_in_parser_key=None,
        )
