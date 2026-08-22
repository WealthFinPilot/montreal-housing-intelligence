"""Entry point: fetch Bank of Canada series and load them into raw.boc_observation.

    python -m ingestion.bank_of_canada.run
    python -m ingestion.bank_of_canada.run --dry-run
    python -m ingestion.bank_of_canada.run --start-date 2024-01-01
    python -m ingestion.bank_of_canada.run --series V39079

Needs the SSH tunnel open:  bash scripts/tunnel-start.sh

What it guarantees
------------------
* The run is recorded in raw.pipeline_run BEFORE the download starts, so a
  failed download leaves a trace instead of nothing.
* Observations are written in a single transaction: either the whole batch
  lands or none of it does. There is no half-loaded state to clean up.
* Running it a second time on unchanged data reports 0 inserted and 0 updated.
  That number comes from the database, not from a counter kept by this script.

Attribution
-----------
Data reproduced from the Bank of Canada Valet API under its terms of use,
https://www.bankofcanada.ca/terms/ . The Bank of Canada is not responsible for
any use made of this data here.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time

from ingestion.bank_of_canada import load, series, valet
from src import db

PIPELINE_NAME = "bank_of_canada_valet"


def _date(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--start-date",
        type=_date,
        default=series.HISTORY_START,
        help=f"first date to request (default {series.HISTORY_START.isoformat()})",
    )
    parser.add_argument("--end-date", type=_date, default=None, help="last date to request")
    parser.add_argument(
        "--series",
        action="append",
        dest="series_ids",
        metavar="ID",
        help="restrict to one series, repeatable (default: the whole catalogue)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and report, write nothing to the database",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    series_ids = tuple(args.series_ids) if args.series_ids else series.SERIES_IDS

    print(f"pipeline    : {PIPELINE_NAME}")
    print(f"series      : {', '.join(series_ids)}")
    for series_id in series_ids:
        try:
            definition = series.by_id(series_id)
        except KeyError:
            continue
        print(f"              {series_id} = {definition.label} ({definition.frequency})")
    print(f"from        : {args.start_date.isoformat()}"
          f"{' to ' + args.end_date.isoformat() if args.end_date else ' to today'}")

    if args.dry_run:
        fetched = valet.fetch_observations(series_ids, args.start_date, args.end_date)
        print(f"url         : {fetched.source_url}")
        print(f"received    : {len(fetched.observations)} observations")
        print("DRY RUN -- nothing written.")
        return 0

    print(f"database    : {db.describe_target()}")
    started = time.monotonic()
    conn = db.connect()
    try:
        # Recorded and committed first, so a run that dies mid-download is
        # still visible afterwards as a failure rather than as silence.
        run_id = load.start_run(conn, PIPELINE_NAME)
        conn.commit()
        print(f"run_id      : {run_id}")

        try:
            fetched = valet.fetch_observations(series_ids, args.start_date, args.end_date)
            print(f"url         : {fetched.source_url}")
            print(f"received    : {len(fetched.observations)} observations")

            result = load.load_observations(
                conn,
                fetched.observations,
                source_url=fetched.source_url,
                run_id=run_id,
            )
            load.finish_run(
                conn,
                run_id,
                status="success",
                rows_received=len(fetched.observations),
                rows_inserted=result.inserted,
                rows_updated=result.updated,
            )
            # One commit for the observations AND the run log together: the
            # numbers in the log can never disagree with the rows on disk.
            conn.commit()
        except Exception as exc:
            conn.rollback()
            load.finish_run(
                conn,
                run_id,
                status="failed",
                error_message=f"{type(exc).__name__}: {exc}"[:2000],
            )
            conn.commit()
            print(f"FAILED      : {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    finally:
        conn.close()

    print(f"loaded      : {result}")
    print(f"elapsed     : {time.monotonic() - started:.1f} s")
    print("Data reproduced under the Bank of Canada terms of use, "
          "https://www.bankofcanada.ca/terms/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
