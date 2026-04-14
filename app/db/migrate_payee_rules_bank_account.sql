-- One-time migration: payee_rules from template_id to bank_account_id.
-- Run after backup: psql -d moth_and_money -f app/db/migrate_payee_rules_bank_account.sql

ALTER TABLE payee_rules ADD COLUMN IF NOT EXISTS bank_account_id UUID REFERENCES bank_accounts(id) ON DELETE CASCADE;

INSERT INTO payee_rules (payee_pattern, coa_id, bank_account_id, transaction_type, confidence)
SELECT pr.payee_pattern, pr.coa_id, ba.id, pr.transaction_type, pr.confidence
FROM payee_rules pr
INNER JOIN bank_accounts ba ON ba.template_id = pr.template_id
WHERE pr.bank_account_id IS NULL AND pr.template_id IS NOT NULL;

DELETE FROM payee_rules WHERE bank_account_id IS NULL;

ALTER TABLE payee_rules DROP CONSTRAINT IF EXISTS payee_rules_payee_pattern_template_id_key;

ALTER TABLE payee_rules DROP COLUMN IF EXISTS template_id;

ALTER TABLE payee_rules ALTER COLUMN bank_account_id SET NOT NULL;

ALTER TABLE payee_rules ADD CONSTRAINT payee_rules_payee_pattern_bank_account_id_key UNIQUE (payee_pattern, bank_account_id);
