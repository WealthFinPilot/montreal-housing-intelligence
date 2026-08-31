{{
    config(
        materialized = 'view'
    )
}}

/*
    One row per calendar quarter: the factor that restates a 2020 dollar into
    a dollar of that quarter.

        factor = mean CPI of the quarter's three months
                 -------------------------------------
                 mean CPI of the twelve months of 2020

    WHY 2020 IS THE BASE, AND WHY IT IS NOT A ROUND NUMBER PICKED HERE

    2020 is the INCOME YEAR of the 2021 census -- the year the household
    incomes in fact_affordability describe. The base is therefore fixed by the
    observation being restated, not chosen for convenience. If the model ever
    moves to a later census, this base moves with it, and
    assert_cpi_base_year_matches_the_census_income_year fails until it does.

    WHY A QUARTER NEEDS ALL THREE OF ITS MONTHS

    This is the blank-versus-zero trap the project has now met five times, and
    it is already present in today's data: on 2026-08-31 the CPI reached
    2026-07, so 2026 Q3 exists with ONE month of three. Averaging it would
    produce a perfectly plausible number that is not the average of that
    quarter, and no test downstream could tell the difference.

    So an incomplete quarter yields NULL, never a value, and never 1.0. A
    factor of 1.0 would be worse than a null: it would silently mean "no
    inflation since 2020" and every ratio built on it would look computed.

    fact_market currently stops at 2026 Q2, so nothing is affected today. The
    next APCIQ edition will arrive before the September CPI is published, and
    the guard has to exist before it is needed -- the same reason the rate
    freshness warning was written in J4.2.

    WHAT THIS MODEL DOES NOT DO

    It does not interpolate a missing month, and it does not carry the
    previous quarter forward. Section 41.1 of the brief forbids both.
*/

{% set census_income_year = 2020 %}

with monthly as (

    select
        ref_year,
        ref_quarter,
        ref_month,
        index_value,
        index_status
    from {{ ref('stg_statcan__consumer_price_index') }}

),

by_quarter as (

    select
        ref_year,
        ref_quarter,
        count(*)                                        as months_observed,
        avg(index_value)                                as quarter_index,
        min(ref_month)                                  as first_month,
        max(ref_month)                                  as last_month,
        -- A quarter is only as final as its least final month.
        count(*) filter (where index_status <> 'final') as months_not_final
    from monthly
    group by ref_year, ref_quarter

),

base as (

    /*
        The twelve months of the census income year. Guarded the same way a
        quarter is: if the base year is ever incomplete, every factor becomes
        null rather than being computed against a partial year.
    */
    select
        count(*)          as base_months_observed,
        avg(index_value)  as base_index
    from monthly
    where ref_year = {{ census_income_year }}

),

factors as (

    select
        by_quarter.ref_year,
        by_quarter.ref_quarter,
        by_quarter.months_observed,
        by_quarter.months_not_final,
        by_quarter.first_month,
        by_quarter.last_month,
        by_quarter.quarter_index,

        {{ census_income_year }}                        as base_year,
        base.base_index,
        base.base_months_observed,

        /*
            The factor, or nothing. Three conditions, all of them necessary:
            the quarter has its three months, the base year has its twelve,
            and the base is not zero. Anything else yields NULL.
        */
        case
            when by_quarter.months_observed = 3
             and base.base_months_observed = 12
             and base.base_index > 0
            then by_quarter.quarter_index / base.base_index
        end                                             as index_factor

    from by_quarter
    cross join base

)

select
    ref_year,
    ref_quarter,
    months_observed,
    months_not_final,
    first_month,
    last_month,
    quarter_index,
    base_year,
    base_index,
    base_months_observed,
    index_factor,

    /*
        The assumption, carried as a column so it travels with every row that
        uses it -- the same device as price_basis, assignment_method and
        is_posted_rate. A reader of one row never has to know this file
        exists to know what was assumed.
    */
    case
        when index_factor is null then 'not_indexed'
        else 'cpi_rmr462'
    end                                                 as index_basis,

    -- Why a quarter has no factor, in words. Empty when it has one.
    case
        when index_factor is not null            then null
        when months_observed <> 3                then 'quarter incomplete: '
                                                      || months_observed || ' of 3 months published'
        when base_months_observed <> 12          then 'base year incomplete: '
                                                      || base_months_observed || ' of 12 months published'
        else 'base index is not positive'
    end                                                 as not_indexed_reason

from factors
