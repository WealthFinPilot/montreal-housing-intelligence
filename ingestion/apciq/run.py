"""Entry point: archive the Baromètre PDFs, read them, load the raw layer.

    python -m ingestion.apciq.run                 every quarter since 2019 Q2
    python -m ingestion.apciq.run --dry-run       fetch and parse, write nothing
    python -m ingestion.apciq.run --only 2026Q2   one edition
    python -m ingestion.apciq.run --force         re-download what is cached

Needs a reachable database (except with --dry-run):
    bash scripts/tunnel-start.sh

WHAT THIS GUARANTEES
--------------------
* The run is recorded in raw.pipeline_run BEFORE the first download, so a run
  that dies mid-way leaves a trace rather than nothing.
* Every PDF is archived on first fetch and read from disk afterwards. The
  series survives the source reorganising.
* A gap inside the series is refused. A missing quarter at the END is normal --
  APCIQ publishes a few weeks after the quarter closes.
* 47 control totals run on every edition, and their verdicts are LOADED, not
  just printed -- see sql/bootstrap/06_apciq_control_total.sql.
* What stops the load is an edition this code cannot read. An edition it reads
  correctly whose own figures do not add up is loaded, with the failed control
  beside it. Four of the 29 archived editions are in that case, and refusing
  them would have destroyed 3 420 figures -- most of them sound -- along with
  the only evidence of the defect.
* Everything lands in one transaction, or nothing does.
* A second run over unchanged PDFs reports 0 inserted and 0 updated, counted
  by the database rather than by this script.

Attribution: Source : APCIQ par le système Centris.
Redistribution of these figures is forbidden -- see editions.py.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

from ingestion.apciq import download, editions, load, parse
from src import db, pipeline_log

PIPELINE_NAME = "apciq_barometer"
ONLY_RE = re.compile(r"^(\d{4})Q([1-4])$", re.IGNORECASE)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="download, parse and run the control totals; write nothing",
    )
    parser.add_argument(
        "--only",
        metavar="YYYYQn",
        help="restrict to one edition, e.g. 2026Q2",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-download editions already archived on disk",
    )
    return parser.parse_args(argv)


def _selected_editions(only: str | None, today: date) -> list[editions.Edition]:
    candidates = editions.candidate_editions(today)
    if only is None:
        return candidates
    match = ONLY_RE.match(only.strip())
    if not match:
        raise SystemExit(f"--only expects YYYYQn, e.g. 2026Q2 (got {only!r})")
    wanted = editions.Edition(int(match.group(1)), int(match.group(2)))
    if wanted not in candidates:
        raise SystemExit(
            f"{wanted} is outside the archive: it runs from "
            f"{editions.Edition(*editions.FIRST_EDITION)} to {candidates[-1]}"
        )
    return [wanted]


def _archive(chosen: list[editions.Edition], *, force: bool) -> list[download.ArchiveEntry]:
    archive_dir = REPO_ROOT / editions.ARCHIVE_DIR
    session = requests.Session()
    entries = download.ensure_archived(
        chosen,
        archive_dir,
        session=session,
        force=force,
        on_progress=lambda entry: print(f"  {entry}"),
    )
    download.check_no_hole(entries)
    return entries


def _read(entry: download.ArchiveEntry) -> parse.EditionReading:
    """Read one archived edition and report what its controls said.

    A failed control is printed in full rather than summarised. It is the one
    thing in this output somebody has to act on -- and the difference between
    a sector total that misses by a fraction of a percent and one that
    misses by nearly half is the whole point.
    """
    assert entry.path is not None
    reading = parse.read_edition(entry.path, entry.edition)
    print(f"  {reading}")
    for control in reading.failed_controls:
        print(f"      {control}")
    return reading


def main(argv=None) -> int:
    args = _parse_args(argv)
    chosen = _selected_editions(args.only, date.today())

    print(f"Source   : {editions.BASE_URL}")
    print(f"Licence  : reproduction forbidden without written consent "
          f"-- {editions.LICENCE_URL}")
    print(f"Editions : {len(chosen)} candidates, {chosen[0]} to {chosen[-1]}")
    print("\nArchive:")
    entries = [e for e in _archive(chosen, force=args.force) if e.path is not None]

    print("\nRead and control:")
    parsed = [(entry, _read(entry)) for entry in entries]
    total_rows = sum(len(reading.observations) for _, reading in parsed)
    total_controls = sum(len(reading.controls) for _, reading in parsed)
    off = [(entry.edition, control)
           for entry, reading in parsed
           for control in reading.failed_controls]

    print(f"\n{total_controls} controls run over {len(parsed)} editions, "
          f"{len(off)} of them OFF"
          + (f" -- on {len({e for e, _ in off})} edition(s): "
             f"{', '.join(str(e) for e in sorted({e for e, _ in off}))}"
             if off else ""))

    if args.dry_run:
        print(f"\nDRY RUN -- nothing written. Would load {total_rows} figures "
              f"and {total_controls} control results from {len(parsed)} editions.")
        return 0

    print(f"\nTarget   : {db.describe_target()}")
    started = time.monotonic()
    result = load.LoadResult(0, 0)
    controls = load.LoadResult(0, 0)

    with db.connect() as conn:
        run_id = pipeline_log.start_run(conn, PIPELINE_NAME)
        # Committed on its own so a crash later still leaves evidence.
        conn.commit()
        try:
            for entry, reading in parsed:
                # The figures and the verdict on the figures, in one
                # transaction. Either both are in the database or neither is.
                result = result + load.load_observations(
                    conn, reading.observations, source_pdf=entry.edition.filename
                )
                controls = controls + load.load_control_totals(
                    conn, reading.controls
                )
            pipeline_log.finish_run(
                conn,
                run_id,
                status="success",
                rows_received=total_rows + total_controls,
                rows_inserted=result.inserted + controls.inserted,
                rows_updated=result.updated + controls.updated,
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

    print(f"\nOK -- figures: {result}; controls: {controls} "
          f"-- in {time.monotonic() - started:.1f} s")
    if off:
        print(f"     {len(off)} control(s) OFF are now in "
              f"raw.apciq_control_total. Nothing downstream may present those "
              f"edition/metric pairs without saying so.")
    print(f"     {editions.ATTRIBUTION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
