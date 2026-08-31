-- ---------------------------------------------------------------------------
-- 09 -- Raw layer: Statistics Canada Consumer Price Index, monthly
--
-- One table, one series, under the Statistics Canada Open Licence -- the same
-- licence as migration 07, so these figures may sit in a versioned file and in
-- a published report. The exact opposite of the APCIQ rule of migration 05.
--
-- WHY THIS SERIES EXISTS IN THIS PROJECT
--
-- fact_affordability divides a 2026 price by a 2020 income. The gap has been
-- carried as price_year_minus_income_year since J4.1 and displayed as a
-- warning, but never corrected, because no source publishes income below the
-- census metropolitan area after 2021: the full WDS catalogue was swept on
-- 2026-08-31 -- 8 267 cubes, the 27 carrying "census tract" all end in 2021.
--
-- So the income of today cannot be OBSERVED. It can only be CALCULATED: the
-- 2020 census income, restated in dollars of the quarter being displayed.
-- That is what this table makes possible, and the figure it produces is a
-- THEORETICAL median income -- never an observation. The distinction is the
-- same one is_posted_rate and assignment_method carry elsewhere in the model.
--
-- WHY THE CPI RATHER THAN A PUBLISHED INCOME SERIES
--
-- Two indices were measured on 2026-08-31 and both were built. Restating the
-- CMA income series (11100190) in nominal terms agrees with the CPI alone to
-- within 1.3 % over 2021-2024, and diverges by 7.8 % on 2019 -- the isolated
-- pandemic-transfer peak of 2020. The CPI was chosen because it is the only
-- one that reaches the last published quarter: the income series stops at
-- income year 2024, the CPI reaches 2026-07.
--
-- The income series is therefore a CONTROL, measured once and written down in
-- docs/limitations.md, not a source this pipeline ingests. Assuming incomes
-- follow inflation is wrong by a known and bounded amount, which is a very
-- different thing from being wrong by an unknown one.
--
-- WHY EVERY SOURCE FIELD IS TEXT
--
-- Same reasoning as raw.boc_observation, raw.apciq_barometer_statistic and
-- raw.statcan_income_statistic: the raw layer keeps what the source sent, and
-- dbt converts where a failure is loud. A status code stored as an integer
-- would put "normal" and "missing" one typo apart.
--
-- WHAT THE CODES MEAN, read from getCodeSets on 2026-08-31, not from memory
--
--   statusCode  0 normal
--               1 not available for a specific reference period
--               2 value rounded to 0 where a true zero is meaningful
--   symbolCode  0 none, 1 preliminary, 3 revised
--   scalarCode  0 units
--   frequency   6 monthly
--   uom        17 "2002=100"
--
-- Every point retrieved on 2026-08-31 for this vector carried 0 on all four
-- codes and no null value -- 151 points, 2014-01 to 2026-07. That is a fact
-- about today, not a guarantee: the columns exist so a future preliminary or
-- revised figure is visible instead of silently averaged in.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.statcan_cpi_observation (
    -- The published series identifier. Kept as the key rather than the
    -- coordinate because a vector is what Statistics Canada guarantees to be
    -- stable; a coordinate is a position in a cube that can be re-cut.
    vector_id             TEXT NOT NULL,

    -- The first day of the month the observation describes, verbatim from
    -- refPer. A month, not a day: frequencyCode 6.
    ref_period            TEXT NOT NULL,

    -- Traceability back into the published cube. Never joined on.
    product_id            TEXT,
    coordinate            TEXT,
    geo_name              TEXT,
    product_name          TEXT,

    -- The index itself. TEXT for the reason given in the header.
    value                 TEXT,
    decimals              TEXT,

    -- The four codes. Not decoration: a non-zero status or symbol means the
    -- number beside it is not an ordinary final observation.
    status_code           TEXT,
    symbol_code           TEXT,
    scalar_factor_code    TEXT,
    security_level_code   TEXT,
    frequency_code        TEXT,

    -- The unit is the BASE of the index, e.g. "2002=100". Recorded because it
    -- names what the number is -- though the model is deliberately immune to
    -- it: an index divided by an index cancels the base, so a future rebasing
    -- by Statistics Canada cannot change a single ratio downstream.
    uom_code              TEXT,
    uom                   TEXT,

    -- When Statistics Canada released this figure. Distinct from first_seen_at,
    -- which is when this project first saw it.
    release_time          TEXT,

    source_url            TEXT NOT NULL,

    first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT statcan_cpi_observation_pk
        PRIMARY KEY (vector_id, ref_period)
);

COMMENT ON TABLE raw.statcan_cpi_observation IS
  'Statistics Canada table 18100004, Consumer Price Index, monthly, not '
  'seasonally adjusted. Loaded for the Montreal census metropolitan area '
  '(classification 462), All-items. Statistics Canada Open Licence: "use, '
  'reproduce, publish, freely distribute, or sell" -- redistribution allowed. '
  'Purpose: restate the 2020 census income in dollars of a later quarter. The '
  'result is a THEORETICAL income, never an observation.';

COMMENT ON COLUMN raw.statcan_cpi_observation.value IS
  'The index value. NOT a dollar amount and never to be displayed as one. It '
  'is meaningful only as a ratio against another month of the same series.';

COMMENT ON COLUMN raw.statcan_cpi_observation.status_code IS
  'From the WDS status code set, read on 2026-08-31: 0 normal, 1 not '
  'available for this reference period, 2 rounded to zero where a true zero '
  'is meaningful. Never collapse a non-zero status into a usable value.';

COMMENT ON COLUMN raw.statcan_cpi_observation.symbol_code IS
  'From the WDS symbol code set: 0 none, 1 preliminary, 3 revised. A '
  'preliminary index is a figure Statistics Canada expects to change.';

COMMENT ON COLUMN raw.statcan_cpi_observation.uom IS
  'The base of the index, e.g. "2002=100". The quarterly factor built from '
  'this table is a ratio of two months of the same series, so the base '
  'cancels and a rebasing upstream cannot move any figure in the marts.';
