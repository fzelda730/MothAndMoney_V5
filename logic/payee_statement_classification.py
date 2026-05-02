"""
MOTH AND MONEY — PAYEE STATEMENT CLASSIFICATION (LOGIC)
/logic/payee_statement_classification.py

Formal:  Suggests ledger offset accounts for bank-statement lines using saved mappings,
         similar saved payees, and small category keyword hints — before post.
Human:   Your payee file is checked first; then a gentle guess (mark suggested); else clearing.

Accounting Rule:
    Suggestions are presentation-only until post; 5890 clearing remains the explicit default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from difflib import get_close_matches

from sqlalchemy.orm import Session

from database.chart_of_accounts_repository import fetch_active_chart_accounts_ordered
from database.connection import open_database_session
from database.payee_chart_account_mapping_repository import (
    fetch_payee_normalized_key_to_account_number,
)
from database.statement_import_chart_seed import STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER

# Substrings (lowercase) → chart account_category for a deterministic first pick.
# Accounting Rule: Heuristic only; yellow “suggested” rows still need your eyes.
PAYEE_SUBSTRING_ACCOUNT_CATEGORY_GUESSES: tuple[tuple[str, str], ...] = (
    ("payroll", "Expense"),
    ("salary", "Expense"),
    ("gusto", "Expense"),
    ("amazon", "Expense"),
    ("amzn", "Expense"),
    ("walmart", "Expense"),
    ("target", "Expense"),
    ("costco", "Expense"),
    ("restaurant", "Expense"),
    ("cafe", "Expense"),
    ("coffee", "Expense"),
    ("uber", "Expense"),
    ("lyft", "Expense"),
    ("shell", "Expense"),
    ("chevron", "Expense"),
    ("pg&e", "Expense"),
    ("utility", "Expense"),
    ("at&t", "Expense"),
    ("verizon", "Expense"),
    ("interest earned", "Revenue"),
    ("dividend", "Revenue"),
    ("stripe", "Revenue"),
    ("shopify", "Revenue"),
)


@dataclass(frozen=True)
class PayeeOffsetSuggestion:
    """
    Formal:  One suggested offset account and how it was chosen.
    Human:   Tells the UI whether to treat the row as saved, guessed, or still open.
    """

    offset_account_number: int
    classification_source: str


_CLASSIFICATION_SAVED = "saved_mapping"
_CLASSIFICATION_SIMILAR = "similar_payee_mapping"
_CLASSIFICATION_KEYWORD = "keyword_category_guess"
_CLASSIFICATION_CLEARING = "clearing_unclassified"

_MIN_SUBSTRING_MATCH_LENGTH = 3
_SIMILAR_PAYEE_CUTOFF = 0.72


def normalize_payee_for_mapping_key(raw_payee: str) -> str:
    """
    Formal:  Collapses whitespace and lowercases payee text for stable map keys.
    Human:   Stops "AMAZON" and "amazon " from duplicating memories.

    Accounting Rule:
        Keys are not shown on official reports — ledger still stores original payee text per line.
    """
    collapsed = re.sub(r"\s+", " ", str(raw_payee).strip().lower())
    return collapsed[:500]


def _account_numbers_for_category_excluding_clearing(
    *,
    active_chart_account_rows: list[dict],
    account_category: str,
) -> list[int]:
    """
    Formal:  Active account numbers in a category, excluding statement-import clearing.
    Human:   Keyword guesses never land back on 5890 by accident.
    """
    blocked = {STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER}
    numbers: list[int] = []
    for chart_row in active_chart_account_rows:
        if int(chart_row.get("is_active") or 0) != 1:
            continue
        account_number = int(chart_row["account_number"])
        if account_number in blocked:
            continue
        if str(chart_row.get("account_category") or "") != account_category:
            continue
        numbers.append(account_number)
    numbers.sort()
    return numbers


def classify_payee_for_statement_line(
    payee_text: str,
    *,
    payee_normalized_key_to_account_number: dict[str, int],
    active_chart_account_rows: list[dict],
) -> PayeeOffsetSuggestion:
    """
    Formal:  Returns offset account number and source tag for one payee string.
    Human:   Saved rule wins, then “looks like another saved payee,” then a tiny keyword hint.

    Accounting Rule:
        Default offset is STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER when nothing else applies.
    """
    clearing_number = STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER
    normalized_payee_key = normalize_payee_for_mapping_key(payee_text)
    if normalized_payee_key == "":
        return PayeeOffsetSuggestion(
            offset_account_number=clearing_number,
            classification_source=_CLASSIFICATION_CLEARING,
        )

    direct_hit = payee_normalized_key_to_account_number.get(normalized_payee_key)
    if direct_hit is not None:
        return PayeeOffsetSuggestion(
            offset_account_number=int(direct_hit),
            classification_source=_CLASSIFICATION_SAVED,
        )

    saved_keys = list(payee_normalized_key_to_account_number.keys())
    best_substring_key: str | None = None
    best_substring_length = 0
    for saved_key in saved_keys:
        if len(saved_key) < _MIN_SUBSTRING_MATCH_LENGTH:
            continue
        if saved_key in normalized_payee_key or normalized_payee_key in saved_key:
            key_length = len(saved_key)
            if key_length > best_substring_length:
                best_substring_length = key_length
                best_substring_key = saved_key

    if best_substring_key is not None:
        return PayeeOffsetSuggestion(
            offset_account_number=int(
                payee_normalized_key_to_account_number[best_substring_key]
            ),
            classification_source=_CLASSIFICATION_SIMILAR,
        )

    close_names = get_close_matches(
        normalized_payee_key,
        saved_keys,
        n=1,
        cutoff=_SIMILAR_PAYEE_CUTOFF,
    )
    if len(close_names) > 0:
        matched_key = close_names[0]
        return PayeeOffsetSuggestion(
            offset_account_number=int(
                payee_normalized_key_to_account_number[matched_key]
            ),
            classification_source=_CLASSIFICATION_SIMILAR,
        )

    lowered_full = normalized_payee_key
    for substring_hint, account_category in PAYEE_SUBSTRING_ACCOUNT_CATEGORY_GUESSES:
        if substring_hint in lowered_full:
            candidates = _account_numbers_for_category_excluding_clearing(
                active_chart_account_rows=active_chart_account_rows,
                account_category=account_category,
            )
            if len(candidates) > 0:
                return PayeeOffsetSuggestion(
                    offset_account_number=int(candidates[0]),
                    classification_source=_CLASSIFICATION_KEYWORD,
                )

    return PayeeOffsetSuggestion(
        offset_account_number=clearing_number,
        classification_source=_CLASSIFICATION_CLEARING,
    )


def human_readable_classification_source(classification_source: str) -> str:
    """
    Formal:  UI label for classification_source including visual “yellow” cue for guesses.
    Human:   Scannable status in the Review grid.
    """
    if classification_source == _CLASSIFICATION_SAVED:
        return "Saved mapping"
    if classification_source == _CLASSIFICATION_SIMILAR:
        return "🟡 Suggested — similar saved payee"
    if classification_source == _CLASSIFICATION_KEYWORD:
        return "🟡 Suggested — category hint"
    return "Unclassified (clearing)"


def build_offset_account_option_labels(
    *,
    active_chart_account_rows: list[dict],
    clearing_account_number: int,
    clearing_display_name: str = "Statement import clearing",
) -> tuple[list[str], dict[str, int]]:
    """
    Formal:  Selectbox labels for offset accounts; first label is clearing, then ascending by number.
    Human:   Matches the “number — name (category)” pattern used elsewhere in ingest.

    Accounting Rule:
        Clearing is always available so an import can stay entirely on 5890 when you prefer.
    """
    label_to_account_number: dict[str, int] = {}
    ordered_labels: list[str] = []

    clearing_label = (
        f"{clearing_account_number} — {clearing_display_name} (Expense — unclassified)"
    )
    ordered_labels.append(clearing_label)
    label_to_account_number[clearing_label] = int(clearing_account_number)

    sorted_rows = sorted(
        active_chart_account_rows,
        key=lambda chart_row: int(chart_row["account_number"]),
    )
    for chart_row in sorted_rows:
        account_number = int(chart_row["account_number"])
        if account_number == clearing_account_number:
            continue
        account_name = str(chart_row.get("account_name") or "")
        account_category = str(chart_row.get("account_category") or "")
        label = f"{account_number} — {account_name} ({account_category})"
        ordered_labels.append(label)
        label_to_account_number[label] = account_number

    return ordered_labels, label_to_account_number


def offset_account_number_from_option_label(option_label: str) -> int:
    """
    Formal:  Parses the leading account number token from a selectbox label.
    Human:   Same trick as the target-account picker on Statement Upload.

    Accounting Rule:
        N/A — round-trip for UI state only.
    """
    account_token = str(option_label).split("—")[0].strip()
    return int(account_token)


def enrich_statement_transactions_with_payee_offsets(
    database_session: Session,
    *,
    transaction_rows: list[dict],
) -> list[dict]:
    """
    Formal:  Returns a shallow copy of each transaction dict with offset_account_number
             and classification_source filled from saved data and heuristics.
    Human:   Run once per preview so the grid can show suggestions before you post.

    Accounting Rule:
        Amounts and dates are untouched; offset defaults to clearing when unknown.
    """
    mapping_dictionary = fetch_payee_normalized_key_to_account_number(database_session)
    active_chart_rows = fetch_active_chart_accounts_ordered(database_session)

    enriched_rows: list[dict] = []
    for transaction_row in transaction_rows:
        copied_row = dict(transaction_row)
        payee_raw = str(transaction_row.get("payee") or "")
        suggestion = classify_payee_for_statement_line(
            payee_raw,
            payee_normalized_key_to_account_number=mapping_dictionary,
            active_chart_account_rows=active_chart_rows,
        )
        copied_row["offset_account_number"] = suggestion.offset_account_number
        copied_row["classification_source"] = suggestion.classification_source
        enriched_rows.append(copied_row)
    return enriched_rows


def enrich_statement_transactions_with_payee_offsets_using_default_session(
    *,
    transaction_rows: list[dict],
) -> list[dict]:
    """
    Formal:  Loads mappings from moth_and_money.db and enriches transaction rows.
    Human:   Convenient for Statement Upload when no outer session is open.

    Accounting Rule:
        Read-only path except when the caller posts afterward.
    """
    with open_database_session() as database_session:
        return enrich_statement_transactions_with_payee_offsets(
            database_session,
            transaction_rows=transaction_rows,
        )


def statement_preview_rows_to_dataframe_rows(
    enriched_transaction_rows: list[dict],
    *,
    label_for_account_number: dict[int, str],
) -> list[dict]:
    """
    Formal:  Flattens enriched dicts into plain objects suitable for a pandas DataFrame.
    Human:   Feeds st.data_editor with one row per bank line.

    Accounting Rule:
        Amounts stay as Decimal until the UI stringifies for display.
    """
    flat_rows: list[dict] = []
    for enriched_row in enriched_transaction_rows:
        amount_value = enriched_row["amount"]
        if not isinstance(amount_value, Decimal):
            amount_value = Decimal(str(amount_value))
        offset_number = int(enriched_row["offset_account_number"])
        option_label = label_for_account_number.get(offset_number)
        if option_label is None:
            option_label = (
                f"{STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER} — "
                "Statement import clearing (Expense — unclassified)"
            )
        classification_source = str(enriched_row.get("classification_source") or "")
        flat_rows.append(
            {
                "posting_date_iso": str(enriched_row.get("posting_date_iso") or ""),
                "payee": str(enriched_row.get("payee") or ""),
                "amount": format(amount_value, "f"),
                "reference": str(enriched_row.get("reference") or ""),
                "offset_account_label": option_label,
                "classification_status": human_readable_classification_source(
                    classification_source
                ),
            }
        )
    return flat_rows


def merge_edited_preview_into_posting_rows(
    *,
    enriched_transaction_rows: list[dict],
    edited_preview_records: list[dict],
) -> list[dict]:
    """
    Formal:  Applies user-edited offset labels back onto transaction dicts for posting.
    Human:   Keeps amounts and payees from the parser; classification from your edits.

    Accounting Rule:
        Row count must match; misalignment raises before post.
    """
    if len(edited_preview_records) != len(enriched_transaction_rows):
        raise ValueError(
            "The classification table row count changed — re-upload the statement file "
            "and try again without adding or removing rows."
        )

    merged_rows: list[dict] = []
    for index, enriched_row in enumerate(enriched_transaction_rows):
        editor_row = edited_preview_records[index]
        merged = dict(enriched_row)
        label_text = str(editor_row.get("offset_account_label") or "").strip()
        merged["offset_account_number"] = offset_account_number_from_option_label(
            label_text
        )
        merged_rows.append(merged)
    return merged_rows
