"""
MOTH AND MONEY — GENERAL LEDGER (UI)
/ui/general_ledger.py

Formal:  Renders the General Ledger — chart band, period dates, per-account opening,
         detail lines, running balance, and ending.
Human:   Your map + your postings in one scroll, scoped the way you and your CPA expect.

Accounting Rule:
    UI only; balances and running totals are delegated to logic and SQL repositories.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas
import streamlit as st

from database.connection import open_database_session
from database.general_ledger_repository import (
    fetch_active_account_number_bounds,
    fetch_chart_accounts_in_number_band,
    fetch_journal_entry_date_iso_bounds,
    fetch_opening_net_debit_minus_credit_by_account,
    fetch_period_ledger_line_rows_for_general_ledger,
)
from logic.currency_presentation import format_currency_standard_us
from logic.general_ledger_report import (
    GeneralLedgerAccountSection,
    account_numbers_with_period_motion_or_nonzero_opening,
    build_general_ledger_account_sections,
    normalize_account_number_band,
)


def _general_ledger_money_or_dash(ledger_amount: Decimal, zero_as_empty: bool = False) -> str:
    """
    Formal:  Formats a Decimal for a GL grid cell; optional blank when zero.
    Human:   Keeps wide grids readable when many cells are empty.

    Accounting Rule:
        Display only.
    """
    if zero_as_empty and ledger_amount == Decimal("0"):
        return ""
    return format_currency_standard_us(ledger_amount)


def _general_ledger_detail_dataframe(section: GeneralLedgerAccountSection) -> pandas.DataFrame:
    """
    Formal:  Builds a pandas grid from one account section's detail rows.
    Human:   Feeds st.dataframe with human column titles.

    Accounting Rule:
        Running total is algebraic net (debit − credit).
    """
    table_rows: list[dict[str, str | int]] = []
    for detail_row in section.detail_rows:
        table_rows.append(
            {
                "Date": detail_row.entry_date_iso,
                "Journal": detail_row.journal_entry_id,
                "Description": detail_row.entry_description,
                "Payee": detail_row.payee,
                "Reference": detail_row.reference,
                "Source": detail_row.source_metadata,
                "Debit": _general_ledger_money_or_dash(
                    detail_row.debit_amount, zero_as_empty=True
                ),
                "Credit": _general_ledger_money_or_dash(
                    detail_row.credit_amount, zero_as_empty=True
                ),
                "Running (Dr − Cr)": format_currency_standard_us(
                    detail_row.running_net_debit_minus_credit
                ),
            }
        )
    return pandas.DataFrame(table_rows)


def render_general_ledger_page() -> None:
    """
    Formal:  General Ledger report page — filters, fan-out sections, formatted grids.
    Human:   Pick dates and accounts; read opening, every line, and ending in one place.

    Accounting Rule:
        Beginning = journals before the first day; activity = inclusive through the last day.
    """
    st.title("General Ledger")
    st.caption(
        "Formal: Ledger detail by chart band and date window. "
        "Human: Beginning is everything before your start date; each line shows the running net "
        "(debit − credit)."
    )

    with open_database_session() as database_session:
        band_low_optional, band_high_optional = fetch_active_account_number_bounds(
            database_session
        )
        earliest_journal_iso, latest_journal_iso = fetch_journal_entry_date_iso_bounds(
            database_session
        )

    if band_low_optional is None or band_high_optional is None:
        st.info(
            "Add at least one active account under Onboarding before running the General Ledger."
        )
        return

    today_reference = date.today()
    if earliest_journal_iso is not None and latest_journal_iso is not None:
        earliest_journal_date = date.fromisoformat(earliest_journal_iso)
        latest_journal_date = date.fromisoformat(latest_journal_iso)
        default_start = earliest_journal_date
        default_end = max(today_reference, latest_journal_date)
    else:
        default_start = date(today_reference.year, today_reference.month, 1)
        default_end = today_reference

    date_column_left, date_column_right = st.columns(2)
    with date_column_left:
        period_start_date = st.date_input(
            "Period start (inclusive)",
            value=default_start,
            key="general_ledger_period_start_date",
        )
    with date_column_right:
        period_end_date = st.date_input(
            "Period end (inclusive)",
            value=default_end,
            key="general_ledger_period_end_date",
        )

    st.caption(
        "Detail lines only include postings whose **journal** `entry_date` falls inside this window. "
        "Anything dated **before** Period start appears only in Beginning balance — widen the start "
        "date to include your statement month if tables look empty."
    )

    if period_start_date > period_end_date:
        st.error(
            "Period start must be on or before period end — swap your dates and rerun the report."
        )
        return

    period_start_inclusive_iso = period_start_date.isoformat()
    period_end_inclusive_iso = period_end_date.isoformat()
    period_start_exclusive_iso = period_start_inclusive_iso

    scope_all_accounts = st.checkbox(
        "All accounts (active chart — use min and max account numbers automatically)",
        value=False,
        key="general_ledger_scope_all_accounts",
        help=(
            "Formal: band = MIN/MAX active account_number. Human: Skip typing from/to when "
            "you want the whole map."
        ),
    )

    account_number_from_input = band_low_optional
    account_number_to_input = band_high_optional
    if not scope_all_accounts:
        number_column_left, number_column_right = st.columns(2)
        with number_column_left:
            account_number_from_input = st.number_input(
                "From account number (inclusive)",
                min_value=1,
                max_value=999999,
                value=int(band_low_optional),
                step=1,
                key="general_ledger_from_account_number",
            )
        with number_column_right:
            account_number_to_input = st.number_input(
                "To account number (inclusive)",
                min_value=1,
                max_value=999999,
                value=int(band_high_optional),
                step=1,
                key="general_ledger_to_account_number",
            )
        if account_number_from_input != account_number_to_input:
            st.caption(
                "Every **active** chart account in this band is listed — even with no postings "
                "in the period."
            )

    only_accounts_with_motion = False
    if scope_all_accounts:
        only_accounts_with_motion = st.checkbox(
            "Only show accounts with period activity or a non-zero beginning balance",
            value=False,
            key="general_ledger_only_motion_or_opening",
            help=(
                "Formal: Filters to accounts with lines in the window or opening ≠ 0. "
                "Human: Shrinks the book when you picked “All accounts.” "
                "When you type a from/to range, every account in the band always appears."
            ),
        )

    if scope_all_accounts:
        resolved_low = int(band_low_optional)
        resolved_high = int(band_high_optional)
    else:
        resolved_low, resolved_high = normalize_account_number_band(
            int(account_number_from_input),
            int(account_number_to_input),
        )

    st.divider()

    with open_database_session() as database_session:
        chart_account_rows = fetch_chart_accounts_in_number_band(
            database_session,
            account_number_low=resolved_low,
            account_number_high=resolved_high,
        )
        opening_net_by_account_number = (
            fetch_opening_net_debit_minus_credit_by_account(
                database_session,
                account_number_low=resolved_low,
                account_number_high=resolved_high,
                period_start_exclusive_iso=period_start_exclusive_iso,
            )
        )
        period_ledger_line_rows = fetch_period_ledger_line_rows_for_general_ledger(
            database_session,
            account_number_low=resolved_low,
            account_number_high=resolved_high,
            period_start_inclusive_iso=period_start_inclusive_iso,
            period_end_inclusive_iso=period_end_inclusive_iso,
        )

    if scope_all_accounts and only_accounts_with_motion:
        chart_account_numbers_in_order = [
            int(chart_row["account_number"]) for chart_row in chart_account_rows
        ]
        keep_account_numbers = account_numbers_with_period_motion_or_nonzero_opening(
            chart_account_numbers_in_order=chart_account_numbers_in_order,
            opening_net_by_account=opening_net_by_account_number,
            period_line_rows=period_ledger_line_rows,
        )
        chart_account_rows = [
            chart_row
            for chart_row in chart_account_rows
            if int(chart_row["account_number"]) in keep_account_numbers
        ]

    if len(chart_account_rows) == 0:
        st.warning(
            "No active accounts fall in this band for the current filters. "
            "Widen the range or adjust Onboarding."
        )
        return

    account_sections = build_general_ledger_account_sections(
        chart_account_rows=chart_account_rows,
        opening_net_by_account_number=opening_net_by_account_number,
        period_ledger_line_rows=period_ledger_line_rows,
    )

    section_count = len(account_sections)
    line_total = sum(len(section.detail_rows) for section in account_sections)
    st.info(
        f"{section_count} account(s) in scope with **{line_total}** detail line(s) "
        f"between **{period_start_inclusive_iso}** and **{period_end_inclusive_iso}**."
    )

    if line_total == 0 and earliest_journal_iso is not None:
        st.warning(
            "No lines in this date window — check **Period start**. Journals in your file run "
            f"from **{earliest_journal_iso}** through **{latest_journal_iso or earliest_journal_iso}**; "
            "beginning balances already include activity dated before Period start."
        )

    for section in account_sections:
        st.subheader(
            f"{section.account_number} — {section.account_name}"
        )
        st.caption(
            f"{section.account_category} · Normal balance: {section.normal_balance}. "
            "Running total is cumulative debit minus credit (negative is typical for "
            "credit-normal buckets)."
        )
        st.metric(
            label="Beginning balance (net Dr − Cr)",
            value=format_currency_standard_us(
                section.opening_net_debit_minus_credit
            ),
        )

        if len(section.detail_rows) == 0:
            st.markdown("*No postings in this period.*")
        else:
            st.dataframe(
                _general_ledger_detail_dataframe(section),
                width="stretch",
                hide_index=True,
                column_config={
                    "Journal": st.column_config.NumberColumn("Journal", format="%d"),
                },
            )

        st.metric(
            label="Ending balance (net Dr − Cr)",
            value=format_currency_standard_us(section.ending_net_debit_minus_credit),
        )
        st.divider()
