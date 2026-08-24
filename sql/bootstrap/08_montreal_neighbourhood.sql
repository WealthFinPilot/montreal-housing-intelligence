-- ---------------------------------------------------------------------------
-- 08 -- Raw layer: the neighbourhood layers of Ville de Montreal
--
-- Two CC-BY 4.0 GeoJSON files from donnees.montreal.ca, loaded for one reason:
-- they are the only published documents that cut the two boroughs APCIQ cuts.
--
-- WHY THIS MIGRATION EXISTS AT ALL, WHEN J3.1 SAID POLYGONS WOULD BE CARVED
--
-- The plan recorded at the end of J3.3 was to rebuild the eighteen APCIQ sector
-- polygons by slicing administrative boundaries with neighbourhoods as a knife
-- (ST_Intersection / ST_Difference), then to attach census tracts to the result.
-- That work is not needed, and the measurement that killed it is worth keeping:
--
--   * the 3 228 populated dissemination-area representative points each fall in
--     exactly one of the 34 administrative entities -- none outside, none in two
--   * 532 of the 534 populated census tracts fall entirely inside one entity
--   * the 62 tracts of the two boroughs APCIQ splits resolve ENTIRELY through
--     these two files: 40 in Cote-des-Neiges-Notre-Dame-de-Grace, 22 in Verdun,
--     and not one of them straddles a sector line
--
-- So a tract reaches an APCIQ sector by a point falling in a polygon, never by
-- a polygon being cut. Measured 2026-08-24 -- docs/geography.md section 7.
--
-- WHY TWO FILES AND NOT ONE
--
-- Neither is sufficient on its own, and this is not a preference:
--
--   quartiers-sociologiques  names "Cote-des-Neiges" and "Notre-Dame-de-Grace"
--                            as separate polygons. Nothing else published does,
--                            and APCIQ sectors 8 and 7 are exactly those two.
--
--   quartiers                ("Quartiers de reference en habitation") isolates
--                            "Ile-des-Soeurs", which is APCIQ sector 10, from
--                            the rest of Verdun, which is part of sector 4.
--                            The sociological file has one polygon for the
--                            whole of Verdun and cannot make that cut.
--
-- WHAT IS DELIBERATELY NOT DONE HERE
--
-- The two files are NOT merged, unioned or reconciled. Their borders do not
-- coincide -- 0.44 % apart on Cote-des-Neiges-Notre-Dame-de-Grace, measured
-- 2026-08-23 -- and this project has already recorded what happens when
-- polygons from different files are combined. Each file is used alone, on the
-- one borough it alone can cut, and a point is asked which polygon it is in.
-- ---------------------------------------------------------------------------


CREATE TABLE IF NOT EXISTS raw.mtl_neighbourhood (
    -- Which of the two files this row came from. Part of the key, because the
    -- two number their neighbourhoods independently and both start at 1.
    source_dataset              TEXT NOT NULL,

    -- The key the file itself publishes: `id` in the sociological file, `no_qr`
    -- in the housing-reference file. Unique within its file -- checked at load,
    -- 32/32 and 91/91 on 2026-08-24 -- so it keys this table without a name
    -- ever being compared.
    neighbourhood_code          TEXT NOT NULL,
    neighbourhood_name          TEXT,

    /*
        The borough this neighbourhood belongs to, as a code this project
        already uses, derived from a code the file publishes -- never from the
        name beside it.

        The housing-reference file carries `no_arr`, and 'REM' || no_arr lands
        on all nineteen borough codes of raw.mtl_administrative_boundary: none
        missing, none extra, verified 2026-08-24. Its fourteen remaining
        features are linked cities, which have no borough, and carry no no_arr.

        The sociological file publishes no such code, so this column is NULL for
        every one of its rows. That NULL is the honest answer: matching
        "Cote-des-Neiges-Notre-Dame-de-Grace" spelled by one organisation to the
        same words spelled by another is precisely the join this project refuses.
        Nothing downstream needs it -- the seed addresses those two polygons by
        their published id.
    */
    borough_code                TEXT,

    -- What the file itself says about where this neighbourhood sits. Kept
    -- verbatim so a reader can find the wording in the source, and never
    -- joined on.
    borough_name_source         TEXT,
    municipality_name_source    TEXT,

    -- Every property of the feature, exactly as the file spelled it. The two
    -- files have entirely different attribute sets, and this project has been
    -- bitten before by an attribute discarded at load time that had to be
    -- fetched again later.
    properties_json             TEXT NOT NULL,

    -- The polygon as GeoJSON text, converted to a geometry in staging where a
    -- failure stops a dbt build instead of being swallowed by a script. Same
    -- contract as migration 04.
    geometry_geojson            TEXT NOT NULL,

    -- CRS84 for both files, checked before a row is written. Migration 04
    -- records what loading the NAD83 twin costs: it loads without error and
    -- every spatial join silently returns nothing.
    source_crs                  TEXT NOT NULL,

    first_seen_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT mtl_neighbourhood_pk PRIMARY KEY (source_dataset, neighbourhood_code)
);

COMMENT ON TABLE raw.mtl_neighbourhood IS
  'Neighbourhood polygons of Ville de Montreal, from two donnees.montreal.ca '
  'datasets (quartiers-sociologiques, quartiers). CC-BY 4.0: redistribution '
  'allowed with attribution. Loaded to resolve the only two boroughs APCIQ '
  'splits; not merged with each other, and not used to carve anything.';

COMMENT ON COLUMN raw.mtl_neighbourhood.borough_code IS
  'REM code of the borough, derived from the published no_arr, never from a '
  'name. NULL for every sociological-file row -- that file publishes no code, '
  'and guessing one from matching names is the join this project forbids.';

COMMENT ON COLUMN raw.mtl_neighbourhood.neighbourhood_code IS
  'The key the file publishes: id (sociological) or no_qr (housing reference). '
  'A seed maps four of these codes to APCIQ sectors, and a test asserts the '
  'name still beside each code -- so a renumbered file fails the build instead '
  'of quietly attaching the wrong polygon to a sector.';
