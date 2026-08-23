"""Write Bank of Canada observations into PostgreSQL, idempotently.

This module talks to the database and nothing else: it never makes an HTTP
call. It also never commits. The caller decides when work becomes permanent,
which is what lets the test suite exercise these functions against the real
tables and roll everything back afterwards.

Where idempotence actually comes from
-------------------------------------
Not from this code. It comes from the primary key (series_id, observation_date)
declared on raw.boc_observation. A time series has exactly one value per date;
that fact is stated in the database, so a buggy script CANNOT create a
duplicate -- the database refuses it. The code below simply tells the database
what to do when it meets a key it already has.

The three outcomes of one incoming row:

    key absent          -> INSERT                     counted as inserted
    key present, value changed  -> UPDATE             counted as updated
    key present, value identical -> nothing at all    counted as neither

The third case is the interesting one. The WHERE clause on DO UPDATE means an
unchanged row is not rewritten, so updated_at keeps its meaning: it moves only
when the Bank of Canada actually revised a published figure. A pipeline rerun
on unchanged data reports 0 and 0, which is acceptance criterion 2 of J2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import psycopg

# Opening and closing a row in raw.pipeline_run is not specific to the Bank of
# Canada, so it moved to src/pipeline_log.py when the second source arrived.
# Re-exported here because callers and tests already import it from this
# module, and a rename would be churn without a reader benefit.
from src.pipeline_log import finish_run, start_run  # noqa: F401

# One statement for the whole batch.
#
# unnest() turns three parallel arrays into rows, so the entire load is a
# single round trip to the server instead of one per observation.
#
# RETURNING (xmax = 0): xmax is a hidden system column. PostgreSQL leaves it at
# zero on a freshly inserted row and non-zero on a row it just updated. It is
# therefore the database itself, not the script, that reports which of the two
# happened. Rows skipped by the WHERE clause return nothing at all.
UPSERT_SQL = """
INSERT INTO raw.boc_observation AS existing
       (series_id, observation_date, value_raw, source_url, run_id)
SELECT s, d, v, %(source_url)s, %(run_id)s
  FROM unnest(
           %(series_ids)s::text[],
           %(dates)s::date[],
           %(values)s::text[]
       ) AS incoming(s, d, v)
ON CONFLICT (series_id, observation_date) DO UPDATE
   SET value_raw  = excluded.value_raw,
       source_url = excluded.source_url,
       run_id     = excluded.run_id,
       updated_at = now()
 WHERE existing.value_raw IS DISTINCT FROM excluded.value_raw
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


def load_observations(
    conn: psycopg.Connection,
    observations,
    *,
    source_url: str,
    run_id: uuid.UUID,
) -> LoadResult:
    """Insert or refresh observations. Does not commit."""
    observations = list(observations)
    if not observations:
        return LoadResult(0, 0)

    with conn.cursor() as cur:
        cur.execute(
            UPSERT_SQL,
            {
                "series_ids": [o.series_id for o in observations],
                "dates": [o.observation_date for o in observations],
                "values": [o.value_raw for o in observations],
                "source_url": source_url,
                "run_id": run_id,
            },
        )
        outcomes = [row[0] for row in cur.fetchall()]

    inserted = sum(1 for was_inserted in outcomes if was_inserted)
    return LoadResult(inserted=inserted, updated=len(outcomes) - inserted)
