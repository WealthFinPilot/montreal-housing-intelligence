-- ---------------------------------------------------------------------------
-- 05 -- Raw layer: APCIQ Baromètre résidentiel, Tableau 2
--
-- Source: the quarterly Montréal edition of the Baromètre résidentiel, a PDF
-- published by APCIQ from the Centris system. One row per figure read off
-- Tableau 2 of an island or sector page.
--
-- 855 rows per edition: 19 areas (the island plus its 18 APCIQ sectors)
-- x 3 property categories x 5 metrics x 3 periods. 29 editions on record as
-- of 2026-08-23, so about 24 800 rows once the archive is fully loaded.
--
-- LICENCE -- THIS TABLE HOLDS DATA THAT MAY NOT BE REDISTRIBUTED
--
-- Page 65 of every edition, verbatim: « Toute reproduction de l'information
-- qui s'y retrouve, en tout ou en partie, directement ou indirectement, est
-- strictement interdite sans l'autorisation préalable écrite du titulaire du
-- droit d'auteur. »
--
-- Nothing derived from this table belongs in a versioned file, an exported
-- dataset, or a Power BI report published to the web -- a published report
-- exposes its whole semantic model, hidden columns included. The same rule
-- the project already applies to listings applies here.
--
-- WHY VALUES ARE STORED AS TEXT
--
-- Same reason as raw.boc_observation and raw.mtl_administrative_boundary: the
-- raw layer keeps what the source published, and dbt converts where a failure
-- is loud. It matters more here than elsewhere, because a Baromètre cell has
-- four distinct states that a numeric column would flatten into one NULL:
--
--   '123 456 $'  a figure
--   '**'         « Nombre de transactions insuffisant pour produire une
--                  statistique fiable » -- APCIQ withheld it deliberately
--   '-'          printed as a dash, no figure
--   NULL         nothing at all was printed. Seen only in the 2019-era
--                template, and only on days-on-market cells
--
-- Telling "withheld because too thin" apart from "not printed" is exactly the
-- kind of distinction section 41.1 of the brief forbids inventing our way
-- out of.
--
-- WHY BOTH A CODE AND THE SOURCE LABEL
--
-- Reading a PDF means interpreting a position on a page, so the parser has to
-- normalise; there is no source identifier to carry over. The verbatim French
-- label is stored next to every code so the interpretation stays auditable --
-- and it earns its place: the days-on-market row was called « Délai de vente
-- moyen (jours) » in 2019 and « Moyenne de jours sur le marché » in 2026. The
-- wording changed, the meaning did not, and the table shows both.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.apciq_barometer_statistic (
    -- Which quarterly publication this figure was read from. Not the period
    -- the figure describes: an edition reports its own quarter and the twelve
    -- months ending with it, and period_code says which.
    edition_year            INTEGER NOT NULL,
    edition_quarter         INTEGER NOT NULL,

    -- 'island', or 'sector-01' .. 'sector-18'. Zero-padded so that ordering
    -- by text matches ordering by number. Sectors 19 and above are Laval and
    -- the two shores: off the island, out of scope.
    area_code               TEXT    NOT NULL,

    -- 'single_family' | 'condo' | 'plex'
    property_category       TEXT    NOT NULL,

    -- 'sales' | 'active_listings' | 'median_price' | 'average_price'
    -- | 'days_on_market'
    metric_code             TEXT    NOT NULL,

    -- 'quarter'      the edition's own quarter
    -- 'trailing_12m' the twelve months ending with it
    -- 'five_year'    a five-year change, with no value of its own
    period_code             TEXT    NOT NULL,

    -- The cell, as printed. See the four states above.
    value_text              TEXT,

    -- The change APCIQ printed beside it. Page 65: « les taux de variation
    -- sont calculés par rapport au même trimestre de l'année précédente. »
    -- Year over year, never quarter over quarter.
    change_percent_text     TEXT,

    -- Provenance, so any figure can be traced back to a page and read again.
    source_area_label       TEXT    NOT NULL,
    source_category_label   TEXT    NOT NULL,
    source_metric_label     TEXT    NOT NULL,
    source_pdf              TEXT    NOT NULL,
    source_page             INTEGER NOT NULL,

    -- Freshness is measured on first_seen_at, not updated_at: updated_at only
    -- moves when a figure is revised, so a stable series would look stale.
    first_seen_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Idempotence is declared here, not left to the loader. One figure, one
    -- row: rerunning the pipeline over the same PDFs cannot duplicate it.
    CONSTRAINT apciq_barometer_statistic_pk
        PRIMARY KEY (edition_year, edition_quarter, area_code,
                     property_category, metric_code, period_code)
);

-- The natural analytical filter is "one metric across every edition", which
-- scans the primary key backwards. A small table today, but this index costs
-- nothing and the dbt models lean on exactly this shape.
CREATE INDEX IF NOT EXISTS apciq_barometer_statistic_metric_idx
    ON raw.apciq_barometer_statistic (metric_code, period_code, area_code);

COMMENT ON TABLE raw.apciq_barometer_statistic IS
  'Tableau 2 of the APCIQ Baromètre résidentiel (Montréal), read positionally '
  'from the quarterly PDF. Source : APCIQ par le système Centris. '
  'Redistribution of these figures is forbidden without written consent.';

COMMENT ON COLUMN raw.apciq_barometer_statistic.value_text IS
  'The cell as printed. ''**'' means APCIQ withheld the figure for too few '
  'transactions; NULL means nothing was printed at all. Not the same thing.';

COMMENT ON COLUMN raw.apciq_barometer_statistic.change_percent_text IS
  'Year-over-year change as printed, compared with the same quarter of the '
  'previous year (definition given on page 65 of the source).';

COMMENT ON COLUMN raw.apciq_barometer_statistic.area_code IS
  'island, or sector-NN for the 18 APCIQ sectors of the island. Joins to '
  'marts.dim_geography on geography_key apciq_sector:N.';
