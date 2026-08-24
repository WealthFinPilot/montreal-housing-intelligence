"""Entry point: fetch Montréal boundary files and load them into the raw layer.

    python -m ingestion.montreal_open_data.run
    python -m ingestion.montreal_open_data.run --dry-run

Needs a reachable database:  bash scripts/tunnel-start.sh

What it guarantees
------------------
* The run is recorded in raw.pipeline_run BEFORE the download starts, so a
  failed download leaves a trace instead of nothing.
* The projection is verified before anything is written. This dataset also
  publishes a NAD83 variant whose coordinates are metres, and loading it would
  produce valid-looking rows on which every spatial join returns nothing --
  the kind of failure that surfaces three weeks later in a dashboard.
* Everything lands in one transaction, or nothing does.
* A second run on an unchanged file reports 0 inserted and 0 updated, and that
  count comes from the database rather than from a counter kept here.

Attribution
-----------
Contains information licensed under the Creative Commons Attribution 4.0
International licence by Ville de Montréal.
http://creativecommons.org/licenses/by/4.0/
"""

from __future__ import annotations

import argparse
import sys
import time

import requests

from ingestion.montreal_open_data import ckan, datasets, load
from src import db, pipeline_log

PIPELINE_NAME = "montreal_open_data_boundaries"
NEIGHBOURHOOD_PIPELINE_NAME = "montreal_open_data_neighbourhoods"

# What --only accepts, and what running with no flag does: everything.
BOUNDARY_KEY = datasets.BOUNDARIES.key
ALL_KEYS = (BOUNDARY_KEY,) + tuple(d.key for d in datasets.NEIGHBOURHOOD_DATASETS)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and check the file, print what would be loaded, write nothing",
    )
    parser.add_argument(
        "--only",
        metavar="KEY",
        choices=ALL_KEYS,
        help=f"load a single dataset. One of: {', '.join(ALL_KEYS)}",
    )
    return parser.parse_args(argv)


def _fetch(dataset: datasets.Dataset) -> tuple[list[ckan.BoundaryFeature], str, str]:
    """Resolve, download, verify. Returns the features, the URL and the CRS."""
    session = requests.Session()
    url = ckan.resolve_resource_url(dataset, session=session)
    print(f"  resource : {url}")

    document = ckan.fetch_geojson(url, session=session)
    crs = ckan.check_crs(document)
    print(f"  crs      : {crs}  (checked, not assumed)")

    features = ckan.features_from(document)
    print(f"  features : {len(features)}")
    if dataset.expected_features and len(features) != dataset.expected_features:
        # A warning, not a failure. The island's political geography does
        # change -- boroughs have merged before -- and the pipeline should
        # report that, not refuse to run. The dbt tests decide what is
        # acceptable downstream.
        print(
            f"  NOTE     : expected {dataset.expected_features} features. "
            "The source changed shape -- check the dbt tests before trusting "
            "anything built on this."
        )
    return features, url, crs


def _fetch_neighbourhoods(dataset):
    """Resolve, download, verify a neighbourhood file.

    The same three steps as _fetch, and the middle one matters just as much
    here: both neighbourhood files are published in CRS84, and this project has
    already paid once for loading a lookalike whose coordinates were metres.
    """
    session = requests.Session()
    url = ckan.resolve_resource_url(dataset, session=session)
    print(f"  resource : {url}")

    document = ckan.fetch_geojson(url, session=session)
    crs = ckan.check_crs(document)
    print(f"  crs      : {crs}  (checked, not assumed)")

    features = ckan.neighbourhoods_from(document, dataset)
    print(f"  features : {len(features)}")
    if dataset.expected_features and len(features) != dataset.expected_features:
        print(
            f"  NOTE     : expected {dataset.expected_features} features. "
            "The source changed shape -- check the dbt tests before trusting "
            "anything built on this."
        )
    return features, url, crs


def _load_one(conn, *, pipeline_name, label, fetch, write) -> load.LoadResult:
    """One dataset, from its own pipeline_run row to its own commit.

    Each dataset gets its own run row rather than sharing one. That is what
    lets a later reader see that the boundaries loaded and the neighbourhoods
    failed, instead of a single verdict covering both.

    The run row is committed before the download starts, so a crash mid-download
    leaves a trace instead of rolling away its own evidence.
    """
    print()
    print(f"Dataset  : {label}")
    run_id = pipeline_log.start_run(conn, pipeline_name)
    conn.commit()
    try:
        features, _url, crs = fetch()
        result = write(features, crs)
        pipeline_log.finish_run(
            conn,
            run_id,
            status="success",
            rows_received=len(features),
            rows_inserted=result.inserted,
            rows_updated=result.updated,
        )
        conn.commit()
        print(f"  loaded   : {result}")
        return result
    except Exception as exc:
        conn.rollback()
        pipeline_log.finish_run(
            conn, run_id, status="failed", error_message=f"{type(exc).__name__}: {exc}"
        )
        conn.commit()
        raise


def main(argv=None) -> int:
    args = _parse_args(argv)
    selected = (args.only,) if args.only else ALL_KEYS

    print(f"Licence  : {datasets.LICENCE} -- {datasets.LICENCE_URL}")

    if args.dry_run:
        print()
        print("DRY RUN -- nothing written.")
        for key in selected:
            if key == BOUNDARY_KEY:
                print()
                print(f"Dataset  : {key}")
                features, _, _ = _fetch(datasets.BOUNDARIES)
                by_type: dict[str, int] = {}
                for feature in features:
                    name = feature.entity_type or "?"
                    by_type[name] = by_type.get(name, 0) + 1
                for entity_type, count in sorted(by_type.items()):
                    print(f"    {count:3} x {entity_type}")
            else:
                dataset = next(d for d in datasets.NEIGHBOURHOOD_DATASETS if d.key == key)
                print()
                print(f"Dataset  : {key}")
                features, _, _ = _fetch_neighbourhoods(dataset)
                with_code = sum(1 for f in features if f.borough_code)
                print(f"    {with_code} of {len(features)} carry a published borough code")
        return 0

    print(f"Target   : {db.describe_target()}")
    started = time.monotonic()

    with db.connect() as conn:
        try:
            for key in selected:
                if key == BOUNDARY_KEY:
                    dataset = datasets.BOUNDARIES
                    _load_one(
                        conn,
                        pipeline_name=PIPELINE_NAME,
                        label=dataset.key,
                        fetch=lambda d=dataset: _fetch(d),
                        write=lambda features, crs, d=dataset: load.load_boundaries(
                            conn, features, source_dataset=d.key, source_crs=crs
                        ),
                    )
                else:
                    dataset = next(d for d in datasets.NEIGHBOURHOOD_DATASETS if d.key == key)
                    _load_one(
                        conn,
                        pipeline_name=NEIGHBOURHOOD_PIPELINE_NAME,
                        label=dataset.key,
                        fetch=lambda d=dataset: _fetch_neighbourhoods(d),
                        write=lambda features, crs, d=dataset: load.load_neighbourhoods(
                            conn, features, source_dataset=d.key, source_crs=crs
                        ),
                    )
        except Exception as exc:
            print(file=sys.stderr)
            print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

    print()
    print(f"OK -- {len(selected)} dataset(s) in {time.monotonic() - started:.1f} s")
    print(f"     {datasets.ATTRIBUTION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
