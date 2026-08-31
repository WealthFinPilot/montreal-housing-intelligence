{{
    config(
        materialized = 'view'
    )
}}

/*
    The Consumer Price Index for the Montréal census metropolitan area,
    All-items, one row per month.

    WHAT THIS SERIES IS FOR, AND WHAT IT IS NOT

    It exists to restate the 2020 census income in dollars of a later quarter.
    It is NOT a source of income, and it is not a price of housing. It is a
    general basket of consumer goods for a metropolitan area that is wider
    than the Island -- CMA 462 also holds Laval, Longueuil and both shores.

    Everything downstream of it is therefore a DERIVED figure carrying an
    assumption, and the assumption is nameable: that household incomes moved
    with consumer prices. That is false by a measured amount -- between -0.4 %
    and +1.3 % over 2021-2024, and +7.8 % on 2019, checked once against the
    Canadian Income Survey (11100190) and written down in docs/limitations.md.
    Bounded error, not unknown error.

    WHY THE BASE OF THE INDEX DOES NOT MATTER

    The published base is 2002=100. Nothing downstream reads the level: every
    use is one month divided by another month of the same series, so the base
    cancels. If Statistics Canada rebases the series tomorrow, not one figure
    in the marts moves.

    WHAT IS EXCLUDED, AND WHY THAT MAKES A TEST MEANINGFUL

    Rows with no value are dropped here, the same choice made for the Bank of
    Canada series in J2 and for the same reason: an empty cell means nothing
    was published that month, which is neither a zero nor an index of zero.
    After that filter, a value that will not convert can only mean the source
    changed format -- so not_null on index_value becomes an alarm with no
    false positives, rather than a count of ordinary gaps.

    Non-normal codes are KEPT, flagged rather than dropped. A preliminary
    figure is still the best available figure; a quarterly average that
    silently absorbed one would be worse than one that says so.
*/

with observations as (

    select *
    from {{ source('statcan', 'statcan_cpi_observation') }}

),

typed as (

    select
        vector_id,
        product_id,
        coordinate,
        geo_name,
        product_name,

        -- The first day of the month the observation describes. The source
        -- publishes monthly (frequency_code 6) and dates each point to the
        -- first of the month; kept as a date so the quarter can be derived
        -- arithmetically rather than by parsing a string.
        ref_period::date                                as ref_month,
        extract(year  from ref_period::date)::int       as ref_year,
        extract(month from ref_period::date)::int       as ref_month_number,
        extract(quarter from ref_period::date)::int     as ref_quarter,

        value::numeric                                  as index_value,

        status_code,
        symbol_code,
        uom_code,
        uom                                             as index_base,

        /*
            What the source asserts about this figure, in words rather than
            in codes. Read from the WDS code sets on 2026-08-31:

                status 0 normal
                status 1 not available for this reference period
                status 2 rounded to zero where a true zero is meaningful
                symbol 0 none, 1 preliminary, 3 revised

            Order matters: a preliminary figure that is also flagged
            unavailable is unavailable first.
        */
        case
            when status_code <> '0' then 'not_normal'
            when symbol_code = '1'  then 'preliminary'
            when symbol_code = '3'  then 'revised'
            when symbol_code = '0'  then 'final'
            else 'unknown_symbol'
        end                                             as index_status,

        release_time,
        source_url,
        first_seen_at,
        updated_at

    from observations
    -- See the header: an empty cell is not an index of zero.
    where value is not null
      and btrim(value) <> ''

)

select *
from typed
