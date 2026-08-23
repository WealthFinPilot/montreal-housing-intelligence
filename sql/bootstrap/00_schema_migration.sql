-- ---------------------------------------------------------------------------
-- 00 -- Schema migration registry
--
-- WHY THIS FILE EXISTS
--
-- Docker runs everything in this folder exactly once, the first time the
-- database volume is created, and never again. That was enough while the
-- schema was being written for the first time. It stops being enough the
-- moment a table has to be added to a database that is already running --
-- which is every milestone from J3 onward.
--
-- So the files in this folder now have two ways of running:
--
--   * a brand-new database  -- Docker executes them at container init;
--   * a live database       -- `bash scripts/migrate.sh` executes the ones
--                              this registry has not recorded yet.
--
-- Same files, same order, both paths. There is no second place where the
-- schema is defined, so the two databases cannot drift apart.
--
-- THE RULE THAT MAKES THIS SAFE
--
-- Every file in this folder MUST be replayable: `CREATE ... IF NOT EXISTS`,
-- `ADD COLUMN IF NOT EXISTS`, and so on. The runner reapplies the whole set
-- against a database Docker has already initialised, and a bare `CREATE`
-- would abort the run. A test enforces this (tests/test_migrations.py).
--
-- AND THE ONE THAT KEEPS IT HONEST
--
-- Never edit a file that has already been applied. Add a new one. The
-- checksum column below exists to catch exactly that mistake: an edited file
-- makes `migrate.sh` exit non-zero instead of quietly reporting success.
-- A check that lets a discrepancy through in silence is worse than no check,
-- which is the lesson check-secrets.sh taught on 2026-08-22.
--
-- Placed in `public` rather than raw/staging/marts on purpose: this is
-- infrastructure about the database, not data flowing through it.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.schema_migration (
    filename    TEXT        PRIMARY KEY,
    checksum    TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.schema_migration IS
  'One row per file in sql/bootstrap/ that has been applied to this database. '
  'checksum is the SHA-256 of the file content at the time it ran; a mismatch '
  'means the repository and this database no longer agree.';

COMMENT ON COLUMN public.schema_migration.checksum IS
  'SHA-256 of the file content as applied. Compared on every run.';
