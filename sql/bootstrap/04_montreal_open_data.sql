-- ---------------------------------------------------------------------------
-- 04 -- Raw layer: Données Montréal administrative boundaries
--
-- Source: donnees.montreal.ca, dataset `limites-administratives-agglomeration`,
-- CC-BY 4.0. 34 features: 19 boroughs of Ville de Montréal plus the 15 linked
-- cities that share the island with it.
--
-- (Named without the `raw` word the sibling files use: a local hook in this
-- working copy refuses to write any path containing `_raw`.)
--
-- WHY THE GEOMETRY IS STORED AS TEXT
--
-- Same reasoning as raw.boc_observation storing rates as text: the raw layer
-- keeps what the source sent, and dbt does the converting where a failure is
-- loud. `ST_GeomFromGeoJSON` lives in the staging model, and if the source
-- ever ships a geometry PostGIS refuses, the staging build fails with the
-- offending row instead of the ingestion silently dropping it.
--
-- The raw layer is never queried spatially, so it loses nothing by not
-- holding a geometry type here.
--
-- WHY codemamh IS THE PRIMARY KEY
--
-- It is the only column in the file that is also a key in another source.
-- Verified on 2026-08-23 against the MAMH assessment roll already extracted:
--
--   linked city  -> codemamh is the 5-digit municipality code (66112 = Baie-D'Urfé)
--                   and matches the roll's municipality_code
--   borough      -> codemamh is a REMxx code                  (REM19 = Ville-Marie)
--                   and matches the roll's borough_code
--
-- One column, two nomenclatures, and the `type` column says which. Making it
-- the key means a duplicate or a missing code aborts the load rather than
-- producing two rows that later join twice.
--
-- CODEID exists too, but it is an internal file identifier with no meaning
-- outside this one download -- a bad thing to key on.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.mtl_administrative_boundary (
    -- Which CKAN dataset this row came from. One table can serve several
    -- boundary files later (neighbourhoods, sectors) without a second schema.
    source_dataset      TEXT NOT NULL,

    codemamh            TEXT NOT NULL,

    -- Attributes exactly as the file spells them, all text. Renaming and
    -- typing happen in staging.
    codeid              TEXT,
    nom                 TEXT,
    num                 TEXT,
    abrev               TEXT,
    comment             TEXT,
    datemodif           TEXT,

    -- `type` is a reserved-ish word in enough dialects to be worth avoiding
    -- as a bare column name; the source calls it TYPE and staging renames it
    -- to something explicit.
    entity_type         TEXT,

    -- The `geometry` member of the GeoJSON feature, serialised. Converted in
    -- staging, not here.
    geometry_geojson    TEXT NOT NULL,

    -- The coordinate reference system the file declared. Stored rather than
    -- assumed: this dataset also publishes a NAD83 variant, and loading that
    -- one by mistake would put metres where degrees are expected -- an error
    -- that yields empty spatial joins rather than an exception.
    source_crs          TEXT NOT NULL,

    -- Freshness is measured on first_seen_at, not updated_at: updated_at only
    -- moves when the source revises something, so a stable dataset would look
    -- stale.
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT mtl_administrative_boundary_pk
        PRIMARY KEY (source_dataset, codemamh)
);

COMMENT ON TABLE raw.mtl_administrative_boundary IS
  'Administrative boundaries of the Montréal agglomeration as published by the '
  'city (CC-BY 4.0). 19 boroughs + 15 linked cities. Geometry kept as GeoJSON '
  'text; staging converts it with ST_GeomFromGeoJSON.';

COMMENT ON COLUMN raw.mtl_administrative_boundary.codemamh IS
  'Official code. A 5-digit municipality code for a linked city, a REMxx '
  'borough code for a borough. Joins to the MAMH roll on either side.';

COMMENT ON COLUMN raw.mtl_administrative_boundary.source_crs IS
  'CRS declared by the source file. Expected urn:ogc:def:crs:OGC:1.3:CRS84 '
  '(equivalent to EPSG:4326). The ingestion refuses anything else.';
