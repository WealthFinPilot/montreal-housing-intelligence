-- ---------------------------------------------------------------------------
-- 07 -- Raw layer: Statistics Canada census geography and household income
--
-- Three tables, one per file downloaded, all under the Statistics Canada Open
-- Licence or the Open Government Licence - Canada. Both permit redistribution,
-- which is why these figures may sit in a versioned file and in a published
-- report -- the exact opposite of the APCIQ rule enforced in migration 05.
--
-- WHY THERE IS NO SPATIAL JOIN ANYWHERE IN THIS MIGRATION
--
-- Restricting census tracts to the Island of Montréal was believed to require
-- one, and it does not. The Geographic Attribute File states the municipality
-- of every dissemination block outright, and census division 2466 turns out to
-- be exactly the Island: 16 census subdivisions, matching the 16 municipalities
-- one for one. Measured on 2026-08-24, with a positive control -- see
-- docs/data-sources.md section 2.9. `csd_uid LIKE '2466%'` is the perimeter.
--
-- WHY EVERY SOURCE FIELD IS TEXT
--
-- Same reasoning as raw.boc_observation and raw.apciq_barometer_statistic. The
-- raw layer keeps what the source sent; dbt converts, where a failure is loud.
-- It matters more than usual here, because Statistics Canada does not leave a
-- cell empty when it has nothing to publish -- it prints a symbol, and the
-- symbols do not all mean the same thing.
--
-- THE THREE ASSERTIONS A CELL CAN MAKE
--
-- Read verbatim from the symbol legend shipped inside 98100058_MetaData.csv,
-- not from memory:
--
--   ''     the value beside it is published
--   'x'    "suppressed to meet the confidentiality requirements of the
--          Statistics Act"  -- a real number exists, the law forbids printing
--          it, and it is almost always a small-count geography
--   '...'  "not applicable"  -- the question does not arise for this
--          combination of household size and household type
--
-- These are three different statements, exactly like APCIQ's '-', '**' and
-- blank. Collapsing them into NULL at load time would destroy the distinction
-- between "the state knows and may not say" and "there is nothing to know".
-- The symbol column is therefore kept beside every value column.
--
-- AND THE TWO NON-VALUES DO NOT LOOK ALIKE
--
-- This is the part that would cost a day. 'x' leaves the value cell empty.
-- '...' does not: it prints the DIGIT ZERO. Measured over the Montréal
-- metropolitan area on 2026-08-24, per 2020 income measure:
--
--     symbol ''     -> a real number, never zero    49 641 cells
--     symbol '...'  -> the literal '0'              18 404 cells
--     symbol 'x'    -> empty                         9 340 cells
--
-- So a loader that decided "empty means missing" would keep 18 404 median
-- household incomes of nought dollars per measure. They cast cleanly, they
-- average quietly, and nothing downstream looks wrong enough to investigate.
--
-- Nor can they be swept up afterwards by discarding zeros, because a zero is
-- REAL DATA on the household counts: 19 385 of those are published as zero,
-- since a tract genuinely can hold no household of a given size and type.
-- Only the symbol separates the two, which is the whole argument for keeping
-- it.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. Geographic Attribute File -- one row per dissemination block
--
-- The finest published geography, and the one that carries every coarser code
-- on the same row: block -> dissemination area -> census tract -> census
-- subdivision. Loaded at block grain on purpose, though the analysis runs at
-- census-tract grain.
--
-- WHY BLOCK GRAIN RATHER THAN THE 541 TRACTS THE ANALYSIS NEEDS
--
-- Because of what the extra rows carry, not because finer is better. A census
-- tract nests inside a municipality -- verified, zero exceptions on the Island
-- -- but nothing published says which borough or which APCIQ sector it falls
-- in, and those do cut tracts in half. Splitting a tract's income between two
-- sectors needs a weight, and population per block is that weight. It is in
-- this file. Aggregating it away at load time would mean re-downloading 298 MB
-- to get it back.
--
-- The dissemination-area representative point is kept for the same reason: it
-- is published twice, in Lambert and in latitude/longitude, which is what let
-- EPSG:3347 be proven rather than assumed (agreement to 5 cm on 6 points).
--
-- SCOPE: Island of Montréal only, census division 2466. 13 844 blocks of the
-- 498 786 in the national file. The filter is the project perimeter, and it is
-- named here so nobody mistakes an absent municipality for a load failure.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.statcan_geographic_attribute (
    -- The block identifier. Unique nationally, so it keys the table on its
    -- own. A duplicate aborts the load rather than producing two rows that
    -- would later double every population sum.
    db_uid                          TEXT NOT NULL,
    db_dguid                        TEXT,

    -- Every coarser geography this block belongs to, as published.
    da_uid                          TEXT,
    ct_uid                          TEXT,
    ct_dguid                        TEXT,
    ct_name                         TEXT,
    cma_uid                         TEXT,
    cma_name                        TEXT,
    csd_uid                         TEXT,
    csd_name                        TEXT,
    csd_type                        TEXT,
    cd_uid                          TEXT,
    pr_uid                          TEXT,

    -- Counts and area. Text, converted in staging.
    population_2021                 TEXT,
    total_dwellings_2021            TEXT,
    usual_resident_dwellings_2021   TEXT,
    land_area_km2                   TEXT,

    -- The representative point of the dissemination area this block sits in,
    -- in both systems the file publishes it in.
    da_lambert_x                    TEXT,
    da_lambert_y                    TEXT,
    da_latitude                     TEXT,
    da_longitude                    TEXT,

    -- Which download this row came from, so a re-release is traceable.
    source_file                     TEXT NOT NULL,

    first_seen_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT statcan_geographic_attribute_pk PRIMARY KEY (db_uid)
);

COMMENT ON TABLE raw.statcan_geographic_attribute IS
  'Statistics Canada 2021 Geographic Attribute File (92-151-X), restricted to '
  'census division 2466 -- which is exactly the Island of Montréal, its 16 '
  'municipalities and nothing else. One row per dissemination block. Statistics '
  'Canada Open Licence: redistribution allowed.';

COMMENT ON COLUMN raw.statcan_geographic_attribute.csd_uid IS
  'Census subdivision, i.e. municipality. Joins to the MAMH municipal code as '
  'csd_uid = ''24'' || mamh_code -- verified for all 16 Island municipalities '
  'on 2026-08-24. A published code, never a name that looks alike.';

COMMENT ON COLUMN raw.statcan_geographic_attribute.ct_uid IS
  'Census tract. Nests entirely inside one municipality on the Island: zero of '
  '541 straddle a municipal boundary. That zero was checked against a positive '
  'control -- 69 tracts elsewhere in Canada do cross one.';

COMMENT ON COLUMN raw.statcan_geographic_attribute.da_lambert_x IS
  'Representative point of the dissemination area, in NAD83 Statistics Canada '
  'Lambert (EPSG:3347), metres. The same point is published as latitude and '
  'longitude in this file, which is what proves the CRS instead of assuming it.';


-- ---------------------------------------------------------------------------
-- 2. Household income statistics -- table 98100058
--
-- NOT one row per geography. The published cube crosses household size (7
-- members) with household type (11 members), so every geography carries
-- exactly 77 rows. Measured: 1 005 geographies x 77 = 77 385 rows for the
-- Montréal CMA, with no geography carrying any other count.
--
-- That regularity is worth keeping, because it is testable. A dbt test asserts
-- 77 rows per geography, so a re-labelled dimension member -- which would make
-- the key below produce a new row instead of updating one -- fails the build
-- loudly instead of silently doubling a geography.
--
-- SCOPE: census metropolitan area 462. That is deliberately wider than the
-- Island: the CMA also contains Laval, Longueuil and both shores, and keeping
-- them makes "the Island against the rest of its metropolitan area" an
-- available comparison rather than a second download. Staging filters down to
-- the 541 Island tracts.
--
-- WHY THE KEY IS THE THREE PUBLISHED LABELS
--
-- The file also carries a `Coordinate` column ("1830.1.1") that would key the
-- table more compactly. It is an internal cube position, meaningless outside
-- this one download, and migration 04 already recorded why that makes a bad
-- key. The labels are what the source actually asserts.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.statcan_income_statistic (
    -- Geographic identifier. Character for character the ct_dguid of table 1
    -- for a census tract, which is what joins income to geography.
    dguid                               TEXT NOT NULL,
    household_size                      TEXT NOT NULL,
    household_type                      TEXT NOT NULL,

    ref_date                            TEXT,
    geo_name                            TEXT,

    -- Kept for traceability back into the published cube, never joined on.
    coordinate                          TEXT,

    -- Six measures, each with the symbol the source printed beside it. The
    -- symbol is not decoration: '' , 'x' and '...' are three different
    -- assertions, and only the first means "this number is the value".
    households_2021                     TEXT,
    households_2021_symbol              TEXT,
    households_2016                     TEXT,
    households_2016_symbol              TEXT,
    median_total_income_2020            TEXT,
    median_total_income_2020_symbol     TEXT,
    median_total_income_2015            TEXT,
    median_total_income_2015_symbol     TEXT,
    median_aftertax_income_2020         TEXT,
    median_aftertax_income_2020_symbol  TEXT,
    median_aftertax_income_2015         TEXT,
    median_aftertax_income_2015_symbol  TEXT,

    source_file                         TEXT NOT NULL,

    first_seen_at                       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT statcan_income_statistic_pk
        PRIMARY KEY (dguid, household_size, household_type)
);

COMMENT ON TABLE raw.statcan_income_statistic IS
  'Statistics Canada table 98100058, household income statistics by household '
  'type, restricted to census metropolitan area 462. 77 rows per geography: '
  'household size crossed with household type. Statistics Canada Open Licence: '
  '"use, reproduce, publish, freely distribute, or sell" -- redistribution '
  'allowed, unlike APCIQ.';

COMMENT ON COLUMN raw.statcan_income_statistic.median_total_income_2020 IS
  'Median household total income for the 2020 income year, in 2020 constant '
  'dollars. A CENSUS figure: it does not move with the market. Any ratio '
  'against a 2026 APCIQ price is an assumption to be displayed, not an '
  'observation -- see brief sections 8.2 and 22.';

COMMENT ON COLUMN raw.statcan_income_statistic.median_total_income_2020_symbol IS
  'Verbatim from 98100058_MetaData.csv: '''' the value is published, ''x'' '
  '"suppressed to meet the confidentiality requirements of the Statistics '
  'Act", ''...'' "not applicable". Never collapse the last two into NULL.';


-- ---------------------------------------------------------------------------
-- 3. Census tract boundaries -- cartographic boundary file lct_000b21a
--
-- Kept as text, converted in staging, exactly as migration 04 does for the
-- city's GeoJSON and for the same reason: a geometry the source changes in a
-- way PostGIS refuses should fail a dbt build with the offending row, not
-- disappear during ingestion.
--
-- WHY source_srid IS STORED RATHER THAN ASSUMED
--
-- The .prj declares "NAD83_Statistics_Canada_Lambert", and PostGIS knows a
-- projection under almost that name at EPSG:3347. Almost is not enough here --
-- this project has already paid for a NAD83 lookalike that loaded without
-- error and produced empty spatial joins (docs/geography.md section 6).
--
-- So it was proven instead: the attribute file publishes the same point twice,
-- in Lambert and in latitude/longitude. Reprojecting the Lambert pair through
-- EPSG:3347 lands on the published latitude and longitude within 5 cm, on
-- every point tested. The number below is a measurement, and storing it means
-- a future file in a different projection cannot be transformed as if it were
-- this one.
--
-- SCOPE: the 541 tracts of the Island, selected by the census-division rule of
-- table 1 rather than by any spatial test.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.statcan_census_tract_boundary (
    ct_uid              TEXT NOT NULL,
    dguid               TEXT,
    ct_name             TEXT,
    pr_uid              TEXT,

    -- Land area as the boundary file states it. Kept beside the geometry so a
    -- computed area can be checked against a published one instead of being
    -- trusted.
    land_area_km2       TEXT,

    -- The polygon, as well-known text, in the coordinate system named below.
    geometry_wkt        TEXT NOT NULL,
    source_srid         INTEGER NOT NULL,

    source_file         TEXT NOT NULL,

    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT statcan_census_tract_boundary_pk PRIMARY KEY (ct_uid)
);

COMMENT ON TABLE raw.statcan_census_tract_boundary IS
  'Statistics Canada 2021 cartographic boundary file for census tracts '
  '(lct_000b21a), restricted to the 541 tracts of the Island. Open Government '
  'Licence - Canada, declared in the file own metadata: redistribution allowed, '
  'including commercially, with attribution.';

COMMENT ON COLUMN raw.statcan_census_tract_boundary.source_srid IS
  'CRS of geometry_wkt. Expected 3347, NAD83 / Statistics Canada Lambert, in '
  'metres -- not degrees, and not the 4326 the city boundary file uses. '
  'Verified by reprojection against coordinates the source publishes itself.';
