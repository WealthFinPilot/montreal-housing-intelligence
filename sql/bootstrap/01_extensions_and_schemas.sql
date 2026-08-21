-- ---------------------------------------------------------------------------
-- 01 -- Extensions and schemas
--
-- Files in this folder run ONCE, in filename order, the first time the
-- database is created. They never run again on an existing volume.
-- ---------------------------------------------------------------------------

-- Spatial types and functions. Not used by the Bank of Canada pipeline, but
-- the geography model of milestone J3 depends on it, and enabling it now costs
-- nothing. IF NOT EXISTS because the postgis image may already have done it.
CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------------
-- Layered schemas. Each layer has one job and one owner.
--
--   raw       what the source actually sent us, untouched. Written by Python.
--   staging   typed, renamed, cleaned. Built by dbt. Never hand-written.
--   marts     analytical tables consumed by Power BI. Built by dbt.
--
-- Keeping them apart means "reload the raw data" and "rebuild the analysis"
-- are two independent operations. A modelling mistake never forces a re-download.
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

COMMENT ON SCHEMA raw IS
  'Landing layer. One table per source endpoint, values stored as received. '
  'Written only by ingestion scripts, never by dbt.';
COMMENT ON SCHEMA staging IS
  'Typed and cleaned layer, built by dbt from raw. Never written by hand.';
COMMENT ON SCHEMA marts IS
  'Analytical layer consumed by Power BI, built by dbt.';
