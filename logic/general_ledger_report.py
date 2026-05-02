"""
MOTH AND MONEY — GENERAL LEDGER REPORT (LOGIC)
/logic/general_ledger_report.py

Formal:  Resolves account bands, optional activity filter, and per-account detail with running balance.
Human:   Turns raw SQL rows into what Streamlit can print — one section per chart bucket.

Accounting Rule:
    Running balance is cumulative (debit - credit) in period, added to opening net in same basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class GeneralLedgerDetailRow:
    """
    Formal:  One printed line on the General Ledger body (not the synthetic opening row).
    Human:   Date, journal id, narrative, amounts, and running net after this line.
    """

    entry_date_iso: str
    journal_entry_id: int
    entry_description: str
    source_metadata: str
    ledger_entry_id: int
    debit_amount: Decimal
    credit_amount: Decimal
    payee: str
    reference: str
    running_net_debit_minus_credit: Decimal


@dataclass
class GeneralLedgerAccountSection:
    """
    Formal:  One chart account's opening, detail lines, and ending net for the report window.
    Human:   A complete mini-ledger for a single bucket in your map.
    """

    account_number: int
    account_name: str
    account_category: str
    normal_balance: str
    opening_net_debit_minus_credit: Decimal
    detail_rows: list[GeneralLedgerDetailRow] = field(default_factory=list)

    @property
    def ending_net_debit_minus_credit(self) -> Decimal:
        """
        Formal:  Opening net plus each line's (debit - credit); zero lines yields opening.
        Human:   The balance at the close of your selected dates.
        """
        running = self.opening_net_debit_minus_credit
        for detail_row in self.detail_rows:
            row_delta = detail_row.debit_amount - detail_row.credit_amount
            running = running + row_delta
        return running


def normalize_account_number_band(
    account_number_from: int,
    account_number_to: int,
) -> tuple[int, int]:
    """
    Formal:  Returns (low, high) with low <= high so SQL BETWEEN is well-defined.
    Human:   If you typed high first, we quietly flip so the report still runs.

    Accounting Rule:
        N/A — presentation order only.
    """
    low = int(account_number_from)
    high = int(account_number_to)
    if low <= high:
        return low, high
    return high, low


def account_numbers_with_period_motion_or_nonzero_opening(
    *,
    chart_account_numbers_in_order: list[int],
    opening_net_by_account: dict[int, Decimal],
    period_line_rows: list[dict],
) -> set[int]:
    """
    Formal:  Accounts to keep when "only with activity or opening" is selected (All accounts scope).

    Accounting Rule:
        Keep if opening net is non-zero or any ledger line exists in the period window for that account.
    """
    with_motion: set[int] = set()
    for line_row in period_line_rows:
        with_motion.add(int(line_row["account_number"]))
    result: set[int] = set()
    for account_number in chart_account_numbers_in_order:
        opening = opening_net_by_account.get(account_number, Decimal("0"))
        if opening != Decimal("0") or account_number in with_motion:
            result.add(account_number)
    return result


def build_general_ledger_account_sections(
    *,
    chart_account_rows: list[dict],
    opening_net_by_account_number: dict[int, Decimal],
    period_ledger_line_rows: list[dict],
) -> list[GeneralLedgerAccountSection]:
    """
    Formal:  Groups period lines by account and computes running net after each line.
    Human:   Produces ordered sections matching the chart order you passed in.

    Accounting Rule:
        Detail lines preserve SQL sort order within each account.
    """
    lines_by_account: dict[int, list[dict]] = {}
    for line_row in period_ledger_line_rows:
        account_number = int(line_row["account_number"])
        lines_by_account.setdefault(account_number, []).append(line_row)

    sections: list[GeneralLedgerAccountSection] = []
    for chart_row in chart_account_rows:
        account_number = int(chart_row["account_number"])
        opening_net = opening_net_by_account_number.get(account_number, Decimal("0"))
        raw_lines = lines_by_account.get(account_number, [])
        running = opening_net
        detail_rows: list[GeneralLedgerDetailRow] = []
        for line_row in raw_lines:
            debit_amount = Decimal(str(line_row["debit_amount"]))
            credit_amount = Decimal(str(line_row["credit_amount"]))
            delta = debit_amount - credit_amount
            running = running + delta
            detail_rows.append(
                GeneralLedgerDetailRow(
                    entry_date_iso=str(line_row["entry_date_iso"]),
                    journal_entry_id=int(line_row["journal_entry_id"]),
                    entry_description=str(line_row["entry_description"]),
                    source_metadata=str(line_row["source_metadata"]),
                    ledger_entry_id=int(line_row["ledger_entry_id"]),
                    debit_amount=debit_amount,
                    credit_amount=credit_amount,
                    payee=str(line_row.get("payee") or ""),
                    reference=str(line_row.get("reference") or ""),
                    running_net_debit_minus_credit=running,
                )
            )
        sections.append(
            GeneralLedgerAccountSection(
                account_number=account_number,
                account_name=str(chart_row["account_name"]),
                account_category=str(chart_row["account_category"]),
                normal_balance=str(chart_row["normal_balance"]),
                opening_net_debit_minus_credit=opening_net,
                detail_rows=detail_rows,
            )
        )
    return sections
