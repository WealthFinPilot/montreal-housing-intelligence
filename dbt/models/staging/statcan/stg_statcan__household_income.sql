{{
    config(
        materialized = 'view'
    )
}}

/*
    Household income by census tract, for the 541 tracts of the Island.

    One row per tract x household size x household type -- 41 657 rows, the
    grain the source publishes. The raw layer holds the whole metropolitan
    area; this model narrows it to the Island by joining the tract list, which
    itself comes from published municipal codes and not from a map.

    The grain is kept rather than reduced to the "Total x Total" line, because
    the breakdown is the analytically interesting part for this project. A
    first-time buyer is a household of a particular shape, and "what does a
    couple without children earn in this tract" is a different and better
    question than "what does the median household earn".

    THREE THINGS A CELL CAN SAY, AND WHY NONE OF THEM IS ZERO

    Every measure comes with a status:

        published        the number is the value
        suppressed       a real number exists and the Statistics Act forbids
                         printing it -- 11 of the 541 Island tracts, all with
                         populations between 0 and 30
        not_applicable   the question does not arise for this combination

    A suppressed income is not a low income, and an inapplicable one is not a
    missing one. Both are NULL in the value column and distinguishable in the
    status column. Nothing here is ever filled in by interpolation or by
    borrowing a neighbouring tract.

    WHAT THIS FIGURE IS, AND IS NOT

    A CENSUS figure, for income years 2020 and 2015, in 2020 constant dollars.
    It does not move with the market. Any ratio against an APCIQ price from
    2026 divides a 2026 price by a 2020 income, which is an assumption to be
    displayed, never an observation -- brief sections 8.2 and 22. The
    income_year column exists so a downstream model cannot forget it.
*/

with income as (

    select *
    from {{ source('statcan', 'statcan_income_statistic') }}

),

tracts as (

    select
        ct_uid,
        ct_dguid,
        municipality_code,
        csd_name
    from {{ ref('stg_statcan__census_tracts') }}

),

island_only as (

    /*
        An inner join, deliberately. The raw table also holds the metropolitan
        area total and the 463 tracts of Laval, Longueuil and both shores --
        CMA 462 is not the Island, and treating it as the project perimeter is
        the mistake docs/data-sources.md section 2.4 was written to prevent.
    */
    select
        tracts.ct_uid,
        tracts.municipality_code,
        tracts.csd_name,
        income.*
    from income
    join tracts on tracts.ct_dguid = income.dguid

),

typed as (

    select
        ct_uid,
        dguid,
        municipality_code,
        csd_name,
        geo_name,
        nullif(trim(ref_date), '')::int as census_year,

        household_size,
        household_type,

        -- Counts of households, at both censuses.
        {{ statcan_value('households_2021', 'households_2021_symbol') }}::int
            as households_2021,
        {{ statcan_status('households_2021_symbol') }}
            as households_2021_status,

        {{ statcan_value('households_2016', 'households_2016_symbol') }}::int
            as households_2016,
        {{ statcan_status('households_2016_symbol') }}
            as households_2016_status,

        -- Total income, before tax, in 2020 constant dollars.
        {{ statcan_value('median_total_income_2020', 'median_total_income_2020_symbol') }}
            as median_total_income_2020,
        {{ statcan_status('median_total_income_2020_symbol') }}
            as median_total_income_2020_status,

        {{ statcan_value('median_total_income_2015', 'median_total_income_2015_symbol') }}
            as median_total_income_2015,
        {{ statcan_status('median_total_income_2015_symbol') }}
            as median_total_income_2015_status,

        /*
            After-tax income. This is the one an affordability calculation
            should reach for when the question is "what can this household
            actually pay each month", and total income the one a lender's
            gross-debt-service rule reaches for. They are not interchangeable,
            and J4 must state which it used.
        */
        {{ statcan_value('median_aftertax_income_2020', 'median_aftertax_income_2020_symbol') }}
            as median_aftertax_income_2020,
        {{ statcan_status('median_aftertax_income_2020_symbol') }}
            as median_aftertax_income_2020_status,

        {{ statcan_value('median_aftertax_income_2015', 'median_aftertax_income_2015_symbol') }}
            as median_aftertax_income_2015,
        {{ statcan_status('median_aftertax_income_2015_symbol') }}
            as median_aftertax_income_2015_status,

        coordinate,
        first_seen_at,
        updated_at

    from island_only

)

select * from typed
