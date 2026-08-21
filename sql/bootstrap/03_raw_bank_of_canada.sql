-- ---------------------------------------------------------------------------
-- 03 -- Bank of Canada: landing table
--
-- Source: Valet API, https://www.bankofcanada.ca/valet/
-- Response shape verified on 2026-08-21 against a real call:
--
--   {
--     "terms": { "url": "..." },
--     "seriesDetail": { "V122514": { "label": "Overnight rate", ... } },
--     "observations": [ { "d": "2026-07-01", "V122514": { "v": "2.2599" } } ]
--   }
--
-- Note that "v" arrives as a JSON STRING, not a number. We keep it that way.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.boc_observation (

    -- ---- Natural key ------------------------------------------------------
    -- A time series has exactly one value per date. That fact, declared here
    -- as a primary key, is what makes the pipeline idempotent: re-running it
    -- CANNOT create a duplicate, because the database refuses one. The rule
    -- lives in the database, not in the script, so a buggy script cannot
    -- bypass it.
    series_id           TEXT NOT NULL,
    observation_date    DATE NOT NULL,

    -- ---- The value, exactly as received -----------------------------------
    -- TEXT, not NUMERIC, and nullable. Two reasons:
    --   1. Valet returns "" for non-publication days (weekends, holidays) on
    --      daily series. That is information, not an error: the source really
    --      did publish nothing that day. Casting here would either crash or
    --      silently invent a zero.
    --   2. If the source ever sends "n/a" or changes format, ingestion still
    --      succeeds and the problem surfaces in dbt as a failing test, loudly,
    --      instead of breaking the collection.
    -- Interpretation belongs to the staging layer. This layer only records.
    value_raw           TEXT,

    -- ---- Provenance -------------------------------------------------------
    -- Which exact URL produced this row, and which run wrote it. Answers
    -- "where does this number come from" without guesswork.
    source_url          TEXT NOT NULL,
    run_id              UUID NOT NULL
                        REFERENCES raw.pipeline_run (run_id),

    -- ---- Technical timestamps ---------------------------------------------
    -- first_seen_at never changes: when we first recorded this observation.
    -- updated_at moves only when the VALUE actually changed, so a revision by
    -- the Bank of Canada is visible even though we keep only the latest value.
    -- Decision of 2026-08-21: a revision overwrites the previous value. We do
    -- not keep value history. Accepted limitation -- this project analyses the
    -- market, it does not audit the Bank of Canada.
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT boc_observation_pk
        PRIMARY KEY (series_id, observation_date),

    -- Structural guard, not a judgement on the data: a row must say which
    -- series it belongs to.
    CONSTRAINT boc_observation_series_not_blank_ck
        CHECK (series_id <> '')
);

COMMENT ON TABLE raw.boc_observation IS
  'Bank of Canada Valet observations as received. One row per (series, date). '
  'Values kept as text on purpose; the staging layer casts them.';

COMMENT ON COLUMN raw.boc_observation.value_raw IS
  'Value exactly as sent by Valet, including empty strings for '
  'non-publication days. Never cast at this layer.';

COMMENT ON COLUMN raw.boc_observation.updated_at IS
  'Moves only when value_raw actually changed, i.e. when the source revised '
  'a published figure.';

-- No extra index. The primary key already indexes (series_id, observation_date),
-- and this table holds a few thousand rows. Adding indexes before a slow query
-- exists is guessing.
