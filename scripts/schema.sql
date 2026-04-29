-- MOTH AND MONEY V4: THE CORE SCHEMA
-- Designed for Human Readability & Audit Integrity

-- 1. THE CHART OF ACCOUNTS (The Map)
CREATE TABLE chart_of_accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_number INTEGER NOT NULL UNIQUE, -- 1000, 2000, etc.
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL, -- Asset, Liability, Equity, Revenue, Expense
    normal_balance TEXT NOT NULL, -- Debit or Credit
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. THE BANK REGISTERS (The Chambers)
CREATE TABLE bank_registers (
    register_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    register_name TEXT NOT NULL, -- e.g., "Relay Business Checking"
    bank_name TEXT,
    account_last_four VARCHAR(4),
    ledger_account_id UUID REFERENCES chart_of_accounts(account_id), -- Links to the 1000-series
    currency_type VARCHAR(3) DEFAULT 'USD',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. THE TRANSACTION LEDGER (The Truth)
CREATE TABLE transaction_ledger (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    posting_date DATE NOT NULL,
    register_id UUID REFERENCES bank_registers(register_id),
    chart_of_accounts_id UUID REFERENCES chart_of_accounts(account_id),
    payee_name TEXT,
    transaction_description TEXT,
    debit_amount DECIMAL(15, 2) DEFAULT 0.00,
    credit_amount DECIMAL(15, 2) DEFAULT 0.00,
    reconciliation_status TEXT DEFAULT 'Pending', -- Pending, Cleared, Flagged
    source_file_name TEXT, -- For audit trail to the original PDF/CSV
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. THE PAYEE MAPPING (The AI memory)
CREATE TABLE payee_classification_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payee_pattern TEXT NOT NULL, -- e.g., "Amazon"
    suggested_chart_of_accounts_id UUID REFERENCES chart_of_accounts(account_id),
    confidence_score FLOAT DEFAULT 1.0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);