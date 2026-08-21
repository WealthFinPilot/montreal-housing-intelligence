-- ---------------------------------------------------------------------------
-- 02 -- Pipeline run log
--
-- Every automated task writes one row here. Required by section 36 of the
-- original brief: pipeline_name, run_id, started_at, finished_at,
-- rows_received, rows_loaded, status, error_message.
--
-- Why a table and not a log file: a log file answers "what happened last
-- night". A table answers "has this pipeline ever silently loaded zero rows",
-- which is the question that actually matters.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.pipeline_run (
    run_id          UUID        PRIMARY KEY,
    pipeline_name   TEXT        NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,

    -- How many observations the source handed us.
    rows_received   INTEGER,

    -- Split on purpose. On a second identical run, rows_inserted must be 0
    -- and rows_updated must be 0. That pair IS the proof of idempotence
    -- required by acceptance criterion 2 -- it is not a detail.
    rows_inserted   INTEGER,
    rows_updated    INTEGER,

    -- Derived by the database itself, so it can never disagree with the two
    -- columns above. The brief asks for rows_loaded; this is it, computed
    -- rather than trusted to the script.
    rows_loaded     INTEGER GENERATED ALWAYS AS
                    (COALESCE(rows_inserted, 0) + COALESCE(rows_updated, 0)) STORED,

    status          TEXT        NOT NULL,
    error_message   TEXT,

    CONSTRAINT pipeline_run_status_ck
        CHECK (status IN ('running', 'success', 'failed')),

    -- A finished run must say when it finished. Catches a script that dies
    -- between writing rows and closing its log entry.
    CONSTRAINT pipeline_run_finished_ck
        CHECK (status = 'running' OR finished_at IS NOT NULL)
);

COMMENT ON TABLE raw.pipeline_run IS
  'One row per ingestion run. rows_inserted = 0 AND rows_updated = 0 on a '
  'repeated run is the evidence of idempotence.';
