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



# ----------------------------------------------------------------------------
# The mortgage chain, with the down payment as a free parameter.
#
# fact_mortgage_scenario holds ONE scenario: the legal minimum down payment.
# Page 3 lets the reader type another, and computes the rest in DAX. So the
# oracle has to be able to compute the same thing, at any down payment, or
# there is nothing to check the page against.
#
# This is the chain that was validated on 2026-09-09 by feeding it the legal
# minimum: it reproduced all four money columns of the mart to the cent on the
# 1 223 rows that carry a price. _reproduction_sql() below re-runs that check
# on every invocation, so the two cannot drift apart in silence.
# ----------------------------------------------------------------------------

_CHAIN = """
with grid as ({grid}),

parameter as (
    select
        max(case when parameter_name = 'gds_max_ratio'
                 then parameter_value end) / 100.0 as gds_max_ratio,
        max(case when parameter_name = 'qualifying_rate_buffer'
                 then parameter_value end)         as buffer_insured,
        max(case when parameter_name = 'qualifying_rate_floor'
                 then parameter_value end)         as floor_insured,
        max(case when parameter_name = 'qualifying_rate_buffer_uninsured'
                 then parameter_value end)         as buffer_uninsured,
        max(case when parameter_name = 'qualifying_rate_floor_uninsured'
                 then parameter_value end)         as floor_uninsured,
        max(case when parameter_name = 'max_amortization_years_standard'
                 then parameter_value end)         as amortization_years,
        max(case when parameter_name = 'interest_compounding_periods_per_year'
                 then parameter_value end)         as compounding_per_year
    from marts.mortgage_underwriting_parameter
),

base as (
    select s.area_code, s.geography_key, s.property_type_code, s.edition_label,
           s.median_price, s.contract_rate_percent, s.minimum_down_payment,
           s.loan_amount                     as mart_loan_amount,
           s.insurance_premium               as mart_premium,
           s.monthly_payment_qualifying_rate as mart_payment,
           s.income_required_lower_bound     as mart_income_required
    from marts.fact_mortgage_scenario s
    where 1 = 1 {where}
),

scenario as (
    select base.*, parameter.*, {down_expr} as down_payment
    from base cross join parameter cross join grid
),

with_ltv as (
    select scenario.*,
           scenario.median_price - scenario.down_payment as loan_before_premium,
           (scenario.median_price - scenario.down_payment)
               / nullif(scenario.median_price, 0)::numeric as loan_to_value
    from scenario
),

with_band as (
    select with_ltv.*, band.premium_rate
    from with_ltv
    left join marts.mortgage_insurance_premium_band band
           on band.amortization_years = with_ltv.amortization_years
          and band.down_payment_kind  = 'traditional'
          and with_ltv.loan_to_value  >  band.ltv_from - 0.0001
          and with_ltv.loan_to_value <= band.ltv_to
),

regime as (
    /*
        THE LEGALITY GUARD COMES FIRST, and the order is the point.
        Written the other way round, a down payment below the legal minimum
        pushes the LTV past 95 per cent, where no band exists, and a coalesce
        reads the missing band as a premium of zero. Section 13.6.

        -1 is "a band was expected and none was found". It must never occur:
        once the down payment is at or above the legal minimum, the LTV cannot
        exceed 95 per cent.
    */
    select with_band.*,
        case
            when median_price is null                 then 0
            when down_payment >= median_price         then 1
            when down_payment <  minimum_down_payment then 2
            when loan_to_value <= 0.80                then 3
            when premium_rate is not null             then 4
            else -1
        end as regime
    from with_band
),

money as (
    select regime.*,
        case when regime.regime = 4
             then round(regime.loan_before_premium * regime.premium_rate, 2)
             when regime.regime = 3 then 0::numeric end as premium,
        case when regime.regime in (3, 4)
             then greatest(
                    regime.contract_rate_percent
                      + case when regime.regime = 3 then regime.buffer_uninsured
                             else regime.buffer_insured end,
                    case when regime.regime = 3 then regime.floor_uninsured
                         else regime.floor_insured end)
             end as qualifying_rate_percent
    from regime
),

compounded as (
    select money.*,
        money.loan_before_premium + coalesce(money.premium, 0) as loan_amount,
        power(1 + (money.qualifying_rate_percent / 100.0
                   / money.compounding_per_year)::double precision,
              (money.compounding_per_year / 12.0)::double precision) - 1 as monthly_rate
    from money
),

paid as (
    select compounded.*,
        case when regime in (3, 4) then
            round((loan_amount::double precision * monthly_rate
                   / (1 - power(1 + monthly_rate,
                                -(amortization_years * 12)::double precision)))::numeric, 2)
        end as payment_qualifying
    from compounded
),

final as (
    /*
        The payment is rounded to the cent BEFORE the division by the GDS
        ratio, exactly as fact_mortgage_scenario.sql does it. Rounding once at
        the end instead moves the answer by a few dollars per sector.
    */
    select paid.*,
        case when payment_qualifying is not null
             then round(payment_qualifying * 12 / gds_max_ratio, 2) end as income_required
    from paid
)
"""

# The six classes of section 13.8, written once. The 10 per cent band is a
# display convention of this project, and this is the only place the oracle
# states it.
_VERDICT = """
        case
            when regime = 0 then 'No published price'
            when regime = 1 then 'Cash purchase'
            when regime = 2 then 'Below the legal minimum'
            when income_required is null then 'Not evaluated'
            when %s >= income_required * 1.10 then 'Within reach'
            when %s >= income_required then 'Borderline'
            else 'Out of reach'
        end
"""


def _down_payment_chain(grid: str, where: str) -> str:
    """One row per sector, at the down payment `grid` yields."""
    return _CHAIN.format(grid=grid, where=where, down_expr="grid.down_payment") + f"""
    select property_type_code,
           area_code,
           regime,
           round(loan_to_value, 4) as ltv,
           -- Shown only where it is APPLIED. The band lookup succeeds below
           -- 80 per cent LTV too, and printing that rate beside a premium of
           -- zero is how the mart's own insurance_premium_rate column misleads
           -- on its 29 not_insurable rows.
           case when regime = 4 then premium_rate end as premium_rate,
           premium,
           income_required,
           {_VERDICT} as verdict
    from final
    order by property_type_code, income_required nulls last, area_code
    """


def _verdict_grid_sql() -> str:
    """The six counts, at seven slider positions, for the three property types."""
    return _CHAIN.format(
        grid="select * from (values (0), (25000), (50000), (100000), (150000), "
             "(200000), (300000)) as g(down_payment)",
        where="and not s.is_island_aggregate "
              "and s.edition_year = %s and s.edition_quarter = %s",
        down_expr="grid.down_payment",
    ) + f"""
    select down_payment,
           property_type_code,
           count(*) filter (where verdict = 'Within reach')            as within_reach,
           count(*) filter (where verdict = 'Borderline')              as borderline,
           count(*) filter (where verdict = 'Out of reach')            as out_of_reach,
           count(*) filter (where verdict = 'Below the legal minimum') as below_minimum,
           count(*) filter (where verdict = 'Cash purchase')           as cash,
           count(*) filter (where verdict = 'No published price')      as no_price,
           count(*) filter (where verdict = 'Not evaluated')           as not_evaluated,
           count(*)                                                    as total
    from (select down_payment, property_type_code, {_VERDICT} as verdict from final) v
    group by 1, 2
    order by 1, 2
    """


def _kpi_and_shapes_sql(down_payment: int) -> str:
    """The six verdict classes, counted as sectors AND as drawn shapes.

    Rewritten on 2026-09-09. It used to classify income_required_lower_bound,
    which is the mart's own scenario -- the LEGAL MINIMUM down payment. Page 3
    stopped reading that column the moment the slider was built, so the block
    was computing the colours of a map the report no longer draws. It now runs
    the same parameterised chain as every other page-3 block, at the same down
    payment.
    """
    return _CHAIN.format(
        grid="select %d as down_payment" % int(down_payment),
        where="and not s.is_island_aggregate "
              "and s.edition_year = %s and s.edition_quarter = %s",
        down_expr="grid.down_payment",
    ) + f"""
    select coalesce(v.property_type_code, '')                  as property_type_code,
           coalesce(v.verdict, 'TOTAL -- 18 sectors, 36 shapes') as verdict,
           count(distinct v.area_code)                         as sectors,
           count(m.place_key)                                  as shapes
    from (
        select property_type_code, area_code, geography_key,
               {_VERDICT} as verdict
        from final
    ) v
    join marts.map_place m on m.apciq_geography_key = v.geography_key
    group by rollup (v.property_type_code, v.verdict)
    having grouping(v.property_type_code) = 0
    order by v.property_type_code, v.verdict nulls last
    """


def _reproduction_sql() -> str:
    """Fed the legal minimum, the chain must land on the mart. Every count 0."""
    return _CHAIN.format(
        grid="select 1 as unused",
        where="",
        down_expr="base.minimum_down_payment",
    ) + """
    select count(*)                                                          as rows_compared,
           count(*) filter (where abs(loan_amount - mart_loan_amount) > 0.01) as loan_differs,
           count(*) filter (where abs(coalesce(premium, 0)
                                      - coalesce(mart_premium, 0)) > 0.01)    as premium_differs,
           count(*) filter (where abs(payment_qualifying - mart_payment) > 0.01)
                                                                              as payment_differs,
           count(*) filter (where abs(income_required - mart_income_required) > 0.01)
                                                                              as income_differs,
           count(*) filter (where regime = -1)                                as band_not_found,
           count(*) filter (where regime = 2)                                 as below_minimum
    from final
    where median_price is not null
    """


# ----------------------------------------------------------------------------
# The quarter-over-quarter badges of section 14, added 2026-09-10.
#
# Almost everything else this script checks is an observation read out of a
# mart. A badge is a DERIVATION, so the oracle has to compute it the same way
# the DAX does or it is not a check at all. Three things are therefore
# reproduced literally rather than approximated:
#
#   - the direction comes off the sign and the number is shown unsigned, because
#     a badge reading "down -4.2 %" says it twice;
#   - a badge that cannot be computed prints as ABSENT, never as 0. That is the
#     blank/zero trap, and printing a 0 here would licence a 0 on screen;
#   - green means FAVOURABLE TO A FIRST-TIME BUYER, not "up". A rising price is
#     unfavourable; a lengthening time on market is favourable, because it is
#     time to decide.
# ----------------------------------------------------------------------------

_BADGE_METRICS = (
    # metric key,           card label,            a rise favours the buyer
    ("sales_count",         "Sales",               False),
    ("median_price",        "Median price",        False),
    ("days_on_market",      "Days on market",      True),
    ("months_of_inventory", "Months of inventory", True),
)


def _badge_sql() -> str:
    """What each page-1 badge must read, on the island row.

    Section 16: the comparison is the SAME QUARTER ONE YEAR EARLIER, joined on
    the date rather than taken by row offset, so a missing quarter cannot shift
    the window silently.
    """
    branches = []
    for metric, label, higher_is_better in _BADGE_METRICS:
        favourable = ">" if higher_is_better else "<"
        branches.append(f"""
            select '{label}'                                    as card,
                   round(now_value, 2)                          as this_quarter,
                   round(prev_value, 2)                         as a_year_earlier,
                   case when prev_value is null or now_value is null
                             or prev_value = 0 then null
                        else round(100.0 * (now_value - prev_value)
                                   / prev_value, 1) end         as movement_pct,
                   case when prev_value is null or now_value is null
                             or prev_value = 0 then 'ABSENT -- no badge'
                        when now_value > prev_value then 'up'
                        when now_value < prev_value then 'down'
                        else 'flat' end                         as direction,
                   case when prev_value is null or now_value is null
                             or prev_value = 0 then '(none)'
                        when now_value = prev_value then '#8FA3B5'
                        when now_value - prev_value {favourable} 0 then '#B8E0C5'
                        else '#FA584C' end                      as colour
            from windowed
            where metric = '{metric}' and quarter_start_date = %s""")
    return f"""
        with island as (
            select f.quarter_start_date, f.sales_count, f.median_price,
                   f.days_on_market,
                   -- Months of inventory is APCIQ's own definition: the
                   -- inventory over the average monthly sales of the PAST
                   -- TWELVE MONTHS, not of the quarter. Sales are seasonal,
                   -- so a quarterly denominator swings with the calendar.
                   t.active_listings::numeric              as listings_12m,
                   t.sales_count::numeric                  as sales_12m,
                   t.active_listings_corroboration         as corroboration_12m
            from marts.fact_market f
            left join marts.fact_market_trailing_12m t
              on t.geography_key = f.geography_key
             and t.property_type_code = f.property_type_code
             and t.edition_quarter_start_date = f.quarter_start_date
            where f.is_island_aggregate and f.property_type_code = %s
        ),
        long as (
            select quarter_start_date, 'sales_count' as metric,
                   sales_count::numeric as v from island
            union all select quarter_start_date, 'median_price',
                   median_price::numeric from island
            union all select quarter_start_date, 'days_on_market',
                   days_on_market::numeric from island
            -- Months of inventory REFUSES on a contradicted quarter: the ratio
            -- is ours, derived from a numerator the mart calls unreliable, and
            -- on those quarters it lands inside the trend where nothing shows.
            union all select quarter_start_date, 'months_of_inventory',
                   case when corroboration_12m = 'corroborated'
                             and sales_12m > 0
                        then listings_12m / (sales_12m / 12.0)
                   end
            from island
        ),
        windowed as (
            select l.metric, l.quarter_start_date, l.v as now_value,
                   y.v                                as prev_value
            from long l
            left join long y
              on y.metric = l.metric
             and y.quarter_start_date
                 = l.quarter_start_date - interval '12 months'
        )
        {" union all ".join(branches)}
    """


def _badge_absent_sql() -> str:
    """Where a badge must VANISH. The island never exercises this guard.

    Section 16: the predecessor is twelve months back, so the opening FOUR
    quarters of the archive have none at all -- 2019 Q2 through 2020 Q1.
    """
    return """
        with s as (
            select f.property_type_code, f.geography_key, f.quarter_start_date,
                   f.median_price,
                   y.median_price as price_a_year_earlier
            from marts.fact_market f
            left join marts.fact_market y
              on y.geography_key = f.geography_key
             and y.property_type_code = f.property_type_code
             and y.quarter_start_date
                 = f.quarter_start_date - interval '12 months'
            where not f.is_island_aggregate
        )
        select property_type_code                                    as property_type,
               count(*) filter (
                   where quarter_start_date >= '2020-04-01')         as sector_quarters,
               count(*) filter (where median_price is not null
                                  and price_a_year_earlier is null
                                  and quarter_start_date >= '2020-04-01')
                                                                     as badge_must_vanish,
               count(*) filter (where median_price is not null
                                  and price_a_year_earlier is not null
                                  and quarter_start_date >= '2020-04-01')
                                                                     as badge_must_show,
               count(*) filter (
                   where quarter_start_date < '2020-04-01')          as opening_year_no_badge
        from s group by 1 order by 1
    """


def _badge_refusal_sql() -> str:
    """The quarters where the inventory card must be EMPTY, and those where
    only its badge must refuse.

    Section 16.4 moved the refusal onto the VALUE: months of inventory is ours,
    not APCIQ's, so a contradicted numerator cannot be shown at all. The badge
    then refuses by itself, plus on the quarters whose predecessor is defective.
    """
    return """
        with t12 as (
            select t.edition_quarter_start_date        as quarter_start_date,
                   t.property_type_code,
                   t.active_listings::numeric          as listings_12m,
                   t.sales_count::numeric              as sales_12m,
                   t.active_listings_corroboration,
                   t.sales_count
            from marts.fact_market_trailing_12m t
            join marts.dim_geography g on g.geography_key = t.geography_key
            where g.geography_type = 'island'
        ),
        s as (
            select d.quarter_label, f.quarter_start_date,
                   f.active_listings_corroboration                  as this_quarter_verdict,
                   y.active_listings_corroboration                  as verdict_a_year_earlier,
                   case when f.active_listings_corroboration = 'corroborated'
                             and f.sales_count > 0
                        then round((f.listings_12m / (f.sales_12m / 12.0)), 1)
                   end                                              as months_of_inventory
            from t12 f
            join marts.dim_date d on d.date_key = f.quarter_start_date
            left join t12 y
              on y.property_type_code = f.property_type_code
             and y.quarter_start_date
                 = f.quarter_start_date - interval '12 months'
            where f.property_type_code = %s
        )
        select quarter_label, this_quarter_verdict, verdict_a_year_earlier,
               months_of_inventory,
               case when this_quarter_verdict <> 'corroborated'
                    then 'CARD EMPTY -- its own inventory figure'
                    else 'badge only -- the quarter it subtracts' end as what_must_happen
        from s
        where this_quarter_verdict <> 'corroborated'
           or verdict_a_year_earlier <> 'corroborated'
        order by quarter_start_date
    """


def _inventory_regime_sql() -> str:
    """Months of inventory over the whole archive, with APCIQ's own thresholds.

    Formula and bands are the publisher's, quoted in docs/apciq.md section 4:
    under 8 months favours sellers, 8 to 10 is balanced, above 10 favours
    buyers. The arithmetic is ours -- APCIQ does not print this per sector, so
    no control total covers it and it inherits the inventory column's verdicts.
    """
    return """
        select d.quarter_label,
               p.name_en                                            as property_type,
               case when t.active_listings_corroboration = 'corroborated'
                         and t.sales_count > 0
                    then round((t.active_listings::numeric
                                / (t.sales_count::numeric / 12.0))::numeric, 1)
               end                                                  as months_of_inventory,
               case when t.active_listings_corroboration <> 'corroborated'
                    then 'CARD EMPTY -- publisher contradicts the inventory'
                    when t.active_listings::numeric
                         / nullif(t.sales_count::numeric / 12.0, 0) < 8
                         then 'Seller''s market'
                    when t.active_listings::numeric
                         / nullif(t.sales_count::numeric / 12.0, 0) <= 10
                         then 'Balanced market'
                    else 'Buyer''s market' end                      as market_condition
        from marts.fact_market_trailing_12m t
        join marts.dim_geography g on g.geography_key = t.geography_key
        join marts.dim_property_type p on p.property_type_code = t.property_type_code
        join marts.dim_date d on d.date_key = t.edition_quarter_start_date
        where g.geography_type = 'island' and t.property_type_code = %s
        order by t.edition_quarter_start_date
    """


def _badge_page2_sql() -> str:
    """The page-2 cards. The share moves in POINTS, never per cent.

    Section 16.6: `Tracts evaluated` left the KPI row for the detail line, and
    the median tract's theoretical income took its place -- WITH NO BADGE,
    because the 2020 census median behind it is a single value across all
    twenty-nine quarters and a badge on it would report the CPI and nothing else.
    """
    return """
        with per_tract as (
            -- One row per DISTINCT tract, because MEDIANX iterates
            -- VALUES ( Census_Tract[...] ). The shared tract carries two rows
            -- in the fact: taking the median over rows would disagree with the
            -- card by a false margin, the same class as rank() against
            -- RANKX ( .., DENSE ).
            select quarter_start_date, ct_uid,
                   max(household_income_indexed) as income_indexed,
                   max(household_income)         as income_2020
            from marts.fact_affordability
            where property_type_code = %s and household_profile_code = %s
            group by 1, 2
        ),
        incomes as (
            select quarter_start_date,
                   percentile_cont(0.5) within group (
                       order by income_indexed)                      as median_tract_income,
                   percentile_cont(0.5) within group (
                       order by income_2020)                         as median_tract_income_2020
            from per_tract group by 1
        ),
        base as (
            select quarter_start_date,
                   100.0 * count(distinct ct_uid) filter (
                       where meets_income_requirement_indexed)
                     / nullif(count(distinct ct_uid) filter (
                       where meets_income_requirement_indexed is not null), 0)
                                                                     as share,
                   count(distinct ct_uid) filter (
                       where meets_income_requirement_indexed is not null)
                                                                     as evaluated,
                   avg(income_required_lower_bound)                  as required
            from marts.fact_affordability
            where property_type_code = %s and household_profile_code = %s
            group by 1
        ),
        q as (
            select b.*, i.median_tract_income, i.median_tract_income_2020
            from base b join incomes i using (quarter_start_date)
        ),
        w as (
            select c.*,
                   y.share     as prev_share,
                   y.evaluated as prev_evaluated,
                   y.required  as prev_required
            from q c
            left join q y
              on y.quarter_start_date
                 = c.quarter_start_date - interval '12 months'
        ),
        here as (select * from w where quarter_start_date = %s)
        select 'Share of tracts within reach  [POINTS, badge]'   as card,
               round(share::numeric, 1)                          as this_quarter,
               round(prev_share::numeric, 1)                     as a_year_earlier,
               round((share - prev_share)::numeric, 1)           as movement,
               case when prev_share is null then '(none)'
                    when share > prev_share then '#B8E0C5'
                    when share < prev_share then '#FA584C'
                    else '#8FA3B5' end                           as colour
        from here
        union all
        select 'Income required, lower bound  [PER CENT, badge]',
               round(required::numeric, 0), round(prev_required::numeric, 0),
               round((100.0 * (required - prev_required)
                      / nullif(prev_required, 0))::numeric, 1),
               case when prev_required is null then '(none)'
                    when required < prev_required then '#B8E0C5'
                    when required > prev_required then '#FA584C'
                    else '#8FA3B5' end
        from here
        union all
        select 'Median tract income  [NO BADGE; col. 2 is the 2020 median, not last year]',
               round(median_tract_income::numeric, 0),
               round(median_tract_income_2020::numeric, 0),
               null,
               '(none -- a badge here would report the CPI)'
        from here
        union all
        select 'Tracts evaluated  [detail line, not a badge]',
               evaluated::numeric, prev_evaluated::numeric,
               (evaluated - prev_evaluated)::numeric,
               '(none)'
        from here
    """


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
    parser.add_argument(
        "--down-payment",
        type=int,
        default=50_000,
        help="down payment for page 3, in dollars. Defaults to the opening "
             "position of the Down payment input slider.",
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
            "PAGE 3 -- KPI row AND map colours, at the typed down payment",
            "Six classes now, not four, and they must add up to 18 sectors and\n"
            "36 shapes on every property type. The two new ones are refusals:\n"
            "Below the legal minimum and Cash purchase. A measure applying its own\n"
            "threshold instead of reading the verdict shows up here as a total\n"
            "that is not 18.\n"
            "\n"
            "⚠️ COMPUTED AT THE DOWN PAYMENT PASSED TO THIS SCRIPT, not at the\n"
            "legal minimum. Until 2026-09-09 this block classified\n"
            "income_required_lower_bound, which is the mart's own scenario -- the\n"
            "legal minimum. Page 3 stopped reading that column when the slider was\n"
            "built, so the block was printing the colours of a map the report no\n"
            "longer draws. Pass --down-payment to match the slider on screen.\n"
            "\n"
            "⚠️ THE MAP DOES NOT COUNT EIGHTEEN. Page 3 draws the 36 administrative\n"
            "places, not the 18 sectors, so the shapes column is what to count on\n"
            "screen. The KPI cards still count sectors: more blue shapes than the\n"
            "card reads is correct, and the text box under the map is what tells\n"
            "the reader not to count patches.\n"
            "\n"
            "⚠️ A blank rather than a zero in any KPI card means the measure is\n"
            "missing its IF ( ISBLANK ( .. ), 0, .. ). COUNTROWS returns blank over\n"
            "an empty set, and at the low end of the slider two of the three\n"
            "counting measures are legitimately zero.",
            _kpi_and_shapes_sql(args.down_payment),
            (year, quarter, args.income, args.income),
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
            "PAGE 2 -- The shortfall map, and the cross-check it makes possible",
            "Added 2026-09-02, when the map stopped colouring the price-to-income\n"
            "ratio and started colouring the shortfall in dollars, diverging at\n"
            "zero.\n"
            "\n"
            "THE POINT OF THIS BLOCK: the share of BLUE shapes must equal the\n"
            "Share of tracts affordable card sitting above the map. Colour and\n"
            "KPI now answer the same question, so a disagreement is visible\n"
            "without opening a measure -- which the ratio never allowed.\n"
            "\n"
            "plex / one_person is the acceptance case: no blue shape at all. An\n"
            "entirely red map is the message, not a scale fault.\n"
            "\n"
            "COUNT ROWS HERE, NOT TRACTS. A shape is a tract, but the shared\n"
            "tract 4620511.02 is drawn once and carries two rows; it is painted\n"
            "violet by its own branch, so it is neither blue nor red.",
            """
            select property_type_code || ' / ' || household_profile_code   as view,
                   count(*) filter (where income_shortfall_indexed < 0)    as blue,
                   count(*) filter (where income_shortfall_indexed >= 0)   as red,
                   count(*)                                                as shaded,
                   round(100.0 * count(*) filter (where income_shortfall_indexed < 0)
                         / nullif(count(*), 0), 1)                         as blue_pct
            from marts.fact_affordability
            where edition_year = 2026 and edition_quarter = 2
              and income_shortfall_indexed is not null
            group by 1
            order by blue_pct desc
            """,
        )

        table(
            cur,
            "PAGE 2 -- One threshold, two measures: they must never disagree",
            "The map colours on the SIGN of income_shortfall_indexed; the KPI\n"
            "counts meets_income_requirement_indexed. Two readings of one\n"
            "threshold is exactly what diverged on 44 of 87 slices on page 3 on\n"
            "2026-08-30, so this checks they are the same statement.\n"
            "\n"
            "disagreements must be 0. Anything else means the mart carries two\n"
            "definitions and the map contradicts the card above it.",
            """
            select count(*) filter (
                       where meets_income_requirement_indexed
                             <> (income_shortfall_indexed < 0)) as disagreements,
                   count(*)                                     as rows_compared
            from marts.fact_affordability
            where meets_income_requirement_indexed is not null
              and income_shortfall_indexed is not null
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

        # ------------------------------------------------------------------
        # J4.2 3/4 . 3 -- the typed down payment. Section 13 of report-design.
        # ------------------------------------------------------------------

        table(
            cur,
            f"PAGE 3 -- The typed down payment, at {args.down_payment:,} $",
            "One row per sector, in the order the bar chart draws them, for all\n"
            "THREE property types -- the page shows one at a time. The DAX chain\n"
            "of section 13.7 must reproduce income_required to the cent.\n"
            "\n"
            "regime is what Down payment regime code returns:\n"
            "  0 no published price   1 cash purchase   2 below the legal minimum\n"
            "  3 uninsured            4 insured",
            _down_payment_chain(
                "select %s::numeric as down_payment",
                "and s.edition_year = %s and s.edition_quarter = %s",
            ),
            (args.down_payment, year, quarter, args.income, args.income),
        )

        table(
            cur,
            "PAGE 3 -- The six verdict classes must total 18",
            "The arithmetic check of the page, at seven slider positions. It was\n"
            "four counts totalling eighteen before the down payment existed; the\n"
            "two refusals are new.\n"
            "\n"
            "A row that does not total 18 means a measure applied its own\n"
            "threshold instead of reading [Verdict at this down payment].\n"
            "\n"
            "Two cases are worth looking for by name:\n"
            "  - at 0 $, every priced sector is below the legal minimum\n"
            "  - at 300 000 $, single-family STILL refuses one sector. Those are\n"
            "    the medians at or above 1.5 M$, where the minimum is 20 per cent.",
            _verdict_grid_sql(),
            (year, quarter, args.income, args.income),
        )

        table(
            cur,
            "PAGE 3 -- The chain fed the legal minimum must reproduce the mart",
            "The probe that licenses every formula of section 13, re-run here so\n"
            "it keeps being true. The same chain, given the down payment the mart\n"
            "assumed, has to land on the mart's own figures.\n"
            "\n"
            "Every count below must be 0. A non-zero one means the SQL here and\n"
            "fact_mortgage_scenario.sql have drifted apart -- and since the DAX\n"
            "was transcribed from this chain, the report drifted with it.",
            _reproduction_sql(),
            (),
        )

        quarter_start = f"{year}-{quarter * 3 - 2:02d}-01"

        table(
            cur,
            "PAGE 1 -- the four year-over-year badges (island, condominium)",
            "Section 16. The badge under each KPI card, now comparing the SAME\n"
            "QUARTER ONE YEAR EARLIER. Compare the arrow, the\n"
            "size and the colour -- and read the number UNSIGNED, because the\n"
            "direction is in the arrow.\n"
            "\n"
            "A row printed ABSENT must show NO badge on screen. A card showing\n"
            "'0.0 %' there is the blank/zero trap, ninth appearance.\n"
            "\n"
            "Months of inventory = active listings / (sales / 3). The card is\n"
            "EMPTY, not zero, on the four quarters APCIQ contradicts.\n"
            "\n"
            "Colour is favourable TO A FIRST-TIME BUYER, not 'up': #B8E0C5 on a\n"
            "falling price and on a lengthening time on market, #FA584C on a\n"
            "rising price and on rising sales.",
            _badge_sql(),
            ("condo",) + (quarter_start,) * 4,
        )

        table(
            cur,
            "PAGE 1 -- where a price badge must VANISH, by property type",
            "The island exercises this guard ZERO times, so the report looks\n"
            "finished without it. The sectors do not.\n"
            "\n"
            "Section 16: the whole OPENING YEAR of the archive -- 2019 Q2 to\n"
            "2020 Q1 -- carries no badge on any card, on any geography. Four\n"
            "blank quarters is the honest cost of the twelve-month window and\n"
            "must not be repaired by falling back to the previous quarter.\n"
            "\n"
            "Select a sector on plex and step through the quarters: the badge has\n"
            "to disappear on the quarters where APCIQ published no price in the\n"
            "one before. If it shows a rise from nothing, the guard is missing.",
            _badge_absent_sql(),
            (),
        )

        table(
            cur,
            "PAGE 1 -- where the inventory card must be EMPTY, and where only\n"
            "its badge refuses",
            "active_listings_corroboration carries the J3.2 verdicts. Section\n"
            "16.4 puts the refusal on the VALUE: months of inventory is OUR\n"
            "figure, not one APCIQ printed, so a contradicted numerator cannot\n"
            "be shown at all.\n"
            "\n"
            "That matters because on those quarters the ratio lands INSIDE the\n"
            "surrounding trend -- around 3 months, exactly where a sound figure\n"
            "would sit. A wrong number that looks wrong costs nothing; this one\n"
            "looks right.\n"
            "\n"
            "The rows marked 'badge only' have a sound figure of their own and\n"
            "refuse because the quarter they SUBTRACT is defective.",
            _badge_refusal_sql(),
            ("condo",),
        )

        table(
            cur,
            "PAGE 1 -- months of inventory over the archive, and its regime",
            "APCIQ's formula, from its own glossary: the inventory over the\n"
            "average monthly sales of the PAST TWELVE MONTHS -- not of the\n"
            "quarter. Dividing by the quarter's sales was tried first and is\n"
            "wrong: sales are seasonal, and the two disagree by up to 3.5\n"
            "months on condo and 5.1 on plex, moving 11 of 75 island slices\n"
            "into a different market condition.\n"
            "\n"
            "The bands are the publisher's too: under 8 favours sellers, 8 to\n"
            "10 is balanced, above 10 favours buyers.\n"
            "\n"
            "Read the column top to bottom: it is a monotonic climb from the\n"
            "2022 trough to the end of the archive, with no seasonal swing.\n"
            "The quarterly version had one.",
            _inventory_regime_sql(),
            ("condo",),
        )

        table(
            cur,
            "PAGE 2 -- the KPI row (condominium, couple)",
            "The share badge is in POINTS. A share going from 40 to 44 has risen\n"
            "four points and ten per cent, and both sentences are true about\n"
            "different things.\n"
            "\n"
            "Tracts evaluated is the DENOMINATOR and no longer has a card: it\n"
            "is the detail line under the share. It stays on screen because on\n"
            "single-family it moves by 85 tracts on average and once by 258, so\n"
            "a share that moves ten points can be entirely tracts entering or\n"
            "leaving the base.\n"
            "\n"
            "The income card carries NO badge. Its 2020 census median is one\n"
            "single value across all twenty-nine quarters -- printed here beside\n"
            "it -- so every dollar of movement is the CPI factor and nothing\n"
            "else. A badge there would be an inflation gauge in a row of market\n"
            "indicators.",
            _badge_page2_sql(),
            ("condo", "couple", "condo", "couple", quarter_start),
        )

        print(f"\n{'=' * 78}")
        print("Every figure above is read from marts at run time. If a Power BI card")
        print("disagrees with one of them, the card is wrong -- not this script.")
        print("Do not paste this output anywhere.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
