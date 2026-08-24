"""Database tests for the APCIQ loader.

Two tables are written per edition -- the figures and the verdict of the
controls run on them -- and the point of most of what follows is that they
behave as one unit.

Every test runs inside a transaction that is rolled back (see conftest.py), so
they work against the real tables without leaving anything behind.

Requires the SSH tunnel:  bash scripts/tunnel-start.sh
"""

from __future__ import annotations

import psycopg
import pytest

from ingestion.apciq import load, parse

pytestmark = pytest.mark.db

# A year no Baromètre will ever carry, so these rows cannot collide with the
# archive even for the moment the transaction is open.
TEST_YEAR = 1900
TEST_QUARTER = 1


def an_observation(**overrides) -> parse.Observation:
    fields = dict(
        edition_year=TEST_YEAR,
        edition_quarter=TEST_QUARTER,
        area_code="sector-14",
        property_category="condo",
        metric_code="sales",
        period_code="quarter",
        value_text="86",
        change_percent_text="-34 %",
        source_area_label="Secteur 14 : Villeray",
        source_category_label="Copropriété",
        source_metric_label="Ventes",
        source_page=22,
    )
    fields.update(overrides)
    return parse.Observation(**fields)


def a_control(**overrides) -> parse.ControlTotal:
    fields = dict(
        edition_year=TEST_YEAR,
        edition_quarter=TEST_QUARTER,
        control_code=parse.PAGE_CONTROL,
        scope="sector-14",
        property_category="all",
        metric_code="sales",
        period_code="quarter",
        published_total=207,
        computed_total=207,
        tolerance=0,
        source_page=22,
    )
    fields.update(overrides)
    return parse.ControlTotal(**fields)


@pytest.fixture
def clean_slate(db_connection):
    with db_connection.cursor() as cur:
        cur.execute(
            "DELETE FROM raw.apciq_control_total WHERE edition_year = %s", (TEST_YEAR,)
        )
        cur.execute(
            "DELETE FROM raw.apciq_barometer_statistic WHERE edition_year = %s",
            (TEST_YEAR,),
        )
    return db_connection


def count_controls(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM raw.apciq_control_total WHERE edition_year = %s",
            (TEST_YEAR,),
        )
        return cur.fetchone()[0]


# --- idempotence ------------------------------------------------------------


def test_first_load_inserts_every_control(clean_slate):
    controls = [a_control(), a_control(metric_code="active_listings",
                                       published_total=192, computed_total=150,
                                       tolerance=2)]
    result = load.load_control_totals(clean_slate, controls)

    assert (result.inserted, result.updated) == (2, 0)
    assert count_controls(clean_slate) == 2


def test_reloading_the_same_edition_rewrites_nothing(clean_slate):
    """Criterion 2 of J2, applied to the second table.

    The count comes from the database -- xmax on the returned rows -- not from
    a counter kept in Python, so it cannot report success while writing.
    """
    controls = [a_control()]
    load.load_control_totals(clean_slate, controls)
    again = load.load_control_totals(clean_slate, controls)

    assert (again.inserted, again.updated) == (0, 0)
    assert count_controls(clean_slate) == 1


def test_a_control_whose_verdict_moved_is_counted_as_an_update(clean_slate):
    """What a re-read that changes its mind must look like.

    APCIQ republishes corrected editions. If a figure moves, the control on it
    moves too, and that has to be visible as an update rather than silently
    accepted or silently ignored.
    """
    load.load_control_totals(clean_slate, [a_control(computed_total=150)])
    result = load.load_control_totals(clean_slate, [a_control(computed_total=207)])

    assert (result.inserted, result.updated) == (0, 1)
    with clean_slate.cursor() as cur:
        # The stored verdict is the new one, not the first one seen.
        # updated_at is deliberately not asserted here: it defaults to now(),
        # which in PostgreSQL is the START of the transaction, and this whole
        # test lives in one. Both timestamps are therefore equal by design.
        cur.execute(
            "SELECT computed_total FROM raw.apciq_control_total "
            " WHERE edition_year = %s",
            (TEST_YEAR,),
        )
        assert cur.fetchone() == (207,)


def test_loading_no_control_is_allowed_and_reports_zero(clean_slate):
    assert load.load_control_totals(clean_slate, []) == load.LoadResult(0, 0)


# --- what the database refuses ----------------------------------------------


def test_the_database_refuses_a_negative_tolerance(clean_slate):
    """A tolerance is a distance, and the CHECK constraint says so.

    Declared in the table rather than in Python: a loader written later, or a
    hand-typed INSERT, meets the same rule.
    """
    with pytest.raises(psycopg.errors.CheckViolation):
        load.load_control_totals(clean_slate, [a_control(tolerance=-1)])
    clean_slate.rollback()


def test_two_editions_in_one_call_are_refused(clean_slate):
    """The year and quarter are passed once, as scalars.

    Mixing two editions in one call would file the second under the first --
    quietly, and with no way to tell afterwards.
    """
    with pytest.raises(ValueError, match="one edition per call"):
        load.load_control_totals(
            clean_slate, [a_control(), a_control(edition_year=TEST_YEAR + 1)]
        )


# --- the two tables are one unit --------------------------------------------


def test_figures_and_verdict_stand_or_fall_together(clean_slate):
    """The reason both loaders refuse to commit anything themselves.

    A database holding figures nobody checked, or a verdict on figures that
    are not there, would be worse than one holding neither. Here the control
    write is made to fail after the figures were written; rolling back the
    transaction must leave the database with neither.
    """
    load.load_observations(clean_slate, [an_observation()], source_pdf="test.pdf")

    with pytest.raises(psycopg.errors.CheckViolation):
        load.load_control_totals(clean_slate, [a_control(tolerance=-1)])
    clean_slate.rollback()

    with clean_slate.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM raw.apciq_barometer_statistic WHERE edition_year = %s",
            (TEST_YEAR,),
        )
        assert cur.fetchone()[0] == 0
    assert count_controls(clean_slate) == 0
