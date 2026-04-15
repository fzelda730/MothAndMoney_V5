-- Trial balance opening as transactions (Option A).
-- Run once if your DB predates this enum value:
--   psql -d moth_and_money -f app/db/migrations/003_trial_balance_opening_source.sql

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum e
        JOIN pg_type t ON e.enumtypid = t.oid
        WHERE t.typname = 'transaction_source_enum'
          AND e.enumlabel = 'trial_balance_opening'
    ) THEN
        ALTER TYPE transaction_source_enum ADD VALUE 'trial_balance_opening';
    END IF;
END
$migration$;

-- TB opening rows use coa_id = ledger_coa_id; include them in register balance (not mirror-only).
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
    AND (
        ba.ledger_coa_id IS NULL
        OR t.coa_id IS DISTINCT FROM ba.ledger_coa_id
        OR t.source = 'trial_balance_opening'::transaction_source_enum
    )
WHERE ba.is_active = TRUE
GROUP BY ba.id, ba.account_name, ba.account_type,
         ba.account_number_masked, b.bank_name, ls.ending_balance;
