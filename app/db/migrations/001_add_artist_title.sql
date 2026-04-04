-- Run once if your database was created before artist_title existed:
--   psql -d moth_and_money -f app/db/migrations/001_add_artist_title.sql

ALTER TABLE studio_profile
    ADD COLUMN IF NOT EXISTS artist_title VARCHAR(255) NOT NULL DEFAULT 'Creative Director';
