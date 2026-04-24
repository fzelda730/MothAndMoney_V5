-- Manual register transaction from New entry (one line on a bank register).
-- Run once on existing DB:
--   psql -d moth_and_money -f app/db/migrations/005_manual_register.sql

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum e
        JOIN pg_type t ON e.enumtypid = t.oid
        WHERE t.typname = 'transaction_source_enum'
          AND e.enumlabel = 'manual_register'
    ) THEN
        ALTER TYPE transaction_source_enum ADD VALUE 'manual_register';
    END IF;
END
$migration$;
