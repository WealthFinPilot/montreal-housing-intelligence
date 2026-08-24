"""Write Statistics Canada records into the raw layer, idempotently. No HTTP.

Same contract as the three loaders before it: this module never commits. The
caller decides when work becomes permanent, which is what lets the tests run
against the real tables and roll back afterwards.

Idempotence does not come from this code. It comes from the primary keys
declared in sql/bootstrap/07_statcan.sql -- one block, one row; one cube cell,
one row; one tract, one row -- stated in the database, so a buggy script
cannot duplicate them. The WHERE clause on DO UPDATE is what keeps updated_at
meaningful: a rerun against an unchanged file rewrites nothing and reports
0 inserted, 0 updated.

WHY THIS ONE STAGES THROUGH A TEMPORARY TABLE
---------------------------------------------
The earlier loaders pass one array per column into unnest(), which reads well
for 34 boundaries and 3 629 rates. Here the income table alone is 77 385 rows
of 18 columns, and that shape would mean 18 parallel arrays whose only
guarantee of staying aligned is that nobody miscounts a comma.

So the rows are COPYed into a scratch table first -- COPY is the fast path
into PostgreSQL, and it keeps each row whole -- and merged from there in one
statement. The merge is ordinary SQL a reader can follow, and the arithmetic
of what was inserted versus updated still comes from the database rather than
from a counter kept here.

A duplicate key inside one batch makes the merge fail with "cannot affect row
a second time". That is the desired outcome: it means the source shipped the
same identifier twice, which is a fact about the source, not something to
quietly de-duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import psycopg

from ingestion.statcan import parse


@dataclass(frozen=True)
class LoadResult:
    inserted: int
    updated: int

    @property
    def total(self) -> int:
        return self.inserted + self.updated

    def __str__(self) -> str:
        return f"{self.inserted} inserted, {self.updated} updated"


def _merge(
    conn: psycopg.Connection,
    *,
    table: str,
    key_columns: Sequence[str],
    data_columns: Sequence[str],
    rows: Iterable[Sequence[object]],
) -> LoadResult:
    """COPY rows into a scratch table, then merge them into `table`."""
    all_columns = list(key_columns) + list(data_columns)
    scratch = "incoming_" + table.split(".")[-1]
    column_list = ", ".join(all_columns)

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {scratch}")
        cur.execute(
            f"CREATE TEMP TABLE {scratch} AS "
            f"SELECT {column_list} FROM {table} WITH NO DATA"
        )

        copied = 0
        with cur.copy(f"COPY {scratch} ({column_list}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
                copied += 1

        if copied == 0:
            return LoadResult(0, 0)

        assignments = ", ".join(f"{c} = excluded.{c}" for c in data_columns)
        existing_tuple = ", ".join(f"existing.{c}" for c in data_columns)
        excluded_tuple = ", ".join(f"excluded.{c}" for c in data_columns)

        cur.execute(
            f"""
            INSERT INTO {table} AS existing ({column_list})
            SELECT {column_list} FROM {scratch}
            ON CONFLICT ({", ".join(key_columns)}) DO UPDATE
               SET {assignments}, updated_at = now()
             WHERE ({existing_tuple}) IS DISTINCT FROM ({excluded_tuple})
            RETURNING (xmax = 0) AS was_inserted
            """
        )
        outcomes = [row[0] for row in cur.fetchall()]

    inserted = sum(1 for was_inserted in outcomes if was_inserted)
    return LoadResult(inserted=inserted, updated=len(outcomes) - inserted)


# --------------------------------------------------------------------------


BLOCK_DATA_COLUMNS = (
    "db_dguid", "da_uid", "ct_uid", "ct_dguid", "ct_name",
    "cma_uid", "cma_name", "csd_uid", "csd_name", "csd_type",
    "cd_uid", "pr_uid",
    "population_2021", "total_dwellings_2021", "usual_resident_dwellings_2021",
    "land_area_km2",
    "da_lambert_x", "da_lambert_y", "da_latitude", "da_longitude",
    "source_file",
)


def load_blocks(
    conn: psycopg.Connection,
    blocks: Iterable[parse.BlockRecord],
    *,
    source_file: str,
) -> LoadResult:
    return _merge(
        conn,
        table="raw.statcan_geographic_attribute",
        key_columns=("db_uid",),
        data_columns=BLOCK_DATA_COLUMNS,
        rows=(
            (
                b.db_uid,
                b.db_dguid, b.da_uid, b.ct_uid, b.ct_dguid, b.ct_name,
                b.cma_uid, b.cma_name, b.csd_uid, b.csd_name, b.csd_type,
                b.cd_uid, b.pr_uid,
                b.population_2021, b.total_dwellings_2021,
                b.usual_resident_dwellings_2021, b.land_area_km2,
                b.da_lambert_x, b.da_lambert_y, b.da_latitude, b.da_longitude,
                source_file,
            )
            for b in blocks
        ),
    )


INCOME_DATA_COLUMNS = (
    "ref_date", "geo_name", "coordinate",
    "households_2021", "households_2021_symbol",
    "households_2016", "households_2016_symbol",
    "median_total_income_2020", "median_total_income_2020_symbol",
    "median_total_income_2015", "median_total_income_2015_symbol",
    "median_aftertax_income_2020", "median_aftertax_income_2020_symbol",
    "median_aftertax_income_2015", "median_aftertax_income_2015_symbol",
    "source_file",
)


def load_income(
    conn: psycopg.Connection,
    rows: Iterable[parse.IncomeRecord],
    *,
    source_file: str,
) -> LoadResult:
    def measures(record: parse.IncomeRecord):
        for key, _ in parse.MEASURES:
            yield record.values[key]
            yield record.symbols[key]

    return _merge(
        conn,
        table="raw.statcan_income_statistic",
        key_columns=("dguid", "household_size", "household_type"),
        data_columns=INCOME_DATA_COLUMNS,
        rows=(
            (
                r.dguid, r.household_size, r.household_type,
                r.ref_date, r.geo_name, r.coordinate,
                *measures(r),
                source_file,
            )
            for r in rows
        ),
    )


BOUNDARY_DATA_COLUMNS = (
    "dguid", "ct_name", "pr_uid", "land_area_km2",
    "geometry_wkt", "source_srid", "source_file",
)


def load_boundaries(
    conn: psycopg.Connection,
    boundaries: Iterable[parse.BoundaryRecord],
    *,
    source_srid: int,
    source_file: str,
) -> LoadResult:
    return _merge(
        conn,
        table="raw.statcan_census_tract_boundary",
        key_columns=("ct_uid",),
        data_columns=BOUNDARY_DATA_COLUMNS,
        rows=(
            (
                b.ct_uid,
                b.dguid, b.ct_name, b.pr_uid, b.land_area_km2,
                b.geometry_wkt, source_srid, source_file,
            )
            for b in boundaries
        ),
    )


def island_tract_uids(conn: psycopg.Connection) -> set[str]:
    """The census tracts the attribute file places on the Island.

    Read from the database rather than recomputed, so the boundary step and
    the attribute step cannot disagree about the perimeter. It also makes the
    ordering explicit: without the attribute file loaded, there is no Island.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT ct_uid FROM raw.statcan_geographic_attribute "
            "WHERE ct_uid <> ''"
        )
        return {row[0] for row in cur.fetchall()}
