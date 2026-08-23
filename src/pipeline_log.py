"""Opening and closing a row in raw.pipeline_run.

Section 36 of the original brief requires every automated task to record
pipeline_name, run_id, started_at, finished_at, rows_received, rows_loaded,
status and error_message. That is one behaviour, shared by every source, so it
lives here rather than being copied into each ingestion package -- which is
what would have happened the moment a second source appeared.

Lifted out of ingestion/bank_of_canada/load.py on 2026-08-23, unchanged. That
module still re-exports both functions, so nothing that imported them from
there had to move.

Neither function commits. The caller decides when work becomes permanent.
"""

from __future__ import annotations

import uuid

import psycopg


def start_run(conn: psycopg.Connection, pipeline_name: str) -> uuid.UUID:
    """Open a run and return its identifier.

    Called BEFORE fetching anything, so a run that dies during the download is
    still on record instead of leaving no trace at all.
    """
    run_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw.pipeline_run (run_id, pipeline_name, started_at, status)"
            " VALUES (%s, %s, now(), 'running')",
            (run_id, pipeline_name),
        )
    return run_id


def finish_run(
    conn: psycopg.Connection,
    run_id: uuid.UUID,
    *,
    status: str,
    rows_received: int | None = None,
    rows_inserted: int | None = None,
    rows_updated: int | None = None,
    error_message: str | None = None,
) -> None:
    """Close a run. rows_loaded is not passed: the database computes it."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE raw.pipeline_run"
            "   SET finished_at = now(), status = %s, rows_received = %s,"
            "       rows_inserted = %s, rows_updated = %s, error_message = %s"
            " WHERE run_id = %s",
            (status, rows_received, rows_inserted, rows_updated, error_message, run_id),
        )
