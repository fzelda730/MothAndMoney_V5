-- ============================================================
-- Moth and Money V4 — PostgreSQL Schema
-- Run once against a fresh database: moth_and_money
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE account_type_enum AS ENUM (
    'checking', 'savings', 'credit_card', 'cash'
);

CREATE TYPE bank_type_enum AS ENUM (
    'depository', 'credit_card'
);

CREATE TYPE template_type_enum AS ENUM (
    'bank_statement', 'credit_card'
);

CREATE TYPE transaction_source_enum AS ENUM (
    'bank_import', 'credit_card_import'
);

CREATE TYPE transaction_status_enum AS ENUM (
    'pending', 'cleared', 'flagged'
);

CREATE TYPE batch_status_enum AS ENUM (
    'processing', 'complete', 'failed'
);

CREATE TYPE trial_balance_status_enum AS ENUM (
    'pending', 'confirmed'
);

CREATE TYPE accounting_method_enum AS ENUM (
    'cash', 'accrual'
);

CREATE TYPE coa_account_type_enum AS ENUM (
    'asset', 'liability', 'equity', 'income', 'expense'
);

-- ============================================================
-- STUDIO PROFILE
-- ============================================================

CREATE TABLE studio_profile (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artist_name         VARCHAR(255) NOT NULL DEFAULT 'Your Name',
    studio_name         VARCHAR(255) NOT NULL DEFAULT 'Your Studio',
    bio                 TEXT,
    logo_url            TEXT,
    email               VARCHAR(255),
    tax_id              VARCHAR(100),
    base_currency       VARCHAR(10) NOT NULL DEFAULT 'USD',
    fiscal_year_start   VARCHAR(20) NOT NULL DEFAULT 'January',
    default_tax_rate    NUMERIC(5,2) NOT NULL DEFAULT 25.00,
    accounting_method   accounting_method_enum NOT NULL DEFAULT 'cash',
    theme_preference    VARCHAR(20) NOT NULL DEFAULT 'light',
    compact_ui          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed one profile row on first run
INSERT INTO studio_profile (artist_name, studio_name)
VALUES ('Julian Voss', 'The Digital Atelier')
ON CONFLICT DO NOTHING;

-- ============================================================
-- CHART OF ACCOUNTS
-- ============================================================

CREATE TABLE chart_of_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_number  VARCHAR(20) NOT NULL UNIQUE,
    account_name    VARCHAR(255) NOT NULL,
    account_type    coa_account_type_enum NOT NULL,
    account_subtype VARCHAR(100),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pre-seeded Creatives Chart of Accounts
INSERT INTO chart_of_accounts (account_number, account_name, account_type, account_subtype) VALUES
-- Assets (1000s)
('1100', 'Cash',                         'asset',   'current_asset'),
('1200', 'Accounts Receivable',          'asset',   'current_asset'),
('1300', 'Art Inventory',                'asset',   'inventory'),
('1400', 'Digital Assets',               'asset',   'current_asset'),
('1500', 'Prepaid Expenses',             'asset',   'current_asset'),
('1600', 'Equipment',                    'asset',   'fixed_asset'),
-- Liabilities (2000s)
('2100', 'Accounts Payable',             'liability','current_liability'),
('2200', 'Credit Card Payable',          'liability','current_liability'),
('2300', 'Tax Reserve',                  'liability','current_liability'),
('2400', 'Deferred Revenue',             'liability','current_liability'),
-- Equity (3000s)
('3100', 'Owner Equity',                 'equity',  'owners_equity'),
('3200', 'Retained Earnings',            'equity',  'retained_earnings'),
-- Income (4000s)
('4100', 'Gallery Sales (Direct)',       'income',  'operating_income'),
('4200', 'Online Atelier / Digital Shop','income',  'operating_income'),
('4300', 'Consultancy & Curatorial',     'income',  'operating_income'),
('4400', 'Commission Income',            'income',  'operating_income'),
('4500', 'Licensing & Royalties',        'income',  'operating_income'),
('4900', 'Other Income',                 'income',  'other_income'),
-- Expenses (5000s)
('5100', 'Studio Rent & Utilities',      'expense', 'overhead'),
('5200', 'Material Supplies',            'expense', 'cost_of_goods'),
('5300', 'Marketing & Exhibition Fees',  'expense', 'marketing'),
('5400', 'Professional Staff',           'expense', 'payroll'),
('5500', 'Software & Subscriptions',     'expense', 'overhead'),
('5600', 'Shipping & Logistics',         'expense', 'cost_of_goods'),
('5700', 'Travel & Dining',              'expense', 'travel'),
('5800', 'Photography & Documentation',  'expense', 'marketing'),
('5900', 'Other Expenses',               'expense', 'other_expense')
ON CONFLICT (account_number) DO NOTHING;

-- ============================================================
-- BANKS
-- ============================================================

CREATE TABLE banks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_name   VARCHAR(255) NOT NULL,
    bank_type   bank_type_enum NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- IMPORT TEMPLATES (one per bank format, shared across accounts)
-- ============================================================

CREATE TABLE import_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name   VARCHAR(255) NOT NULL,
    template_type   template_type_enum NOT NULL,
    column_map      JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- BANK ACCOUNTS (many accounts can share one template)
-- ============================================================

CREATE TABLE bank_accounts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_id                 UUID NOT NULL REFERENCES banks(id) ON DELETE RESTRICT,
    template_id             UUID REFERENCES import_templates(id) ON DELETE SET NULL,
    account_name            VARCHAR(255) NOT NULL,
    account_number_masked   VARCHAR(10) NOT NULL,
    account_type            account_type_enum NOT NULL,
    currency                VARCHAR(10) NOT NULL DEFAULT 'USD',
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- PAYEE INTELLIGENCE RULES
-- ============================================================

CREATE TABLE payee_rules (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payee_pattern       VARCHAR(500) NOT NULL,
    coa_id              UUID NOT NULL REFERENCES chart_of_accounts(id) ON DELETE RESTRICT,
    template_id         UUID REFERENCES import_templates(id) ON DELETE CASCADE,
    transaction_type    VARCHAR(10) NOT NULL DEFAULT 'debit',
    confidence          NUMERIC(4,3) NOT NULL DEFAULT 1.000,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (payee_pattern, template_id)
);

-- ============================================================
-- TRIAL BALANCE ENTRIES (Onboarding Step 1)
-- ============================================================

CREATE TABLE trial_balance_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_account_id UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE CASCADE,
    coa_id          UUID NOT NULL REFERENCES chart_of_accounts(id) ON DELETE RESTRICT,
    reference_name  VARCHAR(255) NOT NULL,
    debit_amount    NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    credit_amount   NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          trial_balance_status_enum NOT NULL DEFAULT 'pending'
);

-- ============================================================
-- IMPORT BATCHES (each file upload)
-- ============================================================

CREATE TABLE import_batches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_account_id UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE CASCADE,
    template_id     UUID NOT NULL REFERENCES import_templates(id) ON DELETE RESTRICT,
    filename        VARCHAR(500) NOT NULL,
    period_start    DATE,
    period_end      DATE,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    record_count    INTEGER NOT NULL DEFAULT 0,
    status          batch_status_enum NOT NULL DEFAULT 'processing'
);

-- ============================================================
-- TRANSACTIONS (core ledger)
-- ============================================================

CREATE TABLE transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_account_id UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE CASCADE,
    import_batch_id UUID REFERENCES import_batches(id) ON DELETE SET NULL,
    coa_id          UUID REFERENCES chart_of_accounts(id) ON DELETE SET NULL,
    date            DATE NOT NULL,
    payee           VARCHAR(500) NOT NULL,
    payee_normalized VARCHAR(500),
    debit_amount    NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    credit_amount   NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    description     TEXT,
    source          transaction_source_enum NOT NULL,
    status          transaction_status_enum NOT NULL DEFAULT 'pending',
    is_categorized  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for common query patterns
CREATE INDEX idx_transactions_bank_account ON transactions(bank_account_id);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_coa ON transactions(coa_id);
CREATE INDEX idx_transactions_categorized ON transactions(is_categorized);

-- ============================================================
-- LEDGER SUBMISSIONS (immutable period-close audit log)
-- ============================================================

CREATE TABLE ledger_submissions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_account_id     UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT,
    period_label        VARCHAR(50) NOT NULL,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    beginning_balance   NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    total_debits        NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    total_credits       NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    ending_balance      NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    notes               TEXT
);

-- ============================================================
-- HELPFUL VIEWS
-- ============================================================

-- Current account balances (for Dashboard Financial Accounts table)
CREATE OR REPLACE VIEW v_account_balances AS
SELECT
    ba.id                           AS bank_account_id,
    ba.account_name,
    ba.account_type,
    ba.account_number_masked,
    b.bank_name,
    COALESCE(ls.ending_balance, 0)  AS beginning_balance,
    COALESCE(SUM(t.debit_amount), 0)  AS total_debits,
    COALESCE(SUM(t.credit_amount), 0) AS total_credits,
    COALESCE(ls.ending_balance, 0)
        - COALESCE(SUM(t.debit_amount), 0)
        + COALESCE(SUM(t.credit_amount), 0) AS ending_balance
FROM bank_accounts ba
JOIN banks b ON ba.bank_id = b.id
LEFT JOIN (
    SELECT DISTINCT ON (bank_account_id)
        bank_account_id, ending_balance
    FROM ledger_submissions
    ORDER BY bank_account_id, submitted_at DESC
) ls ON ls.bank_account_id = ba.id
LEFT JOIN transactions t ON t.bank_account_id = ba.id
    AND t.status IN ('cleared', 'pending')
WHERE ba.is_active = TRUE
GROUP BY ba.id, ba.account_name, ba.account_type,
         ba.account_number_masked, b.bank_name, ls.ending_balance;

-- ============================================================
-- TRIGGER: auto-update updated_at on studio_profile
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_studio_profile_updated_at
    BEFORE UPDATE ON studio_profile
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_import_templates_updated_at
    BEFORE UPDATE ON import_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
