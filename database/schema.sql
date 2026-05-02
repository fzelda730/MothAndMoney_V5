-- =============================================================================
-- MOTH AND MONEY — GENERAL LEDGER SCHEMA
-- /database/schema.sql
--
-- Formal:  Defines the three-table double-entry bookkeeping structure that
--          underpins every financial report in the moth_and_money.db ledger.
-- Human:   The Map (accounts), the Events (journal), and the Truth (ledger).
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- TABLE 1: CHART OF ACCOUNTS  ("The Map")
-- Every account that money can ever flow through lives here first.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chart_of_accounts (
    account_number      INTEGER PRIMARY KEY,       -- 1000s=Assets, 2000s=Liabilities,
                                                   -- 3000s=Equity, 4000s=Revenue, 5000s=Expenses
    account_name        TEXT    NOT NULL,           -- e.g., "Relay Business Checking"
    account_category    TEXT    NOT NULL,           -- Asset | Liability | Equity | Revenue | Expense
    normal_balance      TEXT    NOT NULL,           -- Debit | Credit
    account_description TEXT,                      -- Human: "What is this bucket for?"
    is_active           INTEGER NOT NULL DEFAULT 1 -- 1 = open for business, 0 = retired
);

-- -----------------------------------------------------------------------------
-- TABLE 2: JOURNAL ENTRIES  ("The Events")
-- One row per financial event (e.g., "Paid SBA loan on 2026-03-01").
-- source_metadata anchors every entry to its original document for audit.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS journal_entries (
    journal_entry_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date          TEXT    NOT NULL,           -- ISO format: YYYY-MM-DD
    entry_description   TEXT    NOT NULL,           -- Human: "What happened?"
    source_metadata     TEXT    NOT NULL,           -- Audit trail: original filename or import source
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- -----------------------------------------------------------------------------
-- TABLE 3: LEDGER ENTRIES  ("The Truth")
-- One row per account line within a journal entry.
-- A balanced journal entry means: SUM(debit_amount) = SUM(credit_amount).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ledger_entries (
    ledger_entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_entry_id    INTEGER NOT NULL
                            REFERENCES journal_entries(journal_entry_id)
                            ON DELETE CASCADE,      -- Remove lines if the parent event is deleted.
    account_number      INTEGER NOT NULL
                            REFERENCES chart_of_accounts(account_number),
    debit_amount        NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    credit_amount       NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    payee               TEXT    NOT NULL DEFAULT '',   -- Counterparty / description at line level
    reference           TEXT    NOT NULL DEFAULT '',   -- Bank memo, check number, or transaction id

    -- Audit Integrity: a line cannot carry both a debit and a credit simultaneously.
    CONSTRAINT one_side_only CHECK (
        NOT (debit_amount > 0 AND credit_amount > 0)
    )
    -- Opening Trial Balance may include explicit zero / zero lines so every CSV
    -- row has a ledger line matching the chart row (solopreneur TB parity).
);

-- -----------------------------------------------------------------------------
-- TABLE 4: BANK TEMPLATES — CSV column maps + built-in ingest registry
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bank_templates (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT    NOT NULL UNIQUE,
    linked_account_number   INTEGER
                                REFERENCES chart_of_accounts(account_number),
    date_col                TEXT    NOT NULL DEFAULT '',
    payee_col               TEXT    NOT NULL DEFAULT '',
    amount_col              TEXT    NOT NULL DEFAULT '',
    reference_col           TEXT    NOT NULL DEFAULT '',
    is_liability            INTEGER NOT NULL DEFAULT 0
                                CHECK (is_liability IN (0, 1)),
    ingest_kind             TEXT    NOT NULL DEFAULT 'csv_headers'
                                CHECK (ingest_kind IN ('csv_headers', 'built_in_pdf')),
    built_in_parser_key     TEXT,
    created_at              TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bank_templates_ingest_kind
    ON bank_templates (ingest_kind);

-- -----------------------------------------------------------------------------
-- TABLE 5: BANK TEMPLATE CHART LINKS — optional short list for Statement Upload
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bank_template_chart_links (
    bank_template_id    INTEGER NOT NULL
                            REFERENCES bank_templates(id)
                            ON DELETE CASCADE,
    account_number      INTEGER NOT NULL
                            REFERENCES chart_of_accounts(account_number),
    PRIMARY KEY (bank_template_id, account_number)
);

CREATE INDEX IF NOT EXISTS idx_bank_template_chart_links_template
    ON bank_template_chart_links (bank_template_id);

-- -----------------------------------------------------------------------------
-- TABLE 6: PAYEE CHART ACCOUNT MAPPINGS — remembered offset accounts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payee_chart_account_mappings (
    payee_normalized_key    TEXT    NOT NULL,
    account_number          INTEGER NOT NULL
                                REFERENCES chart_of_accounts(account_number),
    created_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (payee_normalized_key)
);

CREATE INDEX IF NOT EXISTS idx_payee_chart_account_mappings_account
    ON payee_chart_account_mappings (account_number);
