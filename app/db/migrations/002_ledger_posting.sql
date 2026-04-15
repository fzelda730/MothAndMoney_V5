-- Paired classification + ledger postings (Option A).
-- Run if your DB was created before these columns existed:
--   psql -d moth_and_money -f app/db/migrations/002_ledger_posting.sql

ALTER TABLE bank_accounts
    ADD COLUMN IF NOT EXISTS ledger_coa_id UUID REFERENCES chart_of_accounts(id) ON DELETE SET NULL;

ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS posting_group_id UUID;

CREATE INDEX IF NOT EXISTS idx_transactions_posting_group ON transactions(posting_group_id)
    WHERE posting_group_id IS NOT NULL;

-- Bank register balance: sum only the classification leg, not the mirrored ledger leg.
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
    )
WHERE ba.is_active = TRUE
GROUP BY ba.id, ba.account_name, ba.account_type,
         ba.account_number_masked, b.bank_name, ls.ending_balance;
