# Plan: Two-line register manuals (today’s work)

This document summarizes what we intend to do next: change how **manual register** entries are stored so every posting has **two rows** in the `transactions` table (true double-entry legs), keep **one source of truth** for all reports, and reset the database if that is faster than migrating old data.

---

## Why we are doing this

### The problem

Today, when you enter a **manual line on a bank or card register**, the application saves **one** row in `transactions`. That row is classified to the **offset** chart account you pick (for example, an expense or income line). The **cash / bank** chart line linked to that register (the **Ledger COA**) does **not** get its own row for the same event.

That is enough for the **register (subledger)** balance, but it is **not** a complete picture when you run **COA-based** reports (for example **Activity** filtered to the cash account): the manual does not appear as a second leg on the Ledger account. **Journal entries** are different—they already create **one row per line**, so both chart accounts can show up.

For **audit** and for **consistency** across **Trial Balance, P&amp;L, Balance Sheet, General Ledger, and Activity**, we want every leg of the entry to exist as real rows in `transactions` so **all** those reports read the same underlying data.

### The direction we chose (long-term / production)

We will **store two `transactions` rows** for each register manual (not a “fake” second line only on the Activity screen). Both rows live in the same table the rest of the app already uses, so reports stay aligned.

We are **not** choosing the lighter “synthetic second line only in Activity” path for production, because it would leave **General Ledger** and other reports out of sync unless we duplicated that logic everywhere.

---

## What we will implement (plain English)

1. **On save** of a register manual, create **two** `transactions` rows that balance each other:
   - **Row 1:** the **offset** account (expense, income, etc.)—same idea as today’s single line.
   - **Row 2:** the **Ledger (cash) chart line** linked to that register (`bank_accounts.ledger_coa_id`), with the **opposite** debit and credit so the pair balances.
2. **Link the pair** with a shared identifier (for example `posting_group_id` and the same `date`, `bank_account_id`, and `source`), so updates and deletes always treat them as **one** business event.
3. **Update register balance and views** (including `v_account_balances` and any logic that assumed “one line per manual”) so the **bank / register total** is still **correct** and we do **not** double-count or drop activity when two rows exist.
4. **Regression checks** for **opening balances**, **trial balance import**, and **`trial_balance_opening`**-style behavior so we do not double-count the same money.

---

## Data reset strategy (no production users)

There are **no real users** on this data yet, and re-importing / re-entering is acceptable. So we can **drop or recreate the database** after the code is ready, instead of writing a long **migration** that backfills a second row for every old single-line manual.

- **Before** any destructive step: take a **pgAdmin backup** (Custom format) of `moth_and_money` to a path you control, in case you want that snapshot later.
- **Code rollback:** the last known-good state is on **GitHub** (`main`); you can check out that commit or use a **git tag** if you create one, if the new model does not work out.

---

## Safety net

| Layer | What to rely on |
|--------|-----------------|
| **Code** | Commits on GitHub (e.g. current `main`); optional **git tag** on the pre-change commit (e.g. `pre-twin-line-ledger`) |
| **Database** | pgAdmin (or `pg_dump`) **backup file** of the current DB before you nuke or replace it |

---

## Smoke checklist (after the change, before lots of re-entry)

Quick checks to confirm the new model is not obviously broken:

1. Post **one** register manual on an account that has a **Ledger COA** set.
2. Confirm **two** rows exist in `transactions` for that event, with matching group/date and opposite debit/credit.
3. **Register / bank balance** still looks reasonable for that book.
4. **Activity** and **General Ledger** for **both** chart lines (offset + Ledger) show the paired lines in a way you can explain to an auditor.
5. **Trial balance / period** at a high level: no wild imbalance introduced by a single test entry.

---

## Open implementation notes (for whoever codes this)

- **Edit/delete** of a manual must update or remove **both** rows together.
- Registers **without** a `ledger_coa_id` need a defined rule (block save, or single-line only, or require setup first).
- Re-read [insert_manual_register_transaction](app/db/queries.py) and [v_account_balances](app/db/schema.sql) after the two-row design is fixed.

---

## Implementation checklist (for the agent / builder)

This section is what a coding agent (or a developer) needs in addition to the “why” above: **where to change code**, **invariants**, and **acceptance**. It does not replace reading the current implementation.

### A. Business rules (non-negotiable)

1. **Every register manual** with a valid `bank_accounts.ledger_coa_id` becomes **two** `transactions` rows on the **same** `bank_account_id`, same `date`, same `source` = `manual_register` (unless you add a new enum value for the mirror leg—decide in section B), **opposite** debit/credit, **balanced** as a pair.
2. **Pairing:** set the same `posting_group_id` (new UUID) on **both** rows, following the same pattern as [insert_journal_entry](app/db/queries.py) (journal already uses a shared `posting_group_id`).
3. **Row 1 (offset):** `coa_id` = the account the user picked (expense, etc.)—**must** remain `!= ledger_coa_id` (the existing validation intent stays).
4. **Row 2 (ledger leg):** `coa_id` = `ba.ledger_coa_id` for that register, amounts the **opposite** of row 1 so debits and credits match in double-entry.
5. **If `ledger_coa_id` is null:** do not create a second row; **return a clear error** (or require ledger setup) so the app never half-posts. Product choice: no silent single-line in production.
6. **No duplicate economics** in **opening** / **trial balance** / **GL** for the same event (re-read `trial_balance_opening` and TE paths after implementation).

### B. Decisions to make explicitly in code (do not leave implicit)

- **Return value:** [save_register_transaction_to_db](app/data/providers.py) and [insert_manual_register_transaction](app/db/queries.py) today return a **single** `transaction_id`. With two rows, return **`posting_group_id`** and/or the **offset** line’s id, and **document** the contract in the docstring. Update [10_New_Entry.py](app/pages/10_New_Entry.py) if the UI shows the returned id.
- **Mirror `source`:** use **`manual_register` on both** lines, *or* add a dedicated enum (e.g. `manual_register_ledger_leg`) in a new migration. Using one source on both is simpler; a second enum makes SQL filters easier—pick one and use it in Activity/GL filters if needed.
- **Description / payee:** same payee on both, or mark the ledger leg in `description` (e.g. prefix `Ledger leg —`) for audit PDFs. Keep payee short and consistent for bank-style lists.

### C. Files to open first (in order)

| Order | File | Why |
|-------|------|-----|
| 1 | [app/db/queries.py](app/db/queries.py) — `insert_manual_register_transaction` | Core insert: extend to `execute_values` or two `INSERT`s in one transaction; generate `posting_group_id` once. |
| 2 | [app/data/providers.py](app/data/providers.py) — `save_register_transaction_to_db` | Thin wrapper: adjust return type/semantics. |
| 3 | [app/pages/10_New_Entry.py](app/pages/10_New_Entry.py) | User flow that calls `save_register_transaction_to_db`; handle new return value / errors. |
| 4 | [app/db/schema.sql](app/db/schema.sql) — `v_account_balances` | The view **excludes** rows where `t.coa_id` equals `ledger_coa_id` (except `trial_balance_opening`). The **new** mirror row will likely use `coa_id = ledger_coa_id` → it may be **excluded** from the register’s debit/credit roll-up. **Verify** the intended behavior: (a) register total still comes from the **offset** line only, and the ledger line is for **GL/Activity**; or (b) change the view if both rows must affect the subledger. **This is a required design check.** |
| 5 | [app/db/migrations/](app/db/migrations/) | New migration if you add an enum for `source`, or a column for “pair type”; otherwise schema may be unchanged. |
| 6 | Grep: `insert_manual_register`, `delete.*transaction`, `update.*transaction` for register | Any path that **edits** or **deletes** a manual must load **by `posting_group_id`** and touch **both** rows. If delete does not exist yet, document “delete not supported for paired manuals” or implement paired delete. |

### D. Downstream read paths (regression)

After inserts work, run reports with **small** data and confirm numbers:

- [fetch_coa_activity_report](app/db/queries.py) / [merge_coa_activity_with_opening](app/db/queries.py) and Activity UI in [7_Reports.py](app/pages/7_Reports.py) — both COAs should list the pair.
- [fetch_general_ledger_detail](app/db/queries.py) — same.
- [fetch_coa_beginning_balances](app/db/queries.py) — no double count with TE + pre-period.
- [v_account_balances](app/db/schema.sql) — **Dashboard** register totals still correct per section C.4.
- **Demo / sample** mode: [providers](app/data/providers.py) `use_sample_data()` paths—ensure no crash if they still return single-line stubs.

### E. No migration of old one-line data (per product choice)

- User may **wipe** DB and re-apply [schema](app/db/schema.sql) + migrations, then re-import. If so, the agent does **not** need a one-time `UPDATE` to backfill historical manual rows, unless the user changes their mind.
- If backfill is later required, it is a **separate** task: for each `manual_register` with no sibling row, insert mirror with same `date`, `bank_account_id`, `posting_group_id` (new or derived), and opposite amounts.

### F. Out of scope unless requested

- Changing **import** (CSV) to two lines per row—**not** part of this plan unless the user says so.
- **Synthetic-only** Activity lines—**rejected** for this build (see “direction we chose” above).

---

## Document history

- Created to align the team on **“two real rows in `transactions` + optional DB nuke for dev + backup + git rollback.”**
- Added **Implementation checklist (for the agent / builder)** with file paths, invariants, `v_account_balances` warning, and regression list.
