"""Write boundary features into PostgreSQL, idempotently. No HTTP here.

Same contract as ingestion/bank_of_canada/load.py: this module never commits.
The caller decides when work becomes permanent, which is what lets the tests
run against the real tables and roll back afterwards.

Where idempotence comes from, again: not from this code, but from the primary
key (source_dataset, codemamh) declared on the table. One entity, one row --
stated in the database, so a buggy script cannot duplicate it.

The WHERE clause on DO UPDATE is what keeps updated_at meaningful. A rerun
against an unchanged file rewrites nothing and reports 0 inserted, 0 updated,
which is the same evidence of idempotence J2 asked for.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

UPSERT_SQL = """
INSERT INTO raw.mtl_administrative_boundary AS existing
       (source_dataset, codemamh, codeid, nom, num, abrev, entity_type,
        comment, datemodif, geometry_geojson, source_crs)
SELECT %(source_dataset)s, c, i, n, u, a, t, m, d, g, %(source_crs)s
  FROM unnest(
           %(codemamh)s::text[],
           %(codeid)s::text[],
           %(nom)s::text[],
           %(num)s::text[],
           %(abrev)s::text[],
           %(entity_type)s::text[],
           %(comment)s::text[],
           %(datemodif)s::text[],
           %(geometry)s::text[]
       ) AS incoming(c, i, n, u, a, t, m, d, g)
ON CONFLICT (source_dataset, codemamh) DO UPDATE
   SET codeid           = excluded.codeid,
       nom              = excluded.nom,
       num              = excluded.num,
       abrev            = excluded.abrev,
       entity_type      = excluded.entity_type,
       comment          = excluded.comment,
       datemodif        = excluded.datemodif,
       geometry_geojson = excluded.geometry_geojson,
       source_crs       = excluded.source_crs,
       updated_at       = now()
 WHERE (existing.codeid, existing.nom, existing.num, existing.abrev,
        existing.entity_type, existing.comment, existing.datemodif,
        existing.geometry_geojson, existing.source_crs)
    IS DISTINCT FROM
       (excluded.codeid, excluded.nom, excluded.num, excluded.abrev,
        excluded.entity_type, excluded.comment, excluded.datemodif,
        excluded.geometry_geojson, excluded.source_crs)
RETURNING (xmax = 0) AS was_inserted
"""


@dataclass(frozen=True)
class LoadResult:
    inserted: int
    updated: int

    @property
    def total(self) -> int:
        return self.inserted + self.updated

    def __str__(self) -> str:
        return f"{self.inserted} inserted, {self.updated} updated"


def load_boundaries(
    conn: psycopg.Connection,
    features,
    *,
    source_dataset: str,
    source_crs: str,
) -> LoadResult:
    """Insert or refresh boundary rows. Does not commit.

    No run_id column here, unlike raw.boc_observation: a boundary file is a
    snapshot of the present, replaced wholesale, not a series accumulating one
    row per run. The run is still recorded in raw.pipeline_run by the caller.
    """
    features = list(features)
    if not features:
        return LoadResult(0, 0)

    with conn.cursor() as cur:
        cur.execute(
            UPSERT_SQL,
            {
                "source_dataset": source_dataset,
                "source_crs": source_crs,
                "codemamh": [f.codemamh for f in features],
                "codeid": [f.codeid for f in features],
                "nom": [f.nom for f in features],
                "num": [f.num for f in features],
                "abrev": [f.abrev for f in features],
                "entity_type": [f.entity_type for f in features],
                "comment": [f.comment for f in features],
                "datemodif": [f.datemodif for f in features],
                "geometry": [f.geometry_geojson for f in features],
            },
        )
        outcomes = [row[0] for row in cur.fetchall()]

    inserted = sum(1 for was_inserted in outcomes if was_inserted)
    return LoadResult(inserted=inserted, updated=len(outcomes) - inserted)


NEIGHBOURHOOD_UPSERT_SQL = """
INSERT INTO raw.mtl_neighbourhood AS existing
       (source_dataset, neighbourhood_code, neighbourhood_name, borough_code,
        borough_name_source, municipality_name_source, properties_json,
        geometry_geojson, source_crs)
SELECT %(source_dataset)s, c, n, bc, bn, mn, p, g, %(source_crs)s
  FROM unnest(
           %(neighbourhood_code)s::text[],
           %(neighbourhood_name)s::text[],
           %(borough_code)s::text[],
           %(borough_name_source)s::text[],
           %(municipality_name_source)s::text[],
           %(properties_json)s::text[],
           %(geometry_geojson)s::text[]
       ) AS incoming(c, n, bc, bn, mn, p, g)
ON CONFLICT (source_dataset, neighbourhood_code) DO UPDATE
   SET neighbourhood_name       = excluded.neighbourhood_name,
       borough_code             = excluded.borough_code,
       borough_name_source      = excluded.borough_name_source,
       municipality_name_source = excluded.municipality_name_source,
       properties_json          = excluded.properties_json,
       geometry_geojson         = excluded.geometry_geojson,
       source_crs               = excluded.source_crs,
       updated_at               = now()
 WHERE (existing.neighbourhood_name, existing.borough_code,
        existing.borough_name_source, existing.municipality_name_source,
        existing.properties_json, existing.geometry_geojson, existing.source_crs)
    IS DISTINCT FROM
       (excluded.neighbourhood_name, excluded.borough_code,
        excluded.borough_name_source, excluded.municipality_name_source,
        excluded.properties_json, excluded.geometry_geojson, excluded.source_crs)
RETURNING (xmax = 0) AS was_inserted
"""


def load_neighbourhoods(
    conn: psycopg.Connection,
    features,
    *,
    source_dataset: str,
    source_crs: str,
) -> LoadResult:
    """Insert or refresh neighbourhood rows. Does not commit.

    Same contract as load_boundaries, and idempotence comes from the same
    place: the primary key (source_dataset, neighbourhood_code) declared on the
    table. The dataset is part of that key because the two files number their
    neighbourhoods independently and both start at 1 -- without it, the
    sociological neighbourhood 40 would overwrite housing-reference 40.
    """
    features = list(features)
    if not features:
        return LoadResult(0, 0)

    with conn.cursor() as cur:
        cur.execute(
            NEIGHBOURHOOD_UPSERT_SQL,
            {
                "source_dataset": source_dataset,
                "source_crs": source_crs,
                "neighbourhood_code": [f.neighbourhood_code for f in features],
                "neighbourhood_name": [f.neighbourhood_name for f in features],
                "borough_code": [f.borough_code for f in features],
                "borough_name_source": [f.borough_name_source for f in features],
                "municipality_name_source": [f.municipality_name_source for f in features],
                "properties_json": [f.properties_json for f in features],
                "geometry_geojson": [f.geometry_geojson for f in features],
            },
        )
        outcomes = [row[0] for row in cur.fetchall()]

    inserted = sum(1 for was_inserted in outcomes if was_inserted)
    return LoadResult(inserted=inserted, updated=len(outcomes) - inserted)
