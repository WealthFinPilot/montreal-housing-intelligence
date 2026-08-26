"""The Bank of Canada series this project ingests.

Every label below is copied verbatim from what the Valet API itself returned
on 2026-08-22. Nothing here is remembered or guessed: a wrong series name
produces a plausible chart of the wrong number, which is worse than an error.

Verification trail, 2026-08-22:
  GET https://www.bankofcanada.ca/valet/groups/ATABLE_POLICY_INSTRUMENT/json -> 200
  GET https://www.bankofcanada.ca/valet/groups/CHARTERED_BANK_INTEREST/json  -> 200
  GET https://www.bankofcanada.ca/valet/series/V39079/json                   -> 200

Verification trail, 2026-08-26:
  GET https://www.bankofcanada.ca/valet/lists/series/json                    -> 200
  GET https://www.bankofcanada.ca/valet/series/FVI_MTG_RATE_5Y_FIX/json      -> 200
  GET https://www.bankofcanada.ca/valet/observations/FVI_MTG_RATE_5Y_FIX/json-> 200
      648 observations, 2014-01-07 to 2026-06-02
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
    Series(
        series_id="FVI_MTG_RATE_5Y_FIX",
        label="5-year fixed interest rate for a high-ratio mortgage",
        frequency="weekly",
        purpose=(
            "The rate borrowers ACTUALLY CONTRACT on a high-ratio mortgage, which is "
            "the scenario fact_mortgage_scenario models: a buyer putting down the legal "
            "minimum is by definition high-ratio. Added on 2026-08-26, when the "
            "affordability model showed how much the posted rate distorts the answer -- "
            "on 2026 Q2 the posted 5-year stood at 6.09 % against 4.29 % here, and the "
            "gap flows through the qualifying rate into every income figure."
        ),
        caveat=(
            "The Bank of Canada gives it a one-line description and no methodology on "
            "the series endpoint itself, so what population of loans it averages is not "
            "stated there. It remains a CONTRACTED rate on the class of loan modelled "
            "here, which the posted series is not. It also starts in 2014 and ended on "
            "2026-06-02 at retrieval, so it is weekly like the posted series but its "
            "last observation can trail: rate_observation_count in the mart is what "
            "makes a thin quarter visible instead of silently averaging two points."
        ),
    ),
)

SERIES_IDS: tuple[str, ...] = tuple(s.series_id for s in SERIES)


def by_id(series_id: str) -> Series:
    for series in SERIES:
        if series.series_id == series_id:
            return series
    raise KeyError(f"{series_id} is not in the catalogue of {__name__}")
