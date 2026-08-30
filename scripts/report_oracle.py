#!/usr/bin/env python
"""What every KPI of the Power BI report must read, computed in SQL.

    .venv/Scripts/python.exe scripts/report_oracle.py
    .venv/Scripts/python.exe scripts/report_oracle.py --quarter 2023Q4

WHY THIS EXISTS

Every milestone up to J3 ended with a test that either passed or failed. J4
ends with a dashboard, which is read by a human, and nothing in it says "this
is correct". A report can have the right shape, the right colours and the
wrong number in every card, and look finished.

So this script computes, straight from the marts tables, what each visual of
report-design.md must show. Build the report, run this, compare. A figure that
disagrees is a measure written wrong -- an implicit SUM over a median, an
island row added to its own sectors, a filter that did not propagate.

It is the same arrangement as the read-by-eye APCIQ oracle of J3.2: the script
is versioned, its OUTPUT is not. Nothing here contains a figure; every number
printed is read from the database at run time.

DO NOT PASTE THE OUTPUT ANYWHERE. It contains APCIQ figures, whose licence
forbids reproduction "en tout ou en partie, directement ou indirectement".
It is meant to be read on screen, next to Power BI, and closed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.db import connect  # noqa: E402


def table(cur, title: str, note: str, sql: str, params: tuple = ()) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'-' * 78}\n{note}\n")
    cur.execute(sql, params)
    columns = [d.name for d in cur.description]
    rows = cur.fetchall()
    if not rows:
        print("  (no row -- if the report shows something here, the report is wrong)")
        return
    widths = [
        max(len(str(c)), max((len(str(r[i])) for r in rows), default=0))
        for i, c in enumerate(columns)
    ]
    print("  " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(columns)))
    print("  " + "-+-".join("-" * w for w in widths))
    for row in rows:
        print("  " + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quarter",
        default=None,
        help="edition to check, as 2026Q2. Defaults to the most recent loaded.",
    )
    parser.add_argument(
        "--income",
        type=int,
        default=95_000,
        help="household income for page 3, in dollars. Defaults to the figure "
             "used in section 31 of the brief.",
    )
    args = parser.parse_args()

    with connect() as conn, conn.cursor() as cur:
        if args.quarter:
            year, quarter = int(args.quarter[:4]), int(args.quarter[-1])
        else:
            cur.execute(
                "select edition_year, edition_quarter from marts.fact_market "
                "order by edition_year desc, edition_quarter desc limit 1"
            )
            year, quarter = cur.fetchone()

        print(f"\nReport oracle -- edition {year} Q{quarter}, income {args.income:,} $")
        print("Output is for reading on screen. Do not paste it anywhere.")

        table(
            cur,
            "PAGE 1 -- KPI row (island, as published)",
            "Median price must match the card EXACTLY. If the card is blank, the\n"
            "property type slicer is not on a single value -- that is the measure\n"
            "working, not a bug.",
            """
            select p.name_en                as property_type,
                   f.sales_count            as sales,
                   f.median_price           as median_price,
                   f.days_on_market         as days_on_market,
                   f.active_listings        as active_listings,
                   f.median_price_value_status as price_status
            from marts.fact_market f
            join marts.dim_property_type p using (property_type_code)
            where f.is_island_aggregate
              and f.edition_year = %s and f.edition_quarter = %s
            order by p.sort_order
            """,
            (year, quarter),
        )

        table(
            cur,
            "PAGE 1 -- Sectors minus island (sales)",
            "The J3.2 reconciliation control, on screen. Expect 0. A non-zero here\n"
            "is a declared publisher defect, not a modelling error -- 2023 Q4 is\n"
            "the known one.",
            """
            select p.name_en as property_type,
                   sum(f.sales_count) filter (where not f.is_island_aggregate) as sectors,
                   sum(f.sales_count) filter (where f.is_island_aggregate)     as island,
                   sum(f.sales_count) filter (where not f.is_island_aggregate)
                     - sum(f.sales_count) filter (where f.is_island_aggregate) as difference
            from marts.fact_market f
            join marts.dim_property_type p using (property_type_code)
            where f.edition_year = %s and f.edition_quarter = %s
            group by p.name_en, p.sort_order
            order by p.sort_order
            """,
            (year, quarter),
        )

        table(
            cur,
            "PAGE 2 -- Share of tracts affordable, this quarter",
            "Always read the base beside the percentage. It moves a lot by property\n"
            "type: APCIQ withholds plex medians in five sectors entirely, so the\n"
            "plex percentage rests on far fewer tracts than the condo one.\n"
            "Tracts are counted DISTINCT, as the DAX measures do. 4620511.02 is\n"
            "genuinely shared between two sectors and holds two rows, so counting\n"
            "rows here would sit 0.1 point away from the report, for a reason no\n"
            "one would find twice.\n"
            "The last two columns are the amounts report-design.md deliberately\n"
            "does not print: both derive from an APCIQ median.",
            """
            select p.name_en as property_type,
                   h.name_en as household_profile,
                   count(distinct a.ct_uid) filter (where a.meets_income_requirement is not null) as tracts_evaluated,
                   count(distinct a.ct_uid) filter (where a.meets_income_requirement)             as tracts_affordable,
                   round(100.0 * count(distinct a.ct_uid) filter (where a.meets_income_requirement)
                         / nullif(count(distinct a.ct_uid) filter (where a.meets_income_requirement is not null), 0), 1)
                                                                                  as pct_affordable,
                   round(avg(a.income_required_lower_bound))                      as mean_income_required,
                   round(percentile_cont(0.5) within group (order by a.price_to_income_ratio)::numeric, 2)
                                                                                  as median_price_to_income
            from marts.fact_affordability a
            join marts.dim_property_type p using (property_type_code)
            join marts.dim_household_profile h using (household_profile_code)
            where a.edition_year = %s and a.edition_quarter = %s
            group by p.name_en, p.sort_order, h.name_en, h.sort_order
            order by p.sort_order, h.sort_order
            """,
            (year, quarter),
        )

        table(
            cur,
            "PAGE 2 -- The finding: affordability over time (condo, couple)",
            "This is the line chart that carries the report. Every quarter, not\n"
            "grouped by year. The income behind it is the 2020 census and does not\n"
            "move across any of these rows.",
            """
            select a.edition_label as quarter,
                   count(*) filter (where a.meets_income_requirement is not null) as tracts_evaluated,
                   round(100.0 * count(distinct a.ct_uid) filter (where a.meets_income_requirement)
                         / nullif(count(distinct a.ct_uid) filter (where a.meets_income_requirement is not null), 0), 1)
                                                                                  as pct_affordable
            from marts.fact_affordability a
            where a.property_type_code = 'condo'
              and a.household_profile_code = 'couple'
            group by a.edition_label, a.edition_year, a.edition_quarter
            order by a.edition_year, a.edition_quarter
            """,
        )

        table(
            cur,
            f"PAGE 3 -- Tracts within reach of {args.income:,} $ (condo, couple)",
            "Compare with the what-if slicer set to the same income. The two must\n"
            "agree exactly; if the Power BI figure is larger, the measure is\n"
            "counting tracts with no published price.",
            """
            select g.name as sector,
                   count(*) filter (where a.income_required_lower_bound is not null) as tracts_priced,
                   count(*) filter (where a.income_required_lower_bound <= %s)       as within_reach
            from marts.fact_affordability a
            join marts.dim_geography g on g.geography_key = a.apciq_geography_key
            where a.property_type_code = 'condo'
              and a.household_profile_code = 'couple'
              and a.edition_year = %s and a.edition_quarter = %s
            group by g.name, a.apciq_sector_number
            order by a.apciq_sector_number
            """,
            (args.income, year, quarter),
        )

        table(
            cur,
            "PAGE 4 -- Rates over the quarter, and the gap that matters",
            "observations differs by series on purpose: the policy rate publishes\n"
            "every business day, both mortgage rates weekly. A chart that hides\n"
            "that implies the weekly series was observed as often as the daily one.",
            """
            select s.rate_kind,
                   s.frequency,
                   count(*)                          as observations,
                   round(avg(r.rate_percent), 3)     as mean_rate_percent,
                   min(r.observation_date)           as first_obs,
                   max(r.observation_date)           as last_obs
            from marts.fact_interest_rate r
            join marts.dim_interest_rate_series s using (series_id)
            join marts.dim_date d on d.date_key = r.observation_date
            where d.calendar_year = %s and d.calendar_quarter = %s
            group by s.rate_kind, s.frequency, s.sort_order
            order by s.sort_order
            """,
            (year, quarter),
        )

        table(
            cur,
            "PAGE 4 -- Posted minus contract, as the report must show it",
            "The single number that justifies the whole rate model. Reading a\n"
            "posted rate as a contracted one moves the required income by about\n"
            "15 %, and CMHC states the qualifying rate on the CONTRACT rate, so\n"
            "stressing a posted rate applies the margin twice.",
            """
            select round(avg(posted_rate_percent), 3)                as posted,
                   round(avg(contract_rate_percent), 3)              as contracted,
                   round(avg(posted_minus_contract_rate_points), 3)  as gap_points
            from marts.fact_mortgage_scenario
            where edition_year = %s and edition_quarter = %s
            """,
            (year, quarter),
        )

        print(f"\n{'=' * 78}")
        print("Every figure above is read from marts at run time. If a Power BI card")
        print("disagrees with one of them, the card is wrong -- not this script.")
        print("Do not paste this output anywhere.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
