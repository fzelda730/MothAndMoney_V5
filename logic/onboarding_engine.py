"""
MOTH AND MONEY — ONBOARDING ENGINE (BIRTH OF THE LEDGER)
/logic/onboarding_engine.py

Formal:  Single source of truth for Trial Balance intake, Chart assignment (1000s–5000s),
         balance validation, and atomic opening post to chart_of_accounts + ledger_entries.
Human:   One calm engine for “stand the ledger up” without logic leaking into Streamlit.

Human-Readable Summary:
    Trial Balance account names stay source-faithful (trim only); keyword tiers assign 1000s–5000s
    by tens; Decimal audit; one DB transaction on Commit.
"""

from __future__ import annotations

import io
from decimal import Decimal

import pandas
from sqlalchemy import text

from database.connection import open_database_session

# Keyword tiers: evaluated top-to-bottom; first substring hit wins within a tier.
# Asset (1000) is checked before Liability so names like "Chase Savings" map to 1000.
_BUCKET_KEYWORD_RULES: list[tuple[int, tuple[str, ...]]] = [
    (
        1000,
        ("savings", "altura", "checking", "bank", "relay", "cash", "fund"),
    ),
    (
        2000,
        ("card", "chase", "visa", "loan", "payable", "amex", "credit"),
    ),
    (
        3000,
        ("equity", "balance", "retained", "opening"),
    ),
    (
        4000,
        ("sales", "income", "revenue", "service"),
    ),
]

# Formal account_type (Rule 9) + normal side for chart_of_accounts.
_ACCOUNT_TYPE_AND_NORMAL: dict[int, tuple[str, str]] = {
    1000: ("Asset", "Debit"),
    2000: ("Liability", "Credit"),
    3000: ("Equity", "Credit"),
    4000: ("Revenue", "Credit"),
    5000: ("Expense", "Debit"),
}


def _parse_currency_cell_to_decimal(raw_cell_value) -> Decimal:
    """
    Formal:  Normalizes a CSV currency cell to Decimal (commas, $, tabs allowed).
    Human:   Spreadsheet exports stop breaking the forge.

    Accounting Rule:
        Money math stays in Decimal end-to-end before SQL NUMERIC bind.
    """
    if pandas.isna(raw_cell_value) or str(raw_cell_value).strip() == "":
        return Decimal("0.00")
    clean_text = (
        str(raw_cell_value)
        .replace("\t", "")
        .replace("$", "")
        .replace(",", "")
        .strip()
    )
    return Decimal(clean_text)


def _classify_bucket_base(cleaned_account_name: str) -> int:
    """
    Formal:  Maps account label to 1000 / 2000 / 3000 / 4000 / 5000 using strict
             keyword priority: Asset, then Liability, Equity, Revenue, else Expense.
    Human:   "Savings" and bank-style names hit 1000 before anything else.

    Accounting Rule:
        Matching is case-insensitive. Unmatched rows default to 5000 Expense.
    """
    lowered_account_label = cleaned_account_name.lower()
    for bucket_base, keywords in _BUCKET_KEYWORD_RULES:
        if any(keyword in lowered_account_label for keyword in keywords):
            return bucket_base
    return 5000


def _normalized_column_lookup(raw_dataframe: pandas.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for column_name in raw_dataframe.columns:
        key = str(column_name).strip().lower()
        if key in ("full name", "full_name"):
            lookup["full_name"] = column_name
        elif key in ("account name", "account_name"):
            lookup["account_name"] = column_name
        elif key == "debit":
            lookup["debit"] = column_name
        elif key == "credit":
            lookup["credit"] = column_name
    return lookup


def _extract_posting_rows(raw_dataframe: pandas.DataFrame) -> pandas.DataFrame:
    column_lookup = _normalized_column_lookup(raw_dataframe)
    if "debit" not in column_lookup or "credit" not in column_lookup:
        raise ValueError(
            "This CSV needs Debit and Credit columns. Check headers and try again."
        )
    if "full_name" in column_lookup:
        label_col = column_lookup["full_name"]
    elif "account_name" in column_lookup:
        label_col = column_lookup["account_name"]
    else:
        raise ValueError(
            "This CSV needs a Full name or Account Name column for each row."
        )

    slice_frame = raw_dataframe[
        [label_col, column_lookup["debit"], column_lookup["credit"]]
    ].copy()
    slice_frame.columns = ["source_label", "debit_cell", "credit_cell"]
    slice_frame["source_order"] = range(len(slice_frame))

    def should_drop(row) -> bool:
        label = (
            str(row["source_label"]).strip()
            if pandas.notna(row["source_label"])
            else ""
        )
        if label.upper() == "TOTAL":
            return True
        low = label.lower()
        if "cash basis" in low and "gmt" in low:
            return True
        d = _parse_currency_cell_to_decimal(row["debit_cell"])
        c = _parse_currency_cell_to_decimal(row["credit_cell"])
        if label == "" and d == Decimal("0.00") and c == Decimal("0.00"):
            return True
        return False

    return slice_frame.loc[~slice_frame.apply(should_drop, axis=1)].copy()


def _read_has_header_row_usable(dataframe: pandas.DataFrame) -> bool:
    names = {str(c).strip().lower() for c in dataframe.columns}
    if "debit" not in names or "credit" not in names:
        return False
    return "full name" in names or "account name" in names


def _scan_header_row_index(raw_matrix: pandas.DataFrame) -> int | None:
    max_rows = min(40, len(raw_matrix))
    max_cols = min(12, raw_matrix.shape[1])
    for row_index in range(max_rows):
        cells = []
        for col_index in range(max_cols):
            cell = raw_matrix.iloc[row_index, col_index]
            cells.append(str(cell).strip().lower() if pandas.notna(cell) else "")
        if "full name" in cells and "debit" in cells and "credit" in cells:
            return row_index
    return None


class OnboardingEngine:
    """
    Formal:  Encapsulates Trial Balance → Chart proposal → balance check → DB birth.
    Human:   The resale-ready onboarding spine; UI only renders and collects clicks.
    """

    @staticmethod
    def read_trial_balance_csv_bytes(csv_bytes: bytes) -> pandas.DataFrame:
        """
        Formal:  Parses bytes to a DataFrame with account labels and Debit/Credit;
                 detects QuickBooks-style preamble when row 1 is not the real header.
        Human:   Drag the export in once; the engine finds the header row for you.

        Accounting Rule:
            Structural parsing only — no rounding or classification here.
        """
        buffer = io.BytesIO(csv_bytes)
        first_try = pandas.read_csv(buffer)
        if _read_has_header_row_usable(first_try):
            return first_try

        buffer.seek(0)
        raw_matrix = pandas.read_csv(buffer, header=None)
        header_idx = _scan_header_row_index(raw_matrix)
        if header_idx is None:
            raise ValueError(
                "Could not find Full name + Debit + Credit (or row-1 Account Name). "
                "Fix the export and try again."
            )

        header_cells = raw_matrix.iloc[header_idx].tolist()
        new_columns: list[str] = []
        for idx, cell in enumerate(header_cells):
            if idx >= raw_matrix.shape[1]:
                break
            if pandas.isna(cell) or str(cell).strip() == "":
                new_columns.append(f"_unnamed_{idx}")
            else:
                new_columns.append(str(cell).strip())

        body = raw_matrix.iloc[header_idx + 1 :].copy()
        body.columns = new_columns[: body.shape[1]]
        return body.reset_index(drop=True)

    def prepare_proposal(self, source_dataframe: pandas.DataFrame) -> list[dict]:
        """
        Formal:  Builds a proposal list: account_number, account_name, account_type
                 (Asset | Liability | Equity | Revenue | Expense), debit, credit as Decimal.
        Human:   This list feeds the Review grid before Establish Ledger.

        Accounting Rule:
            account_name is the Trial Balance cell text with outer strip only — no stripping
            of embedded codes or punctuation. Numbers advance by 10 within each thousand
            bucket in stable file order. Bucket keywords are matched case-insensitively on
            the full account_name in strict tier order: Asset, Liability, Equity, Revenue;
            otherwise Expense (5000).
        """
        working = _extract_posting_rows(source_dataframe)
        next_by_bucket = {1000: 1000, 2000: 2000, 3000: 3000, 4000: 4000, 5000: 5000}

        proposal_list: list[dict] = []
        for _, row in working.sort_values("source_order").iterrows():
            raw_label = row["source_label"]
            account_name = (
                ""
                if pandas.isna(raw_label)
                else str(raw_label).strip()
            )

            bucket = _classify_bucket_base(account_name.lower())
            account_number = next_by_bucket[bucket]
            next_by_bucket[bucket] = account_number + 10

            account_type, _normal = _ACCOUNT_TYPE_AND_NORMAL[bucket]
            debit_amt = _parse_currency_cell_to_decimal(row["debit_cell"])
            credit_amt = _parse_currency_cell_to_decimal(row["credit_cell"])

            proposal_list.append(
                {
                    "account_number": int(account_number),
                    "account_name": account_name,
                    "account_type": account_type,
                    "debit": debit_amt,
                    "credit": credit_amt,
                }
            )

        return proposal_list

    @staticmethod
    def validate_balances(proposal_list: list[dict]) -> bool:
        """
        Formal:  Returns True only when sum(debit) == sum(credit) exactly in Decimal.
        Human:   Establish Ledger stays off until this is True.

        Accounting Rule:
            Double-entry opening entry requires balanced column totals.
        """
        total_debits, total_credits, _difference = (
            OnboardingEngine.posting_balance_audit(proposal_list)
        )
        return total_debits == total_credits

    @staticmethod
    def posting_balance_audit(
        proposal_list: list[dict],
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Formal:  Returns (total_debits, total_credits, difference) using Decimal sums.
        Human:   The Review footer reads these without recomputing money in the UI layer.

        Accounting Rule:
            difference = total_debits minus total_credits; balanced when difference is zero.
        """
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        for row in proposal_list:
            total_debit += row["debit"]
            total_credit += row["credit"]
        difference = total_debit - total_credit
        return total_debit, total_credit, difference

    @staticmethod
    def proposal_to_editor_dataframe(proposal_list: list[dict]) -> pandas.DataFrame:
        """
        Formal:  Shapes proposal rows for st.data_editor (numeric columns as float).
        Human:   Keeps Streamlit display out of classification math.
        """
        rows = []
        for item in proposal_list:
            rows.append(
                {
                    "account_number": int(item["account_number"]),
                    "account_name": item["account_name"],
                    "account_type": item["account_type"],
                    "debit": float(item["debit"]),
                    "credit": float(item["credit"]),
                }
            )
        return pandas.DataFrame(rows)

    @staticmethod
    def editor_dataframe_to_proposal(editor_dataframe: pandas.DataFrame) -> list[dict]:
        """
        Formal:  Rehydrates Decimal debits/credits after human edits in the grid.
        """
        out: list[dict] = []
        for _, row in editor_dataframe.iterrows():
            out.append(
                {
                    "account_number": int(row["account_number"]),
                    "account_name": str(row["account_name"]).strip(),
                    "account_type": str(row["account_type"]).strip(),
                    "debit": Decimal(str(row["debit"])).quantize(Decimal("0.01")),
                    "credit": Decimal(str(row["credit"])).quantize(Decimal("0.01")),
                }
            )
        return out

    def commit_to_database(
        self,
        proposal_list: list[dict],
        *,
        opening_balance_date_iso: str,
        source_metadata: str,
    ) -> tuple[int, int]:
        """
        Formal:  One SQLAlchemy session transaction: chart upsert, journal header,
                 ledger lines; rolls back on any failure.
        Human:   Establish Ledger runs this after you accept the Review grid.

        Accounting Rule:
            Rule 5 — source_metadata anchors the opening journal to the import filename.
        """
        if not self.validate_balances(proposal_list):
            td = sum((r["debit"] for r in proposal_list), Decimal("0.00"))
            tc = sum((r["credit"] for r in proposal_list), Decimal("0.00"))
            raise ValueError(
                f"Cannot commit: debits ({td}) and credits ({tc}) must match exactly."
            )

        account_numbers = [int(row["account_number"]) for row in proposal_list]
        if len(account_numbers) != len(set(account_numbers)):
            raise ValueError("Duplicate account_number in proposal — fix the grid first.")

        chart_rows = []
        for row in proposal_list:
            account_type = row["account_type"]
            if account_type in ("Asset", "Expense"):
                normal_balance = "Debit"
            else:
                normal_balance = "Credit"

            chart_rows.append(
                {
                    "account_number": int(row["account_number"]),
                    "account_name": row["account_name"],
                    "account_category": account_type,
                    "normal_balance": normal_balance,
                    "account_description": None,
                    "is_active": 1,
                }
            )

        insert_chart = text("""
            INSERT OR REPLACE INTO chart_of_accounts
                (account_number, account_name, account_category,
                 normal_balance, account_description, is_active)
            VALUES
                (:account_number, :account_name, :account_category,
                 :normal_balance, :account_description, :is_active)
        """)

        insert_journal = text("""
            INSERT INTO journal_entries
                (entry_date, entry_description, source_metadata)
            VALUES
                (:entry_date, :entry_description, :source_metadata)
        """)

        insert_ledger = text("""
            INSERT INTO ledger_entries
                (journal_entry_id, account_number, debit_amount, credit_amount, payee, reference)
            VALUES
                (:journal_entry_id, :account_number, :debit_amount, :credit_amount, :payee, :reference)
        """)

        check_duplicate = text("""
            SELECT journal_entry_id FROM journal_entries
            WHERE source_metadata = :source_metadata
            LIMIT 1
        """)

        ledger_payload = []
        for row in proposal_list:
            ledger_payload.append(
                {
                    "account_number": int(row["account_number"]),
                    "debit_amount": str(row["debit"]),
                    "credit_amount": str(row["credit"]),
                    "payee": "",
                    "reference": "",
                }
            )

        opening_description = "Opening Balance: Onboarding Establish Ledger"

        with open_database_session() as session:
            dup = session.execute(
                check_duplicate, {"source_metadata": source_metadata}
            ).fetchone()
            if dup:
                raise ValueError(
                    "This filename was already posted. Reset the database or rename the file."
                )

            session.execute(insert_chart, chart_rows)

            journal_result = session.execute(
                insert_journal,
                {
                    "entry_date": opening_balance_date_iso,
                    "entry_description": opening_description,
                    "source_metadata": source_metadata,
                },
            )
            journal_entry_id = journal_result.lastrowid

            for line in ledger_payload:
                line["journal_entry_id"] = journal_entry_id

            session.execute(insert_ledger, ledger_payload)

        return len(chart_rows), len(ledger_payload)
