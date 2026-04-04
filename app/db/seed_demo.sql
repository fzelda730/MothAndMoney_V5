-- ============================================================
-- Demo seed data for Moth and Money V4
-- Run after schema.sql:  psql -d moth_and_money -f app/db/seed_demo.sql
-- Safe to re-run: uses fixed UUIDs + WHERE NOT EXISTS guards.
-- ============================================================

-- Banks
INSERT INTO banks (id, bank_name, bank_type)
SELECT 'b1111111-1111-1111-1111-111111111101'::uuid, 'Chase Bank', 'depository'::bank_type_enum
WHERE NOT EXISTS (SELECT 1 FROM banks WHERE id = 'b1111111-1111-1111-1111-111111111101'::uuid);

INSERT INTO banks (id, bank_name, bank_type)
SELECT 'b1111111-1111-1111-1111-111111111102'::uuid, 'American Express', 'credit_card'::bank_type_enum
WHERE NOT EXISTS (SELECT 1 FROM banks WHERE id = 'b1111111-1111-1111-1111-111111111102'::uuid);

INSERT INTO banks (id, bank_name, bank_type)
SELECT 'b1111111-1111-1111-1111-111111111103'::uuid, 'Cash', 'depository'::bank_type_enum
WHERE NOT EXISTS (SELECT 1 FROM banks WHERE id = 'b1111111-1111-1111-1111-111111111103'::uuid);

-- Import templates
INSERT INTO import_templates (id, template_name, template_type, column_map)
SELECT
    'd1111111-1111-1111-1111-111111111101'::uuid,
    'Chase Standard CSV',
    'bank_statement'::template_type_enum,
    '{"date":"Transaction Date","transaction_type":"Type","payee":"Description","amount":"Amount (USD)","chart_of_account":"Account Code","description":"Note"}'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM import_templates WHERE id = 'd1111111-1111-1111-1111-111111111101'::uuid);

INSERT INTO import_templates (id, template_name, template_type, column_map)
SELECT
    'd1111111-1111-1111-1111-111111111102'::uuid,
    'Amex Business Gold',
    'credit_card'::template_type_enum,
    '{"date":"Date","payee":"Description","account":"Account","amount":"Amount","description":"Note"}'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM import_templates WHERE id = 'd1111111-1111-1111-1111-111111111102'::uuid);

-- Bank accounts
INSERT INTO bank_accounts (id, bank_id, template_id, account_name, account_number_masked, account_type)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    'b1111111-1111-1111-1111-111111111101'::uuid,
    'd1111111-1111-1111-1111-111111111101'::uuid,
    'Main Studio Checking',
    '4421',
    'checking'::account_type_enum
WHERE NOT EXISTS (SELECT 1 FROM bank_accounts WHERE id = 'c1111111-1111-1111-1111-111111111101'::uuid);

INSERT INTO bank_accounts (id, bank_id, template_id, account_name, account_number_masked, account_type)
SELECT
    'c1111111-1111-1111-1111-111111111102'::uuid,
    'b1111111-1111-1111-1111-111111111101'::uuid,
    'd1111111-1111-1111-1111-111111111101'::uuid,
    'Emergency Reserve',
    '8834',
    'savings'::account_type_enum
WHERE NOT EXISTS (SELECT 1 FROM bank_accounts WHERE id = 'c1111111-1111-1111-1111-111111111102'::uuid);

INSERT INTO bank_accounts (id, bank_id, template_id, account_name, account_number_masked, account_type)
SELECT
    'c1111111-1111-1111-1111-111111111103'::uuid,
    'b1111111-1111-1111-1111-111111111102'::uuid,
    'd1111111-1111-1111-1111-111111111102'::uuid,
    'Artist Rewards Visa',
    '1002',
    'credit_card'::account_type_enum
WHERE NOT EXISTS (SELECT 1 FROM bank_accounts WHERE id = 'c1111111-1111-1111-1111-111111111103'::uuid);

INSERT INTO bank_accounts (id, bank_id, account_name, account_number_masked, account_type)
SELECT
    'c1111111-1111-1111-1111-111111111104'::uuid,
    'b1111111-1111-1111-1111-111111111103'::uuid,
    'Petty Cash Box',
    '—',
    'cash'::account_type_enum
WHERE NOT EXISTS (SELECT 1 FROM bank_accounts WHERE id = 'c1111111-1111-1111-1111-111111111104'::uuid);

-- Opening balances via ledger submissions (view uses latest ending_balance as opening baseline)
INSERT INTO ledger_submissions (
    bank_account_id, period_label, period_start, period_end,
    beginning_balance, total_debits, total_credits, ending_balance
)
SELECT 'c1111111-1111-1111-1111-111111111101'::uuid, 'Opening', '2024-01-01', '2024-01-01',
       0, 0, 0, 28450.00
WHERE NOT EXISTS (
    SELECT 1 FROM ledger_submissions WHERE bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
);

INSERT INTO ledger_submissions (
    bank_account_id, period_label, period_start, period_end,
    beginning_balance, total_debits, total_credits, ending_balance
)
SELECT 'c1111111-1111-1111-1111-111111111102'::uuid, 'Opening', '2024-01-01', '2024-01-01',
       0, 0, 0, 15000.00
WHERE NOT EXISTS (
    SELECT 1 FROM ledger_submissions WHERE bank_account_id = 'c1111111-1111-1111-1111-111111111102'::uuid
);

INSERT INTO ledger_submissions (
    bank_account_id, period_label, period_start, period_end,
    beginning_balance, total_debits, total_credits, ending_balance
)
SELECT 'c1111111-1111-1111-1111-111111111103'::uuid, 'Opening', '2024-01-01', '2024-01-01',
       0, 0, 0, -1240.20
WHERE NOT EXISTS (
    SELECT 1 FROM ledger_submissions WHERE bank_account_id = 'c1111111-1111-1111-1111-111111111103'::uuid
);

INSERT INTO ledger_submissions (
    bank_account_id, period_label, period_start, period_end,
    beginning_balance, total_debits, total_credits, ending_balance
)
SELECT 'c1111111-1111-1111-1111-111111111104'::uuid, 'Opening', '2024-01-01', '2024-01-01',
       0, 0, 0, 450.00
WHERE NOT EXISTS (
    SELECT 1 FROM ledger_submissions WHERE bank_account_id = 'c1111111-1111-1111-1111-111111111104'::uuid
);

-- Transactions (Main Studio Checking): net -4220 debits + 12850 credits from opening 28450 -> 37080
INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '5200' LIMIT 1),
    '2023-10-12'::date,
    'The Canvas Depot',
    'the canvas depot',
    459.00, 0,
    'Store #4412 · Studio Supplies',
    'bank_import'::transaction_source_enum,
    'cleared'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND t.payee = 'The Canvas Depot' AND t.date = '2023-10-12'::date
);

INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '4100' LIMIT 1),
    '2023-10-10'::date,
    'Client Retainer: V. Gogh',
    'client retainer v gogh',
    0, 2500.00,
    'Q4 Landscape Commission',
    'bank_import'::transaction_source_enum,
    'cleared'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND t.payee LIKE 'Client Retainer%' AND t.date = '2023-10-10'::date
);

INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '5100' LIMIT 1),
    '2023-10-08'::date,
    'Studio Rental Corp',
    'studio rental corp',
    1800.00, 0,
    'Monthly Fixed Rent',
    'bank_import'::transaction_source_enum,
    'cleared'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND t.payee = 'Studio Rental Corp' AND t.date = '2023-10-08'::date
);

INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '5600' LIMIT 1),
    '2023-10-05'::date,
    'Freight Logistics Intl',
    'freight logistics intl',
    870.50, 0,
    'Shipping Paris Exhibition',
    'bank_import'::transaction_source_enum,
    'pending'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND t.payee = 'Freight Logistics Intl' AND t.date = '2023-10-05'::date
);

INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    NULL,
    '2023-10-04'::date,
    'Misc Cash Deposit',
    'misc cash deposit',
    0, 620.50,
    'Uncategorized Transaction',
    'bank_import'::transaction_source_enum,
    'flagged'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND t.payee = 'Misc Cash Deposit' AND t.date = '2023-10-04'::date
);

-- Remaining activity so opening 28450 with debits 4220 / credits 12850 -> ending 37080
INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '4100' LIMIT 1),
    '2023-10-15'::date,
    'Additional inflows (demo)',
    'additional inflows demo',
    0, 9729.50,
    'Balances demo',
    'bank_import'::transaction_source_enum,
    'cleared'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND t.payee = 'Additional inflows (demo)'
);

INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '5200' LIMIT 1),
    '2023-10-16'::date,
    'Additional outflows (demo)',
    'additional outflows demo',
    1090.50, 0,
    'Balances demo',
    'bank_import'::transaction_source_enum,
    'cleared'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND t.payee = 'Additional outflows (demo)'
);

-- Emergency Reserve: +1500 credit
INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111102'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '1100' LIMIT 1),
    '2023-10-01'::date,
    'Transfer In',
    'transfer in',
    0, 1500.00,
    'Reserve funding',
    'bank_import'::transaction_source_enum,
    'cleared'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111102'::uuid
      AND t.payee = 'Transfer In'
);

-- Credit card: charges and payment
INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111103'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '5300' LIMIT 1),
    '2023-10-11'::date,
    'Various Merchants',
    'various merchants',
    2140.00, 0,
    'Card charges',
    'credit_card_import'::transaction_source_enum,
    'cleared'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111103'::uuid
      AND t.payee = 'Various Merchants'
);

INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111103'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '1100' LIMIT 1),
    '2023-10-20'::date,
    'Payment Thank You',
    'payment thank you',
    0, 1500.00,
    'Payment applied',
    'credit_card_import'::transaction_source_enum,
    'cleared'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111103'::uuid
      AND t.payee = 'Payment Thank You'
);

-- Petty cash
INSERT INTO transactions (
    bank_account_id, coa_id, date, payee, payee_normalized,
    debit_amount, credit_amount, description, source, status
)
SELECT
    'c1111111-1111-1111-1111-111111111104'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '5700' LIMIT 1),
    '2023-10-03'::date,
    'Coffee Run',
    'coffee run',
    85.50, 0,
    'Petty cash out',
    'bank_import'::transaction_source_enum,
    'cleared'::transaction_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.bank_account_id = 'c1111111-1111-1111-1111-111111111104'::uuid
      AND t.payee = 'Coffee Run'
);

-- Trial balance onboarding preview rows
INSERT INTO trial_balance_entries (
    bank_account_id, coa_id, reference_name, debit_amount, credit_amount, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '1100'),
    'Main / Cash',
    12450.00, 0,
    'confirmed'::trial_balance_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM trial_balance_entries te
    WHERE te.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND te.reference_name = 'Main / Cash'
);

INSERT INTO trial_balance_entries (
    bank_account_id, coa_id, reference_name, debit_amount, credit_amount, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '1200'),
    'Main / AR',
    4200.50, 0,
    'confirmed'::trial_balance_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM trial_balance_entries te
    WHERE te.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND te.reference_name = 'Main / AR'
);

INSERT INTO trial_balance_entries (
    bank_account_id, coa_id, reference_name, debit_amount, credit_amount, status
)
SELECT
    'c1111111-1111-1111-1111-111111111103'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '2100'),
    'Card / AP',
    0, 8100.00,
    'confirmed'::trial_balance_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM trial_balance_entries te
    WHERE te.bank_account_id = 'c1111111-1111-1111-1111-111111111103'::uuid
      AND te.reference_name = 'Card / AP'
);

INSERT INTO trial_balance_entries (
    bank_account_id, coa_id, reference_name, debit_amount, credit_amount, status
)
SELECT
    'c1111111-1111-1111-1111-111111111103'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '3100'),
    'Card / Equity',
    0, 5000.00,
    'confirmed'::trial_balance_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM trial_balance_entries te
    WHERE te.bank_account_id = 'c1111111-1111-1111-1111-111111111103'::uuid
      AND te.reference_name = 'Card / Equity'
);

INSERT INTO trial_balance_entries (
    bank_account_id, coa_id, reference_name, debit_amount, credit_amount, status
)
SELECT
    'c1111111-1111-1111-1111-111111111101'::uuid,
    (SELECT id FROM chart_of_accounts WHERE account_number = '4100'),
    'Main / Sales',
    0, 3550.50,
    'confirmed'::trial_balance_status_enum
WHERE NOT EXISTS (
    SELECT 1 FROM trial_balance_entries te
    WHERE te.bank_account_id = 'c1111111-1111-1111-1111-111111111101'::uuid
      AND te.reference_name = 'Main / Sales'
);
