-- ---------------------------------------------------------------------------
-- 06 -- Raw layer: the control totals run on every APCIQ edition
--
-- One row per reconciliation performed while reading a Baromètre edition:
-- what the source printed as a total, what its own parts add up to, and how
-- far apart the two may legitimately be.
--
-- WHY A CONTROL RESULT IS STORED RATHER THAN ONLY ASSERTED
--
-- Until 2026-08-23 these controls only raised an exception. That had two
-- costs, and the second is the one that mattered.
--
-- A control that only raises leaves nothing behind when it passes. Six months
-- on, nobody can tell an edition that was checked and found sound from one
-- that was never checked -- the evidence exists only in a terminal that has
-- since been closed.
--
-- And it forced a single reaction onto two different situations. Reading a
-- page wrongly and reading a wrong page correctly are not the same failure.
-- The first is ours and must stop everything; the second belongs to the
-- publisher, and refusing the edition destroys 855 sound figures along with
-- the evidence of the defect. Stored, the defect becomes something a model
-- can filter on and a dbt test can freeze.
--
-- THE TWO CONTROLS
--
--   page_table1_vs_table2   On one page: the total residential figure printed
--                           in Tableau 1 against the sum of Tableau 2's three
--                           property categories. Both are printed a few
--                           centimetres apart by the same export and read
--                           with the same column anchors, so agreement
--                           confirms the reading of that page on its own.
--                           Sales agreeing here is the gate: when they do not,
--                           read_edition refuses the edition and nothing
--                           reaches this table.
--
--   sectors_vs_island       Across pages: the 18 sector pages against the
--                           island page, category by category. This one is
--                           about the source being coherent from one page to
--                           the next, not about the reading.
--
-- WHAT THE ARCHIVE ACTUALLY SHOWS (verified 2026-08-23, 29 editions)
--
-- 25 editions pass every control. Four do not, and they are not alike:
--
--   2021 Q4, 2022 Q1, 2022 Q2  Active listings do not reconcile anywhere --
--                              not between the sectors and the island, and
--                              not between the two tables of a single page.
--                              On the 2021 Q4 Villeray page the three
--                              categories of Tableau 2 fall 22 % short of the
--                              total Tableau 1 prints beside them, while the
--                              sales row of that same page matches to the
--                              unit. Same page, same columns, same code: the
--                              contradiction is the source's.
--
--   2023 Q4                    Every page agrees with itself, 19 out of 19.
--                              The sectors merely exceed the island by 0.3 %
--                              on quarterly sales. A different order of
--                              magnitude, and a different verdict.
--
-- The figures behind those percentages are not reproduced here. Page 65 of
-- the source forbids reproducing its content in part, and this file is
-- versioned; the figures themselves are in the table this file creates.
--
-- Nothing downstream may present active listings for the first three quarters
-- without saying so. That rule lives in the marts, where it is testable; this
-- table is what makes it possible to write.
--
-- LICENCE
--
-- These are figures derived from the Baromètre, so the restriction on
-- raw.apciq_barometer_statistic applies here in full: nothing derived from
-- this table belongs in a versioned file, an exported dataset, or a Power BI
-- report published to the web.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.apciq_control_total (
    -- The edition the control was run on.
    edition_year        INTEGER NOT NULL,
    edition_quarter     INTEGER NOT NULL,

    -- 'page_table1_vs_table2' | 'sectors_vs_island'
    control_code        TEXT    NOT NULL,

    -- The area the control is about: the page's own area for an on-page
    -- control, 'island' for the cross-page one.
    scope               TEXT    NOT NULL,

    -- A category code, or 'all' where the source publishes only a combined
    -- total. Tableau 1 combines the three categories, so every on-page
    -- control carries 'all'.
    property_category   TEXT    NOT NULL,

    -- 'sales' | 'active_listings'. Prices and days on market are medians and
    -- averages: eighteen of them do not add up to a nineteenth, and no
    -- arithmetic available here can check them.
    metric_code         TEXT    NOT NULL,
    period_code         TEXT    NOT NULL,

    -- The total as the source printed it, and what its own parts add up to.
    -- Both are stored, not merely their difference: the same gap of a few
    -- units means nothing on a total in the thousands and everything on a
    -- total in the tens.
    published_total     INTEGER NOT NULL,
    computed_total      INTEGER NOT NULL,

    -- How far apart the two may be without meaning anything. Zero on counts.
    -- On active listings it absorbs rounding and nothing else: each figure is
    -- an average rounded once, so three of them against one rounded total
    -- cannot drift past 2, and eighteen against one cannot drift past 9.
    -- Stored per row so that a tolerance changed later cannot silently
    -- rewrite the verdict history.
    tolerance           INTEGER NOT NULL,

    -- The page the control was read from; NULL for the cross-page control,
    -- which belongs to no single page.
    source_page         INTEGER,

    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT apciq_control_total_pk
        PRIMARY KEY (edition_year, edition_quarter, control_code, scope,
                     property_category, metric_code, period_code),

    -- A tolerance is a distance, never a direction.
    CONSTRAINT apciq_control_total_tolerance_not_negative
        CHECK (tolerance >= 0)
);

-- The question asked of this table is almost always "which editions are off,
-- and on what", never "what happened on page 22".
CREATE INDEX IF NOT EXISTS apciq_control_total_metric_idx
    ON raw.apciq_control_total (metric_code, control_code, edition_year,
                                edition_quarter);

COMMENT ON TABLE raw.apciq_control_total IS
  'Reconciliations run while reading each APCIQ Baromètre edition. A row is a '
  'verdict kept as data: published total, computed total, and the tolerance '
  'that separates rounding from a defect. Source : APCIQ par le système '
  'Centris. Redistribution of these figures is forbidden.';

COMMENT ON COLUMN raw.apciq_control_total.computed_total IS
  'What the parts add up to, with a printed dash read as zero on count rows. '
  'That reading is verified by these very controls, not assumed.';

COMMENT ON COLUMN raw.apciq_control_total.tolerance IS
  'Derived, not chosen: zero on counts, and on active listings the most that '
  'rounding one average per published figure can produce.';
