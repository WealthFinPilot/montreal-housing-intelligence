"""The Bank of Canada series this project ingests.

Every label below is copied verbatim from what the Valet API itself returned
on 2026-08-22. Nothing here is remembered or guessed: a wrong series name
produces a plausible chart of the wrong number, which is worse than an error.

Verification trail, 2026-08-22:
  GET https://www.bankofcanada.ca/valet/groups/ATABLE_POLICY_INSTRUMENT/json -> 200
  GET https://www.bankofcanada.ca/valet/groups/CHARTERED_BANK_INTEREST/json  -> 200
  GET https://www.bankofcanada.ca/valet/series/V39079/json                   -> 200
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# Milestone J2 acceptance criterion 4 asks for the policy rate since 2015.
# Unlike the APCIQ market history, which starts in 2019Q2, the Bank of Canada
# publishes this far further back, so 2015 costs nothing here.
HISTORY_START = dt.date(2015, 1, 1)

TERMS_URL = "https://www.bankofcanada.ca/terms/"


@dataclass(frozen=True)
class Series:
    series_id: str
    label: str        # exactly as returned by the API
    frequency: str    # observed, not announced
    purpose: str
    caveat: str | None = None


SERIES: tuple[Series, ...] = (
    Series(
        series_id="V39079",
        label="Target for the overnight rate (business daily)",
        frequency="business daily",
        purpose=(
            "The policy interest rate. The Bank of Canada describes it as the average "
            "rate it wants to see in the market for overnight money market financing."
        ),
    ),
    Series(
        series_id="V80691335",
        label="Conventional mortgage: 5-year",
        frequency="weekly",
        purpose=(
            "Feeds the mortgage payment and affordability calculations of milestone J4."
        ),
        caveat=(
            "POSTED rate, not contracted rate. This is what the major chartered banks "
            "advertise, not what a borrower actually negotiates -- discounts of one to "
            "two points are ordinary. Treat it exactly like asking_price versus "
            "sale_price: an indicator of direction, never a transaction price. Any "
            "affordability figure derived from it is an assumption, not an observation."
        ),
    ),
)

SERIES_IDS: tuple[str, ...] = tuple(s.series_id for s in SERIES)


def by_id(series_id: str) -> Series:
    for series in SERIES:
        if series.series_id == series_id:
            return series
    raise KeyError(f"{series_id} is not in the catalogue of {__name__}")
