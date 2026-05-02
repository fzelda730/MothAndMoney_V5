# Trial Balance CSV — Supported formats (design note)

This document records how **Moth and Money** intends to accept Trial Balance CSV files for **System Initialization** (opening import), including **QuickBooks-style** exports and the **CMF template** layout.

Implementation may lag this spec; see `logic/opening_trial_balance_import.py` for current behavior.

## Format A — CMF template (explicit account columns)

**Required column names** (exact, after trim):

- `Account Number`
- `Account Name`
- `Debit`
- `Credit`

**Layout:** Header row is row 1 of the file (no preamble). Standard CSV.

## Format B — “Full name” export (e.g. QuickBooks Trial Balance to CSV)

Many exports include **preamble** lines (company name, report title, as-of date) **before** the real column headers.

**Detection rule:** Scan the file until we find a **header row** that defines:

- **Full name** — the account label (may combine number and name, or be a hierarchical path such as `Owners Draw:Utilities- SCE`).
- **Debit**
- **Credit**

Matching should be **case-insensitive** on labels (after strip), so minor casing differences still work.

**Data:** Every row **after** that header row is a trial balance line, subject to **footer hygiene** (below).

This is **not** QuickBooks-only: **any** CSV that uses this same three-column header pattern can follow Format B.

## Rows to exclude (Format B)

- **TOTAL** row (label equals `TOTAL`, case-insensitive).
- Rows where the account label is empty and both Debit and Credit are empty (blank / spacer lines).
- Typical **QuickBooks footer** lines (e.g. long timestamp text containing `Cash Basis` / `GMT`), so they are not treated as accounts.

## Account number and account name (Format B)

The database requires an integer **`account_number`** and **`account_name`** on `chart_of_accounts`.

- If **Full name** matches a leading number pattern such as **`4199 - Relay`** (digits, optional spaces, hyphen, remainder), then:
  - **`Account Number`** = leading integer (e.g. `4199`).
  - **`Account Name`** can retain the full **Full name** string for fidelity to the export, or the portion after the hyphen—product choice at implementation time.
- If there is **no** leading number (most plain QuickBooks names), assign a **placeholder** account number in a reserved high range (e.g. **`900001`** incrementing per row) so posting stays valid. The user should treat these as **temporary** until aligned with a formal Chart of Accounts for tax and reporting.

## Balance and posting

- **Debit** and **Credit** cells use the same currency parsing as the rest of the ledger (`Decimal`, commas, blanks).
- Defensive stripping of **`$`** on amounts may be applied where exports include it.
- **Opening import** posts **one ledger line per CSV data row**, including explicit **zero / zero** lines, so every imported line has a matching chart row and ledger line (see schema and `logic/initial_funding.py`).

## Reference sample

- [Samples/CMF_Trial Balance_12312026.csv](../Samples/CMF_Trial%20Balance_12312026.csv) — QuickBooks-style preamble, header row `Full name,Debit,Credit`, `TOTAL` and footer after data.

## Error messaging

If no header row matches either format, the app should raise a **human-readable** error that mentions:

- Preamble + **`Full name` / `Debit` / `Credit`**, **or**
- The CMF template with **`Account Number`** and **`Account Name`**.
