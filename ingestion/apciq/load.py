"""Write Baromètre observations into PostgreSQL, idempotently. No PDF here.

Same contract as the other loaders: this module never commits, so the tests
can run against the real tables inside a transaction and roll it back.

Idempotence comes from the primary key on raw.apciq_barometer_statistic, not
from this code. The WHERE clause on DO UPDATE is what keeps updated_at
honest -- reloading an unchanged PDF rewrites nothing and reports 0 inserted,
0 updated, and that count comes from the database rather than from a counter
kept here.

There is a real reason to expect updates rather than only inserts: APCIQ
revises. An edition republished after a correction carries the same primary
key with a different figure, and updated_at is then the only trace that the
number moved. Nothing here keeps the previous value -- the same limitation
accepted for Bank of Canada revisions in J2, and for the same reason: this
project analyses the market, it does not audit its publishers.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from ingestion.apciq.parse import Observation

UPSERT_SQL = """
INSERT INTO raw.apciq_barometer_statistic AS existing
       (edition_year, edition_quarter, area_code, property_category,
        metric_code, period_code, value_text, change_percent_text,
        source_area_label, source_category_label, source_metric_label,
        source_pdf, source_page)
SELECT %(edition_year)s, %(edition_quarter)s, a, c, m, p, v, ch, al, cl, ml,
       %(source_pdf)s, pg
  FROM unnest(
           %(area_code)s::text[],
           %(property_category)s::text[],
           %(metric_code)s::text[],
           %(period_code)s::text[],
           %(value_text)s::text[],
           %(change_percent_text)s::text[],
           %(source_area_label)s::text[],
           %(source_category_label)s::text[],
           %(source_metric_label)s::text[],
           %(source_page)s::int[]
       ) AS incoming(a, c, m, p, v, ch, al, cl, ml, pg)
ON CONFLICT (edition_year, edition_quarter, area_code, property_category,
             metric_code, period_code) DO UPDATE
   SET value_text            = excluded.value_text,
       change_percent_text   = excluded.change_percent_text,
       source_area_label     = excluded.source_area_label,
       source_category_label = excluded.source_category_label,
       source_metric_label   = excluded.source_metric_label,
       source_pdf            = excluded.source_pdf,
       source_page           = excluded.source_page,
       updated_at            = now()
 WHERE (existing.value_text, existing.change_percent_text,
        existing.source_area_label, existing.source_category_label,
        existing.source_metric_label, existing.source_pdf, existing.source_page)
    IS DISTINCT FROM
       (excluded.value_text, excluded.change_percent_text,
        excluded.source_area_label, excluded.source_category_label,
        excluded.source_metric_label, excluded.source_pdf, excluded.source_page)
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

    def __add__(self, other: "LoadResult") -> "LoadResult":
        return LoadResult(self.inserted + other.inserted, self.updated + other.updated)


def load_observations(
    conn: psycopg.Connection,
    observations: list[Observation],
    *,
    source_pdf: str,
) -> LoadResult:
    """Insert or refresh one edition's observations. Does not commit.

    All observations must come from the same edition: the year and quarter are
    passed once, as scalars, rather than repeated on every row. Mixing two
    editions in one call would silently file the second under the first.
    """
    if not observations:
        return LoadResult(0, 0)

    editions = {(o.edition_year, o.edition_quarter) for o in observations}
    if len(editions) != 1:
        raise ValueError(f"one edition per call, got {sorted(editions)}")
    (year, quarter), = editions

    with conn.cursor() as cur:
        cur.execute(
            UPSERT_SQL,
            {
                "edition_year": year,
                "edition_quarter": quarter,
                "source_pdf": source_pdf,
                "area_code": [o.area_code for o in observations],
                "property_category": [o.property_category for o in observations],
                "metric_code": [o.metric_code for o in observations],
                "period_code": [o.period_code for o in observations],
                "value_text": [o.value_text for o in observations],
                "change_percent_text": [o.change_percent_text for o in observations],
                "source_area_label": [o.source_area_label for o in observations],
                "source_category_label": [o.source_category_label for o in observations],
                "source_metric_label": [o.source_metric_label for o in observations],
                "source_page": [o.source_page for o in observations],
            },
        )
        outcomes = [row[0] for row in cur.fetchall()]

    inserted = sum(1 for was_inserted in outcomes if was_inserted)
    return LoadResult(inserted=inserted, updated=len(outcomes) - inserted)
