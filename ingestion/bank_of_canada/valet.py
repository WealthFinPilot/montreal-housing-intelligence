"""Read observations from the Bank of Canada Valet API.

This module talks to the network and nothing else: it never opens a database
connection. That separation is what makes the parsing testable offline.

The response shape, verified against a live call on 2026-08-22:

    {
      "terms":        {"url": "https://www.bankofcanada.ca/terms/"},
      "seriesDetail": {"V39079": {"label": "...", "description": "..."}},
      "observations": [
        {"d": "2026-07-01", "V39079": {"v": "2.25"}, "V80691335": {"v": "6.09"}},
        {"d": "2026-07-02", "V39079": {"v": "2.25"}}
      ]
    }

Three facts drive the whole parser:

1. One row per DATE, not per observation. Asking for several series at once
   returns them side by side on the same date line.

2. A series that published nothing on a given date is simply ABSENT from that
   line -- see 2026-07-02 above, where the weekly mortgage rate has no key.
   An absent key means "no observation exists". It must never become a zero,
   a null, or the previous value carried forward. Principle 1 of the project:
   never invent a missing value.

3. Values arrive as JSON STRINGS ("2.25", not 2.25). We keep them as strings
   all the way into the raw layer and let dbt convert them, where a surprise
   format fails a test loudly instead of silently becoming a zero.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from urllib.parse import urlencode

import requests

BASE_URL = "https://www.bankofcanada.ca/valet/observations"

# Identifies this project to the server. Not required by the Bank of Canada,
# but it is the courteous thing to do and costs nothing.
USER_AGENT = "montreal-housing-intelligence/0.1 (portfolio project)"

DEFAULT_TIMEOUT_SECONDS = 60


class ValetResponseError(RuntimeError):
    """The API answered something that is not a Valet observations payload."""


class ContradictoryObservationError(ValueError):
    """The same series and date arrived twice with two different values."""


@dataclass(frozen=True, slots=True)
class Observation:
    """One value, for one series, on one date -- exactly as received."""

    series_id: str
    observation_date: dt.date
    value_raw: str


@dataclass(frozen=True)
class FetchResult:
    observations: list[Observation]
    source_url: str


def build_observations_url(
    series_ids,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> str:
    """Build the exact URL we will call, so it can be logged and replayed by hand."""
    series_ids = list(series_ids)
    if not series_ids:
        # Valet answers a request for no series with a large default payload.
        # Better to stop here than to download something nobody asked for.
        raise ValueError("at least one series id is required")

    url = f"{BASE_URL}/{','.join(series_ids)}/json"

    params = {}
    if start_date is not None:
        params["start_date"] = start_date.isoformat()
    if end_date is not None:
        params["end_date"] = end_date.isoformat()
    return f"{url}?{urlencode(params)}" if params else url


def parse_observations(payload: dict) -> list[Observation]:
    """Turn a Valet payload into a flat list of observations."""
    if not isinstance(payload, dict) or "observations" not in payload:
        raise ValetResponseError(
            "response has no observations key -- this is not a Valet observations payload"
        )

    rows: list[Observation] = []
    for entry in payload["observations"]:
        date_text = entry.get("d")
        if not date_text:
            raise ValetResponseError(f"observation without a date: {entry!r}")
        observation_date = dt.date.fromisoformat(date_text)

        for key, cell in entry.items():
            if key == "d":
                continue  # the date column itself, not a series
            if not isinstance(cell, dict):
                raise ValetResponseError(
                    f"unexpected shape for series {key} on {date_text}: {cell!r}"
                )
            if "v" not in cell:
                # No value published for this series on this date. Not an error,
                # and not a row.
                continue
            # Kept as text, empty string included. An empty value is the source
            # saying that nothing was published that day, which is information.
            rows.append(Observation(key, observation_date, cell["v"]))

    return rows


def deduplicate(observations) -> list[Observation]:
    """Collapse identical repeats, refuse contradictions.

    The same series and date appearing twice with the SAME value is harmless
    noise. Appearing twice with DIFFERENT values is a real anomaly, and picking
    one of them would be inventing data -- so it raises instead.
    """
    seen: dict[tuple[str, dt.date], Observation] = {}
    for observation in observations:
        key = (observation.series_id, observation.observation_date)
        previous = seen.get(key)
        if previous is None:
            seen[key] = observation
        elif previous.value_raw != observation.value_raw:
            raise ContradictoryObservationError(
                f"{key[0]} on {key[1]} arrived twice with different values: "
                f"{previous.value_raw!r} then {observation.value_raw!r}"
            )
    return list(seen.values())


def fetch_observations(
    series_ids,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    session=None,
) -> FetchResult:
    """Call the API and return clean observations plus the URL that produced them."""
    url = build_observations_url(series_ids, start_date=start_date, end_date=end_date)
    http = session or requests
    response = http.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return FetchResult(deduplicate(parse_observations(response.json())), url)
