/*
    Every quarter the market model carries should have a price index factor,
    and this says so out loud rather than letting a gap appear as an empty
    visual.

    WHY THIS IS NOT PARANOIA

    The CPI is published monthly, roughly three weeks after the month ends.
    APCIQ publishes quarterly. On 2026-08-31 the CPI reached 2026-07, so
    2026 Q3 already exists with one month of three -- and the next APCIQ
    edition will land before the September CPI does. When that happens this
    test fails, and that is the correct behaviour: it says a quarter of
    prices arrived that cannot be put in today's dollars yet, which is a fact
    someone must see before a dashboard shows it as a hole.

    It is deliberately NOT a freshness test. dbt freshness asks "when did we
    last load this source", and the answer would be "an hour ago" while this
    exact gap existed. Same lesson as the rate freshness warning in J4.2.

    A dbt test passes when it returns no rows.
*/

with market_quarters as (

    select distinct
        edition_year,
        edition_quarter,
        edition_label
    from {{ ref('fact_market') }}

),

index_by_quarter as (

    select
        ref_year,
        ref_quarter,
        index_factor,
        months_observed,
        not_indexed_reason
    from {{ ref('int_statcan__cpi_quarterly_index') }}

)

select
    market_quarters.edition_label,
    coalesce(
        index_by_quarter.not_indexed_reason,
        'no CPI row at all for this quarter'
    )                                                       as problem

from market_quarters
left join index_by_quarter
       on index_by_quarter.ref_year    = market_quarters.edition_year
      and index_by_quarter.ref_quarter = market_quarters.edition_quarter

where index_by_quarter.index_factor is null
