"""Unit tests for the Bank of Canada Valet client.

No network, no database. These tests describe what the parser must do with a
response, and they run offline.

The single most important behaviour tested here: when Valet is asked for two
series at once, it returns ONE row per date and simply omits the key of any
series that published nothing that day. A missing key means "no observation",
and it must never become a zero, a null, or the previous day's value carried
forward. That is principle 1 of the project: never invent a missing value.
"""

from __future__ import annotations

import datetime as dt

import pytest

from ingestion.bank_of_canada import valet


# --- URL construction -------------------------------------------------------

def test_url_joins_series_with_commas_and_carries_the_start_date():
    url = valet.build_observations_url(
        ["V39079", "V80691335"], start_date=dt.date(2015, 1, 1)
    )
    assert url.startswith("https://www.bankofcanada.ca/valet/observations/")
    assert "V39079,V80691335" in url
    assert "start_date=2015-01-01" in url
    assert "/json" in url


def test_url_without_dates_asks_for_the_whole_history():
    url = valet.build_observations_url(["V39079"])
    assert "start_date" not in url
    assert "end_date" not in url


def test_url_refuses_an_empty_series_list():
    # Asking Valet for nothing returns everything. Fail here instead.
    with pytest.raises(ValueError):
        valet.build_observations_url([])


# --- Parsing ----------------------------------------------------------------

def test_parse_returns_one_row_per_series_and_date(valet_payload):
    rows = valet.parse_observations(valet_payload)
    # Counted in the captured fixture: 11 daily policy-rate values and
    # 3 weekly mortgage-rate values over the same fortnight.
    assert len(rows) == 14


def test_parse_does_not_invent_rows_for_a_series_that_published_nothing(valet_payload):
    rows = valet.parse_observations(valet_payload)
    policy = [r for r in rows if r.series_id == "V39079"]
    mortgage = [r for r in rows if r.series_id == "V80691335"]

    assert len(policy) == 11
    assert len(mortgage) == 3
    # The mortgage rate is weekly: only the three Wednesdays are present. The
    # eight other dates in the response must produce no mortgage row at all.
    assert [r.observation_date for r in mortgage] == [
        dt.date(2026, 7, 1),
        dt.date(2026, 7, 8),
        dt.date(2026, 7, 15),
    ]


def test_parse_keeps_the_value_as_text(valet_payload):
    rows = valet.parse_observations(valet_payload)
    sample = next(r for r in rows if r.series_id == "V39079")
    assert isinstance(sample.value_raw, str)
    assert sample.value_raw == "2.25"  # not 2.25 the float


def test_parse_turns_the_date_into_a_real_date(valet_payload):
    rows = valet.parse_observations(valet_payload)
    assert all(isinstance(r.observation_date, dt.date) for r in rows)


def test_parse_preserves_an_empty_value_instead_of_dropping_it():
    # Not observed on our two series (checked over 2015-2026 on 2026-08-22),
    # but Valet documents empty values for non-publication days on some series.
    # An empty string is information: the source published nothing that day.
    # It must reach the raw layer untouched, not become 0 and not vanish.
    payload = {"observations": [{"d": "2026-07-01", "V39079": {"v": ""}}]}
    rows = valet.parse_observations(payload)
    assert len(rows) == 1
    assert rows[0].value_raw == ""


def test_parse_ignores_the_date_key_itself():
    payload = {"observations": [{"d": "2026-07-01", "V39079": {"v": "2.25"}}]}
    rows = valet.parse_observations(payload)
    assert {r.series_id for r in rows} == {"V39079"}


def test_parse_rejects_a_response_with_no_observations_key():
    with pytest.raises(valet.ValetResponseError):
        valet.parse_observations({"terms": {"url": "..."}})


# --- Duplicate handling -----------------------------------------------------

def test_identical_duplicates_are_collapsed():
    rows = [
        valet.Observation("V39079", dt.date(2026, 7, 1), "2.25"),
        valet.Observation("V39079", dt.date(2026, 7, 1), "2.25"),
    ]
    assert len(valet.deduplicate(rows)) == 1


def test_contradictory_duplicates_raise_instead_of_being_silently_resolved():
    # Two different values for the same series and the same day is a real
    # anomaly. Picking one would be inventing data.
    rows = [
        valet.Observation("V39079", dt.date(2026, 7, 1), "2.25"),
        valet.Observation("V39079", dt.date(2026, 7, 1), "5.00"),
    ]
    with pytest.raises(valet.ContradictoryObservationError):
        valet.deduplicate(rows)
