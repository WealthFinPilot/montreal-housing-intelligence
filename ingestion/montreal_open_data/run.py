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


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and check the file, print what would be loaded, write nothing",
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


def main(argv=None) -> int:
    args = _parse_args(argv)
    dataset = datasets.BOUNDARIES

    print(f"Dataset  : {dataset.key}")
    print(f"Licence  : {datasets.LICENCE} -- {datasets.LICENCE_URL}")

    if args.dry_run:
        features, _, crs = _fetch(dataset)
        by_type: dict[str, int] = {}
        for feature in features:
            by_type[feature.entity_type or "?"] = by_type.get(feature.entity_type or "?", 0) + 1
        print("\nDRY RUN -- nothing written. Would load:")
        for entity_type, count in sorted(by_type.items()):
            print(f"  {count:3} x {entity_type}")
        return 0

    print(f"Target   : {db.describe_target()}")
    started = time.monotonic()

    with db.connect() as conn:
        run_id = pipeline_log.start_run(conn, PIPELINE_NAME)
        # The run row is committed on its own so that a crash during the
        # download leaves evidence behind. Without this, a failed run would
        # roll back its own trace.
        conn.commit()

        try:
            features, _url, crs = _fetch(dataset)
            result = load.load_boundaries(
                conn,
                features,
                source_dataset=dataset.key,
                source_crs=crs,
            )
            pipeline_log.finish_run(
                conn,
                run_id,
                status="success",
                rows_received=len(features),
                rows_inserted=result.inserted,
                rows_updated=result.updated,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            pipeline_log.finish_run(
                conn, run_id, status="failed", error_message=f"{type(exc).__name__}: {exc}"
            )
            conn.commit()
            print(f"\nFAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

    print(f"\nOK -- {result} in {time.monotonic() - started:.1f} s")
    print(f"     {datasets.ATTRIBUTION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
