"""Database tests for the Bank of Canada loader.

These are the tests that prove acceptance criterion 2 of milestone J2:
"the ingestion pipeline run twice in a row leaves the same number of rows".

Every test runs inside a transaction that is rolled back (see conftest.py), so
they work against the real tables without leaving anything behind.

Requires the SSH tunnel:  bash scripts/tunnel-start.sh
"""

from __future__ import annotations

import datetime as dt
import uuid

import psycopg
import pytest

from ingestion.bank_of_canada import load, valet

pytestmark = pytest.mark.db

SOURCE_URL = "https://www.bankofcanada.ca/valet/observations/TEST/json"
PIPELINE = "pytest_bank_of_canada"


@pytest.fixture
def sample_rows(valet_payload):
    return valet.parse_observations(valet_payload)


@pytest.fixture
def clean_slate(db_connection, sample_rows):
    """Remove the rows this test is about, so counts are deterministic.

    Safe because the whole transaction is rolled back: production rows come
    back untouched the moment the test ends.
    """
    keys = [(r.series_id, r.observation_date) for r in sample_rows]
    with db_connection.cursor() as cur:
        cur.executemany(
            "DELETE FROM raw.boc_observation WHERE series_id = %s AND observation_date = %s",
            keys,
        )
    return db_connection


# --- The run log ------------------------------------------------------------

def test_start_run_records_a_running_pipeline(clean_slate):
    conn = clean_slate
    run_id = load.start_run(conn, PIPELINE)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pipeline_name, status, finished_at FROM raw.pipeline_run WHERE run_id = %s",
            (run_id,),
        )
        name, status, finished_at = cur.fetchone()
    assert (name, status, finished_at) == (PIPELINE, "running", None)


def test_finish_run_computes_rows_loaded_in_the_database(clean_slate):
    conn = clean_slate
    run_id = load.start_run(conn, PIPELINE)
    load.finish_run(conn, run_id, status="success", rows_received=14, rows_inserted=11, rows_updated=3)
    with conn.cursor() as cur:
        cur.execute("SELECT status, rows_loaded FROM raw.pipeline_run WHERE run_id = %s", (run_id,))
        status, rows_loaded = cur.fetchone()
    # rows_loaded is a generated column: the database computes 11 + 3 itself,
    # so the script cannot report a total that disagrees with its own detail.
    assert (status, rows_loaded) == ("success", 14)


def test_a_failed_run_keeps_its_error_message(clean_slate):
    conn = clean_slate
    run_id = load.start_run(conn, PIPELINE)
    load.finish_run(conn, run_id, status="failed", error_message="boom")
    with conn.cursor() as cur:
        cur.execute("SELECT status, error_message FROM raw.pipeline_run WHERE run_id = %s", (run_id,))
        assert cur.fetchone() == ("failed", "boom")


# --- Idempotence: the point of the whole exercise ---------------------------

def test_first_load_inserts_every_observation(clean_slate, sample_rows):
    conn = clean_slate
    run_id = load.start_run(conn, PIPELINE)
    result = load.load_observations(conn, sample_rows, source_url=SOURCE_URL, run_id=run_id)
    assert (result.inserted, result.updated) == (14, 0)


def test_second_identical_load_changes_nothing(clean_slate, sample_rows):
    """Acceptance criterion 2, stated as a test."""
    conn = clean_slate
    run_id = load.start_run(conn, PIPELINE)

    load.load_observations(conn, sample_rows, source_url=SOURCE_URL, run_id=run_id)
    second = load.load_observations(conn, sample_rows, source_url=SOURCE_URL, run_id=run_id)

    assert (second.inserted, second.updated) == (0, 0)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM raw.boc_observation WHERE series_id IN ('V39079', 'V80691335')"
            " AND observation_date BETWEEN %s AND %s",
            (dt.date(2026, 7, 1), dt.date(2026, 7, 15)),
        )
        assert cur.fetchone()[0] == 14


def test_an_unchanged_row_is_not_even_touched(clean_slate, sample_rows):
    """Re-running must not bump updated_at on rows whose value did not move.

    Without this, every run would rewrite every row and updated_at would stop
    meaning "the Bank of Canada revised this figure".
    """
    conn = clean_slate
    run_id = load.start_run(conn, PIPELINE)
    load.load_observations(conn, sample_rows, source_url=SOURCE_URL, run_id=run_id)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT updated_at FROM raw.boc_observation"
            " WHERE series_id = 'V39079' AND observation_date = %s",
            (dt.date(2026, 7, 1),),
        )
        before = cur.fetchone()[0]

    load.load_observations(conn, sample_rows, source_url=SOURCE_URL, run_id=run_id)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT updated_at FROM raw.boc_observation"
            " WHERE series_id = 'V39079' AND observation_date = %s",
            (dt.date(2026, 7, 1),),
        )
        after = cur.fetchone()[0]

    assert before == after


def test_a_revised_value_is_detected_and_counted_as_an_update(clean_slate, sample_rows):
    conn = clean_slate
    run_id = load.start_run(conn, PIPELINE)
    load.load_observations(conn, sample_rows, source_url=SOURCE_URL, run_id=run_id)

    # Simulate the Bank of Canada revising one published figure.
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE raw.boc_observation SET value_raw = '9.99'"
            " WHERE series_id = 'V39079' AND observation_date = %s",
            (dt.date(2026, 7, 1),),
        )

    result = load.load_observations(conn, sample_rows, source_url=SOURCE_URL, run_id=run_id)
    assert (result.inserted, result.updated) == (0, 1)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT value_raw FROM raw.boc_observation"
            " WHERE series_id = 'V39079' AND observation_date = %s",
            (dt.date(2026, 7, 1),),
        )
        assert cur.fetchone()[0] == "2.25"


# --- The guardrails built into the database ---------------------------------

def test_the_database_refuses_an_observation_from_an_unknown_run(clean_slate, sample_rows):
    """The foreign key is a mechanical guard, not a written instruction.

    A script that forgets to open a run cannot quietly write orphan rows: the
    database rejects them.
    """
    conn = clean_slate
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        load.load_observations(
            conn, sample_rows[:1], source_url=SOURCE_URL, run_id=uuid.uuid4()
        )
    conn.rollback()


def test_loading_nothing_is_allowed_and_reports_zero(clean_slate):
    conn = clean_slate
    run_id = load.start_run(conn, PIPELINE)
    result = load.load_observations(conn, [], source_url=SOURCE_URL, run_id=run_id)
    assert (result.inserted, result.updated) == (0, 0)
