"""What the Consumer Price Index ingestion must guarantee.

The fixtures are real WDS responses, cut down the way the census fixtures in
test_statcan.py are, and for the same reason: a stub written here can only
contain the shape already expected. The Statistics Canada Open Licence permits
redistributing them.

THE TEST WORTH READING TWICE

test_a_coordinate_pointing_elsewhere_is_refused. A coordinate is a POSITION in
a cube, not a name. If the cube is ever re-cut, "13.2.0..." keeps working and
starts describing a different city -- and the neighbouring member is not some
obviously wrong thing, it is the province of Quebec. Nothing would fail. A
provincial index would load, average cleanly, and quietly restate every
Montreal income by the wrong factor.

That is why the loader checks the coordinate against the published
classification code rather than trusting the position, and why this file
spends four tests on it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.statcan import datasets, load, parse, wds

FIXTURES = Path(__file__).parent / "fixtures"

CPI = datasets.CONSUMER_PRICE_INDEX


@pytest.fixture(scope="module")
def cpi_metadata() -> dict:
    payload = json.loads((FIXTURES / "statcan_cpi_metadata.json").read_text(encoding="utf-8"))
    return payload[0]["object"]


@pytest.fixture(scope="module")
def cpi_series() -> dict:
    payload = json.loads((FIXTURES / "statcan_cpi_series.json").read_text(encoding="utf-8"))
    return payload[0]["object"]


@pytest.fixture
def response(cpi_series) -> wds.SeriesResponse:
    return wds.SeriesResponse(
        vector_id=str(cpi_series["vectorId"]),
        points=cpi_series["vectorDataPoint"],
        uom_code="17",
        uom="2002=100",
        cube_title="Consumer Price Index, monthly, not seasonally adjusted",
        cube_end_date="2026-07-01",
        source_url="https://example.invalid/series",
    )


# ---------------------------------------------------------------------------
# The coordinate is checked, not trusted
# ---------------------------------------------------------------------------


def test_the_declared_coordinate_is_accepted(cpi_metadata):
    """The catalogue's own coordinate must pass, or every other test is moot."""
    assert wds._verify_coordinate(CPI, cpi_metadata) == "17"


def test_a_coordinate_pointing_elsewhere_is_refused(cpi_metadata):
    """Member 11 is the PROVINCE of Quebec, and it would load without error."""
    import dataclasses

    province = dataclasses.replace(CPI, coordinate="11.2.0.0.0.0.0.0.0.0")
    with pytest.raises(wds.WdsError, match="classification"):
        wds._verify_coordinate(province, cpi_metadata)


def test_a_coordinate_on_the_wrong_basket_is_refused(cpi_metadata):
    """Right city, wrong product: an index of meat prices is still an index."""
    import dataclasses

    meat = dataclasses.replace(CPI, coordinate="13.9.0.0.0.0.0.0.0.0")
    with pytest.raises(wds.WdsError, match="All-items"):
        wds._verify_coordinate(meat, cpi_metadata)


def test_a_member_that_no_longer_exists_is_refused(cpi_metadata):
    """A re-cut cube drops members. That must stop the run, not skip a check."""
    import dataclasses

    gone = dataclasses.replace(CPI, coordinate="9999.2.0.0.0.0.0.0.0.0")
    with pytest.raises(wds.WdsError, match="no longer exists"):
        wds._verify_coordinate(gone, cpi_metadata)


# ---------------------------------------------------------------------------
# Values keep the precision the source states, and a null stays a null
# ---------------------------------------------------------------------------


def test_the_index_keeps_the_precision_the_source_publishes():
    assert parse._index_value({"value": 169.9, "decimals": 1}) == "169.9"
    assert parse._index_value({"value": 169.0, "decimals": 1}) == "169.0"
    assert parse._index_value({"value": 133.6917, "decimals": 4}) == "133.6917"


def test_a_null_index_never_becomes_a_zero():
    """The failure that cost this project a session twice, in J3.2 and J3.3.

    '-' was read as zero in one source and '...' printed a literal 0 in
    another. Here a missing value must stay empty, so that staging can drop it
    rather than average an index of zero into a quarter.
    """
    assert parse._index_value({"value": None, "decimals": 1}) == ""
    assert parse._index_value({"value": None}) == ""


# ---------------------------------------------------------------------------
# Parsing keeps every assertion the source made
# ---------------------------------------------------------------------------


def test_every_point_becomes_exactly_one_record(response):
    records = parse.cpi_observations(response, CPI)
    assert len(records) == len(response.points)
    assert len({(r.vector_id, r.ref_period) for r in records}) == len(records)


def test_the_codes_travel_with_the_value(response):
    records = parse.cpi_observations(response, CPI)
    sample = records[0]
    assert sample.status_code == "0"
    assert sample.symbol_code == "0"
    assert sample.frequency_code == "6"
    assert sample.uom == "2002=100"
    assert sample.geo_name == CPI.geo_name
    assert sample.product_name == CPI.product_name


def test_a_point_without_a_period_stops_the_run(response):
    """It could not be keyed, so loading it would mean inventing a period."""
    import dataclasses

    broken = dataclasses.replace(
        response, points=[{"value": 100.0, "decimals": 1}]
    )
    with pytest.raises(parse.ParseError, match="reference period"):
        parse.cpi_observations(broken, CPI)


# ---------------------------------------------------------------------------
# Against the real table, in a transaction that is always rolled back
# ---------------------------------------------------------------------------


def test_loading_twice_inserts_nothing_the_second_time(db_connection, response):
    """Idempotence, asserted against the real primary key rather than a copy."""
    records = parse.cpi_observations(response, CPI)

    # A vector id that cannot collide with the loaded series, so the assertion
    # is about the merge and not about what happens to be in the table.
    import dataclasses

    records = [dataclasses.replace(r, vector_id="test-vector") for r in records]

    first = load.load_cpi(db_connection, records, source_file="test")
    assert first.inserted == len(records)
    assert first.updated == 0

    second = load.load_cpi(db_connection, records, source_file="test")
    assert second.inserted == 0
    assert second.updated == 0


def test_a_revised_index_updates_its_row_rather_than_adding_one(db_connection, response):
    import dataclasses

    records = [
        dataclasses.replace(r, vector_id="test-vector")
        for r in parse.cpi_observations(response, CPI)
    ]
    load.load_cpi(db_connection, records, source_file="test")

    revised = [dataclasses.replace(records[0], value="999.9", symbol_code="3")]
    result = load.load_cpi(db_connection, revised, source_file="test")

    assert result.inserted == 0
    assert result.updated == 1

    with db_connection.cursor() as cur:
        cur.execute(
            "select count(*) from raw.statcan_cpi_observation where vector_id = %s",
            ("test-vector",),
        )
        assert cur.fetchone()[0] == len(records)
