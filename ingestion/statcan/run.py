"""Entry point: fetch the Statistics Canada census files into the raw layer.

    python -m ingestion.statcan.run
    python -m ingestion.statcan.run --dry-run
    python -m ingestion.statcan.run --only statcan_income_statistics

Needs a reachable database:  bash scripts/tunnel-start.sh

WHY THE ORDER IS FIXED
----------------------
The boundary step asks the database which census tracts are on the Island, and
the attribute file is what knows that. Running the boundary step first is
refused rather than silently loading nothing, or -- worse -- loading all 6 247
Canadian tracts because the perimeter came back empty.

WHAT EACH RUN GUARANTEES
------------------------
* The run is recorded in raw.pipeline_run BEFORE the download starts, so a
  failed download leaves a trace instead of nothing.
* Everything of one step lands in one transaction, or nothing does.
* A second run on unchanged files reports 0 inserted and 0 updated, and that
  count comes from the database rather than from a counter kept here.

Attribution
-----------
Source: Statistics Canada, 2021 Census of Population. Reproduced and
distributed on an as-is basis with the permission of Statistics Canada.
Boundary file under the Open Government Licence - Canada.
"""

from __future__ import annotations

import argparse
import sys
import time

import requests

from ingestion.statcan import datasets, download, load, parse, wds
from src import db, pipeline_log


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and parse, print what would be loaded, write nothing",
    )
    parser.add_argument(
        "--only",
        choices=[step.key for step in datasets.ALL_STEPS],
        help="run a single step instead of all of them",
    )
    return parser.parse_args(argv)


def _report(dataset: datasets.Dataset, count: int) -> None:
    print(f"  parsed   : {count:,} rows")
    if dataset.expected_rows and count != dataset.expected_rows:
        # A note, not a failure. Census geography is revised between releases,
        # and the pipeline should say so rather than refuse to run. The dbt
        # tests decide what is acceptable downstream.
        print(
            f"  NOTE     : expected {dataset.expected_rows:,}. The source "
            "changed shape -- read the dbt tests before trusting anything "
            "built on this."
        )


def _series_step(conn, dataset, session: requests.Session, *, dry_run: bool):
    """Fetch, parse and load one WDS series.

    Split from _step because the transport is not a file: nothing is
    downloaded or unzipped, and the checks that matter are on the coordinate
    rather than on a filename -- see wds.py.
    """
    response = wds.fetch_series(dataset, session=session)
    print(f"  source   : {response.source_url}")
    print(f"  vector   : {response.vector_id}  ({dataset.geo_name}, {dataset.product_name})")
    print(f"  unit     : {response.uom_code} = {response.uom}")
    print(f"  published: up to {response.cube_end_date}")

    records = parse.cpi_observations(response, dataset)
    print(f"  parsed   : {len(records):,} monthly observations")
    if len(records) < dataset.expected_min_rows:
        # A note, not a failure: a living series grows, it does not shrink.
        # Shrinking means the range came back short, which is worth saying.
        print(
            f"  NOTE     : expected at least {dataset.expected_min_rows:,}. "
            "The range came back shorter than when this was catalogued."
        )

    _report_series_quality(records)

    if dry_run:
        return len(records), None
    return len(records), load.load_cpi(
        conn, records, source_file=response.source_url
    )


def _report_series_quality(records) -> None:
    """Say out loud what the codes assert, instead of averaging them silently.

    Every point retrieved on 2026-08-31 carried status 0 and symbol 0. This
    prints anything that does not, because a preliminary or revised index is
    a figure the source expects to change, and a downstream quarterly average
    would absorb it without a word.
    """
    odd = [r for r in records if r.status_code != "0" or r.symbol_code != "0"]
    empty = [r for r in records if not r.value]
    print(f"  codes    : {len(records) - len(odd):,} normal, {len(odd):,} flagged, {len(empty):,} with no value")
    for record in odd[:5]:
        print(
            f"             {record.ref_period}: status {record.status_code}, "
            f"symbol {record.symbol_code}"
        )


def _step(conn, dataset: datasets.Dataset, session: requests.Session, *, dry_run: bool):
    """Fetch, parse and load one dataset. Returns (rows_parsed, LoadResult)."""
    if isinstance(dataset, datasets.SeriesDataset):
        return _series_step(conn, dataset, session, dry_run=dry_run)

    payload, url = download.fetch(dataset, session=session)
    print(f"  source   : {url}")
    print(f"  bytes    : {len(payload):,}")

    if dataset.key == datasets.GEOGRAPHIC_ATTRIBUTE.key:
        records = parse.island_blocks(payload)
        _report(dataset, len(records))
        if dry_run:
            return len(records), None
        return len(records), load.load_blocks(conn, records, source_file=url)

    if dataset.key == datasets.INCOME.key:
        records = parse.cma_income_rows(payload)
        _report(dataset, len(records))
        _check_cube_shape(records)
        if dry_run:
            return len(records), None
        return len(records), load.load_income(conn, records, source_file=url)

    if dataset.key == datasets.CENSUS_TRACT_BOUNDARIES.key:
        wanted = load.island_tract_uids(conn)
        if not wanted:
            raise RuntimeError(
                "raw.statcan_geographic_attribute holds no census tract, so "
                "the Island perimeter is unknown. Load "
                f"{datasets.GEOGRAPHIC_ATTRIBUTE.key} first."
            )
        print(f"  perimeter: {len(wanted):,} census tracts, from the attribute file")
        records = parse.tract_boundaries(payload, wanted)
        _report(dataset, len(records))
        if dry_run:
            return len(records), None
        return len(records), load.load_boundaries(
            conn, records, source_srid=datasets.BOUNDARY_SRID, source_file=url
        )

    raise ValueError(f"no step is defined for {dataset.key}")


def _check_cube_shape(records) -> None:
    """Every geography must carry exactly 77 rows.

    Cheap, and it catches the one failure mode the primary key cannot: a
    re-worded dimension label would insert a new row instead of updating the
    existing one, leaving a geography with 78. Reported here, and asserted
    again by dbt so it cannot be skipped by loading with --only.
    """
    counts: dict[str, int] = {}
    for record in records:
        counts[record.dguid] = counts.get(record.dguid, 0) + 1
    wrong = {g: n for g, n in counts.items() if n != parse.ROWS_PER_GEOGRAPHY}
    print(f"  cube     : {len(counts):,} geographies x {parse.ROWS_PER_GEOGRAPHY} rows")
    if wrong:
        raise RuntimeError(
            f"{len(wrong)} geographies do not carry "
            f"{parse.ROWS_PER_GEOGRAPHY} rows, for example "
            f"{list(wrong.items())[:3]}. A dimension label has probably been "
            "re-worded, which would silently create rows instead of updating "
            "them."
        )


def main(argv=None) -> int:
    args = _parse_args(argv)
    selected = (
        [datasets.BY_KEY[args.only]] if args.only else list(datasets.ALL_STEPS)
    )

    print(f"Licences : {datasets.STATCAN_LICENCE} -- {datasets.STATCAN_LICENCE_URL}")
    print(f"           {datasets.OGL_LICENCE} -- {datasets.OGL_LICENCE_URL}")
    print(f"Target   : {db.describe_target()}")

    session = requests.Session()
    started = time.monotonic()
    failures = 0

    for dataset in selected:
        print(f"\n{dataset.key}")
        print(f"  title    : {dataset.title}")

        with db.connect() as conn:
            if args.dry_run:
                try:
                    _step(conn, dataset, session, dry_run=True)
                    print("  DRY RUN  -- nothing written")
                except Exception as exc:
                    failures += 1
                    print(f"  FAILED   : {type(exc).__name__}: {exc}", file=sys.stderr)
                continue

            run_id = pipeline_log.start_run(conn, dataset.key)
            # Committed on its own so a crash during the download leaves
            # evidence behind instead of rolling back its own trace.
            conn.commit()
            try:
                received, result = _step(conn, dataset, session, dry_run=False)
                pipeline_log.finish_run(
                    conn,
                    run_id,
                    status="success",
                    rows_received=received,
                    rows_inserted=result.inserted,
                    rows_updated=result.updated,
                )
                conn.commit()
                print(f"  loaded   : {result}")
            except Exception as exc:
                conn.rollback()
                pipeline_log.finish_run(
                    conn,
                    run_id,
                    status="failed",
                    error_message=f"{type(exc).__name__}: {exc}",
                )
                conn.commit()
                failures += 1
                print(f"  FAILED   : {type(exc).__name__}: {exc}", file=sys.stderr)

    elapsed = time.monotonic() - started
    print(f"\n{'FAILED' if failures else 'OK'} -- {len(selected)} step(s) in {elapsed:.1f} s")
    print(f"     {datasets.ATTRIBUTION}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
