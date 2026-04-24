-- Manual journal entries (balanced multi-line GL) and journal register account type.
-- Run once on existing DB:
--   psql -d moth_and_money -f app/db/migrations/004_journal_entry.sql

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum e
        JOIN pg_type t ON e.enumtypid = t.oid
        WHERE t.typname = 'transaction_source_enum'
          AND e.enumlabel = 'journal_entry'
    ) THEN
        ALTER TYPE transaction_source_enum ADD VALUE 'journal_entry';
    END IF;
END
$migration$;

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum e
        JOIN pg_type t ON e.enumtypid = t.oid
        WHERE t.typname = 'account_type_enum'
          AND e.enumlabel = 'journal'
    ) THEN
        ALTER TYPE account_type_enum ADD VALUE 'journal';
    END IF;
END
$migration$;
