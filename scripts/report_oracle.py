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

# Sector names carry accents, and a Windows console defaults to cp1252, which
# turns them into replacement characters. This is a report meant to be read
# beside Power BI, so the names have to be readable.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

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
            f"PAGE 3 -- The table, sector by sector, at {args.income:,} $ (condo, couple)",
            "Page 3 is at the SECTOR, not the tract: the required income depends on\n"
            "the price alone, so every tract of a sector returns the same verdict.\n"
            "verdict applies the 10 % display band, exactly as the DAX measure does\n"
            "-- a card testing required <= income and a table testing\n"
            "required * 1.10 <= income disagree in 44 of the 87 quarter x type\n"
            "slices, by up to five sectors. tracts_priced is coverage only.",
            """
            with per_sector as (
              select g.name                              as sector,
                     a.apciq_sector_number,
                     avg(a.income_required_lower_bound)   as required,
                     count(distinct a.ct_uid)             as tracts,
                     count(distinct a.ct_uid) filter (where a.median_price is not null) as tracts_priced
              from marts.fact_affordability a
              join marts.dim_geography g on g.geography_key = a.apciq_geography_key
              where a.property_type_code = 'condo'
                and a.household_profile_code = 'couple'
                and a.edition_year = %s and a.edition_quarter = %s
              group by g.name, a.apciq_sector_number
            )
            select sector,
                   round(required)                       as income_required,
                   case when required is null then 'No published price'
                        when %s >= required * 1.10 then 'Within reach'
                        when %s >= required        then 'Borderline'
                        else 'Out of reach' end          as verdict,
                   tracts_priced,
                   tracts
            from per_sector
            order by apciq_sector_number
            """,
            (year, quarter, args.income, args.income),
        )

        table(
            cur,
            f"PAGE 3 -- KPI row, which must add up to eighteen",
            "within_reach + borderline + out_of_reach + no_price = 18. Four counts,\n"
            "one definition each. If Power BI shows a blank rather than a zero in\n"
            "any of them, the measure is missing its IF ( ISBLANK ( .. ), 0, .. ) --\n"
            "COUNTROWS and DISTINCTCOUNT both return blank over an empty set, and\n"
            "no sector is within reach at the low end of the slicer.",
            """
            with per_sector as (
              select a.apciq_sector_number, avg(a.income_required_lower_bound) as required
              from marts.fact_affordability a
              where a.property_type_code = 'condo'
                and a.household_profile_code = 'couple'
                and a.edition_year = %s and a.edition_quarter = %s
              group by a.apciq_sector_number
            )
            select count(*) filter (where required is not null)                        as sectors_priced,
                   count(*) filter (where required is not null and %s >= required * 1.10) as within_reach,
                   count(*) filter (where required is not null and %s >= required
                                      and %s < required * 1.10)                        as borderline,
                   count(*) filter (where required is not null and %s < required)      as out_of_reach,
                   count(*) filter (where required is null)                            as no_price,
                   count(*)                                                            as sectors_total
            from per_sector
            """,
            (year, quarter, args.income, args.income, args.income, args.income),
        )

        table(
            cur,
            "PAGE 3 -- The shortcut the KPI denominator rests on",
            "Sectors priced and Tracts priced count a PUBLISHED price\n"
            "(median_price), while the verdict rests on a DERIVED one\n"
            "(income_required_lower_bound). That reads as one number only while the\n"
            "two absences coincide. Every column below must be zero, on every row.\n"
            "The day a price falls outside the insurable range and carries no\n"
            "required income, the sector belongs in the denominator and not in the\n"
            "numerator -- and this is where that shows up first.",
            """
            with rows_ as (
              select property_type_code,
                     count(*) filter (where median_price is not null
                                        and income_required_lower_bound is null) as priced_but_no_required,
                     count(*) filter (where median_price is null
                                        and income_required_lower_bound is not null) as required_but_no_price
              from marts.fact_affordability
              group by property_type_code
            ), per_sector as (
              select property_type_code,
                     count(distinct income_required_lower_bound) as n_required
              from marts.fact_affordability
              group by property_type_code, apciq_sector_number, edition_year,
                       edition_quarter, household_profile_code
            ), spread as (
              select property_type_code,
                     count(*) filter (where n_required > 1) as sectors_with_two_required
              from per_sector group by property_type_code
            )
            select r.property_type_code, r.priced_but_no_required,
                   r.required_but_no_price, s.sectors_with_two_required
            from rows_ r join spread s using (property_type_code)
            order by 1
            """,
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
            "PAGE 4 -- Is every series still publishing?",
            "What Rate freshness warning must say, and the reason it exists. Both\n"
            "weekly series ran at a gap of exactly seven days -- min 7, max 7, no\n"
            "gap above 7 -- over their whole history, so anything in days_behind\n"
            "beyond a couple of weeks is the source having stopped, not a rhythm.\n"
            "Checked against the live Valet API on 2026-08-30: the contracted\n"
            "series answers 200 and has published nothing since 2026-06-02.\n"
            "This column is NOT dbt source freshness, which measures when we last\n"
            "loaded and stays green while a publisher goes silent.",
            """
            with last_obs as (
              select series_id, max(observation_date) as last_obs,
                     min(observation_date) as first_obs, count(*) as observations
              from marts.fact_interest_rate group by 1
            ), cadence as (
              select series_id, max(gap) as max_gap_days from (
                select series_id,
                       observation_date - lag(observation_date)
                         over (partition by series_id order by observation_date) as gap
                from marts.fact_interest_rate) g
              where gap is not null group by 1
            )
            select s.rate_kind, s.frequency, l.observations, l.first_obs, l.last_obs,
                   c.max_gap_days,
                   (select max(last_obs) from last_obs) - l.last_obs as days_behind
            from last_obs l
            join cadence c using (series_id)
            join marts.dim_interest_rate_series s using (series_id)
            order by s.sort_order
            """,
        )

        table(
            cur,
            f"PAGE 4 -- The quarter table for {year}",
            "The row the headline is read off. A year slicer cannot produce a\n"
            "single quarter, so the KPI card averages whatever is selected and\n"
            "this table is where the quoted figure is legible.\n"
            "A quarter with posted observations and no contracted ones must show\n"
            "a BLANK gap, never the posted rate on its own: that is the\n"
            "blank-as-zero fault the DAX measure guards against with ISBLANK.",
            """
            select d.quarter_label,
                   round(avg(r.rate_percent) filter (where s.rate_kind = 'posted'), 3)     as posted,
                   round(avg(r.rate_percent) filter (where s.rate_kind = 'contracted'), 3) as contracted,
                   round(avg(r.rate_percent) filter (where s.rate_kind = 'posted'), 3)
                     - round(avg(r.rate_percent) filter (where s.rate_kind = 'contracted'), 3) as gap_points,
                   count(*) filter (where s.rate_kind = 'contracted')                      as contract_obs,
                   count(*) filter (where s.rate_kind = 'posted')                          as posted_obs
            from marts.fact_interest_rate r
            join marts.dim_interest_rate_series s using (series_id)
            join marts.dim_date d on d.date_key = r.observation_date
            where d.calendar_year = %s
            group by d.quarter_label
            order by d.quarter_label
            """,
            (year,),
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
