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
            "PAGE 1 MAP -- colour classes, which must add up to 18",
            "The map has one absence: a sector APCIQ did not price. Coloured plus\n"
            "grey must equal 18, the shape count of apciq_sector_island.geojson.\n"
            "A total under 18 means a sector failed to join and is invisible --\n"
            "which looks exactly like a sector that happens to be off screen.",
            """
            select p.name_en                                              as property_type,
                   count(*) filter (where f.median_price is not null)     as coloured,
                   count(*) filter (where f.median_price is null)         as grey_no_price,
                   count(*)                                                as must_be_18
            from marts.fact_market f
            join marts.dim_property_type p using (property_type_code)
            join marts.dim_geography g using (geography_key)
            where g.geography_type = 'apciq_sector'
              and f.edition_year = %s and f.edition_quarter = %s
            group by p.name_en, p.sort_order
            order by p.sort_order
            """,
            (year, quarter),
        )

        table(
            cur,
            "PAGE 1 BAR -- relative price and rank, as the bar must sort them",
            "Two checks in one table. The rank column of the report must match\n"
            "`rank` here exactly, and the bar must be in this order. The multiple\n"
            "must sit inside the fixed 0-3.5x axis: the whole archive runs 0.51x\n"
            "to 3.29x, so a bar at the edge means the axis was left on auto.",
            """
            with island as (
                select property_type_code, median_price::numeric as island_price
                from marts.fact_market f join marts.dim_geography g using (geography_key)
                where g.geography_type = 'island'
                  and f.edition_year = %s and f.edition_quarter = %s
                  and f.median_price is not null
            )
            select p.name_en                                             as property_type,
                   g.name                                                as sector,
                   -- dense_rank, not rank: the DAX measure uses RANKX ( .., DENSE ),
                   -- and 13 pairs of sectors share an identical median somewhere in
                   -- the archive. With plain rank() the two would disagree by one
                   -- place after every tie -- a false failure at acceptance time.
                   dense_rank() over (partition by p.name_en
                                      order by f.median_price desc)      as rank,
                   round(f.median_price::numeric / i.island_price, 2)    as x_island,
                   f.median_price_value_status                           as price_status
            from marts.fact_market f
            join marts.dim_property_type p using (property_type_code)
            join marts.dim_geography g using (geography_key)
            join island i using (property_type_code)
            where g.geography_type = 'apciq_sector'
              and f.edition_year = %s and f.edition_quarter = %s
              and f.median_price is not null
            order by p.sort_order, rank
            """,
            (year, quarter, year, quarter),
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
            f"PAGE 3 -- KPI row AND map colours, which must add up to eighteen",
            "within_reach + borderline + out_of_reach + no_price = 18. Four counts,\n"
            "one definition each. If Power BI shows a blank rather than a zero in\n"
            "any of them, the measure is missing its IF ( ISBLANK ( .. ), 0, .. ) --\n"
            "COUNTROWS and DISTINCTCOUNT both return blank over an empty set, and\n"
            "no sector is within reach at the low end of the slicer.\n"
            "\n"
            "The same four counts are the map's four colour classes, because the map\n"
            "reads Sector bar colour, which reads Verdict for this income. Counting\n"
            "shapes of each shade must reproduce this row -- and a shape that failed\n"
            "to join carries no colour at all, so the four would fall short of 18.",
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

        table(
            cur,
            "PAGE 2 -- The theoretical income, and what it changes",
            "Added in J4.2-3/4 step 1. The report now shows the THEORETICAL\n"
            "income: the 2020 census median restated into dollars of the quarter\n"
            "by the Montreal CPI. The second share is what the report displayed\n"
            "before, and the gap between them is the result of that session.\n"
            "\n"
            "COUNT DISTINCT TRACTS, NOT ROWS. The shared tract 4620511.02 is one\n"
            "tract and two rows: a row count returns 513 where a tract count\n"
            "returns 512, and both are right about different questions.",
            """
            select edition_label,
                   count(distinct ct_uid)
                       filter (where meets_income_requirement_indexed is not null)
                                                                    as evaluated,
                   round(100.0 * count(distinct ct_uid)
                       filter (where meets_income_requirement_indexed)
                       / nullif(count(distinct ct_uid)
                       filter (where meets_income_requirement_indexed is not null), 0), 1)
                                                                    as share_theoretical_pct,
                   round(100.0 * count(distinct ct_uid)
                       filter (where meets_income_requirement)
                       / nullif(count(distinct ct_uid)
                       filter (where meets_income_requirement is not null), 0), 1)
                                                                    as share_2020_dollars_pct
            from marts.fact_affordability
            where property_type_code = 'condo'
              and household_profile_code = 'couple'
              and (edition_year, edition_quarter) in
                  ((2019,2),(2022,2),(2023,4),(2026,2))
            group by edition_label, edition_year, edition_quarter
            order by edition_year, edition_quarter
            """,
        )

        table(
            cur,
            "PAGE 2 -- The CPI factor behind the theoretical income",
            "What the Income basis note card must show. Below 1.0 before 2020:\n"
            "the index deflates towards the past. A card reading 1.000 on every\n"
            "quarter means the measure lost its filter context.\n"
            "\n"
            "A quarter without its three months has NO factor and reads\n"
            "not_indexed -- never 1.0, which would assert that no inflation had\n"
            "occurred. 2026 Q3 is already in that state.",
            """
            select ref_year || ' Q' || ref_quarter    as quarter,
                   months_observed,
                   round(index_factor, 4)             as factor,
                   index_basis,
                   coalesce(not_indexed_reason, '')   as reason
            from staging.int_statcan__cpi_quarterly_index
            where (ref_year, ref_quarter) in
                  ((2019,2),(2022,2),(2023,4),(2026,1),(2026,2),(2026,3))
            order by ref_year, ref_quarter
            """,
        )

        table(
            cur,
            "PLACE SLICER -- what each place actually puts on screen",
            "Added in J4.2-3/4 step 2. Choosing a place selects its APCIQ\n"
            "sector(s), and a sector usually holds more than one place. Only 8\n"
            "of the 34 places show exactly what was asked for.\n"
            "\n"
            "This is what Selected area disclosure must say. extra_places is\n"
            "the count the card names; the last column is what it lists.",
            """
            with reached as (
              select c.admin_name                             as chosen,
                     count(distinct c.apciq_sector_number)    as sectors,
                     count(distinct b.admin_name) - 1         as extra_places,
                     string_agg(distinct b.admin_name, ', ')  as everything_shown
              from marts.bridge_apciq_sector_geography c
              join marts.bridge_apciq_sector_geography b
                on b.apciq_sector_number = c.apciq_sector_number
              group by c.admin_name)
            select chosen, sectors, extra_places, left(everything_shown, 66) as everything_shown
            from reached
            where chosen in ('Rosemont-La Petite-Patrie', 'Westmount',
                             'Beaconsfield', 'Verdun')
               or extra_places = 6
               or chosen in (select admin_name
                             from marts.bridge_apciq_sector_geography
                             where coverage = 'part')
            order by extra_places desc, chosen
            """,
        )

        table(
            cur,
            "PLACE SLICER -- the plex acceptance case",
            "16 of the 34 places have NO published plex price in any quarter.\n"
            "The KPI row must read -- with Price status, never 0.\n"
            "\n"
            "COUNT PLACES, NOT BRIDGE ROWS. The study printed 17 because it\n"
            "counted the 36 rows: Verdun's Ile-des-Soeurs row has no plex price\n"
            "ever, but its Le Sud-Ouest row has all 29, and choosing Verdun\n"
            "reaches both. 16 is the figure this page is accepted against.",
            """
            with place_price as (
              select b.admin_name, f.property_type_code,
                     count(*) filter (where f.median_price is not null) as priced_quarters
              from marts.bridge_apciq_sector_geography b
              join marts.fact_market f on f.geography_key = b.apciq_geography_key
              group by 1, 2)
            select property_type_code,
                   count(*) filter (where priced_quarters = 0)  as places_never_priced,
                   count(*) filter (where priced_quarters = 29) as places_all_29_quarters,
                   count(*)                                     as places
            from place_price
            group by 1
            order by 1
            """,
        )

        table(
            cur,
            "PLACE SLICER -- the island switch must stay exclusive",
            "Sales (selected area) switches between the island aggregate and\n"
            "the sector rows; it must never show their union. The ratio below\n"
            "is what dropping the filter instead of switching it would cost.\n"
            "\n"
            "Exactly 2.0000 on sales is the J3.2 reconciliation seen from the\n"
            "other end: the 18 sectors tile the island.",
            """
            select property_type_code,
                   round(min(ratio), 4) as min_ratio,
                   round(max(ratio), 4) as max_ratio
            from (
              select property_type_code, edition_label,
                     sum(sales_count)::numeric
                       / nullif(sum(sales_count) filter (where is_island_aggregate), 0) as ratio
              from marts.fact_market
              group by 1, 2
              having sum(sales_count) filter (where is_island_aggregate) > 0
            ) r
            group by 1
            order by 1
            """,
        )

        print(f"\n{'=' * 78}")
        print("Every figure above is read from marts at run time. If a Power BI card")
        print("disagrees with one of them, the card is wrong -- not this script.")
        print("Do not paste this output anywhere.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
