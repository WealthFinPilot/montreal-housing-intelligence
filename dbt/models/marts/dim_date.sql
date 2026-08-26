/*
    One row per calendar day, from 2015-01-01 to the end of the current year.

    WHY A DAY GRAIN FOR A PROJECT WHOSE MARKET DATA IS QUARTERLY

    Because the Bank of Canada series are daily and weekly, and they start on
    2015-01-01 -- measured, not assumed. A quarterly date table would serve
    fact_market and force a second date table for the rate series, and two date
    tables in one Power BI model is how a report ends up with two slicers that
    disagree.

    Every fact in this project therefore joins to this one table: the market
    facts on quarter_start_date, the rate observations on their own date.

    WHY IT REACHES INTO THE FUTURE

    Power BI wants a contiguous date column with no gaps to accept a table as
    its date table -- that is what makes time intelligence work. Stopping at
    the last observed date would leave the current quarter half empty and would
    make the table shrink or grow depending on which fact was loaded last. It
    ends on 31 December of the current year, so the table is complete for any
    period the data can reach, and it extends on its own each January.

    Contiguity is not left to chance either: assert_dim_date_has_no_gap.sql
    checks that the row count equals the span in days.
*/

with bounds as (

    select
        -- The first Bank of Canada observation on record. A fact dated before
        -- this would have nowhere to join, and the relationship tests on the
        -- fact tables are what would say so.
        date '2015-01-01'                                          as first_day,
        (date_trunc('year', current_date)
            + interval '1 year' - interval '1 day')::date          as last_day

),

days as (

    select generate_series(first_day, last_day, interval '1 day')::date as date_key
    from bounds

)

select
    date_key,

    extract(year    from date_key)::int                            as calendar_year,
    extract(quarter from date_key)::int                            as calendar_quarter,
    extract(month   from date_key)::int                            as calendar_month,
    extract(day     from date_key)::int                            as day_of_month,

    /*
        The two columns the market facts join on and group by. quarter_label is
        spelled the way the APCIQ editions are labelled elsewhere in this
        project ("2026 Q2"), so a chart axis and an edition reference read the
        same.
    */
    date_trunc('quarter', date_key)::date                          as quarter_start_date,
    (date_trunc('quarter', date_key)
        + interval '3 months' - interval '1 day')::date            as quarter_end_date,
    extract(year from date_key)::int
        || ' Q' || extract(quarter from date_key)::int             as quarter_label,

    date_trunc('month', date_key)::date                            as month_start_date,
    (date_trunc('month', date_key)
        + interval '1 month' - interval '1 day')::date             as month_end_date,

    -- ISO day of week: 1 = Monday, 7 = Sunday. The Bank of Canada publishes
    -- nothing on a weekend, which is a legitimate absence rather than a hole.
    extract(isodow from date_key)::int                             as iso_day_of_week,
    extract(isodow from date_key)::int >= 6                        as is_weekend,

    date_key = (date_trunc('quarter', date_key)
        + interval '3 months' - interval '1 day')::date            as is_quarter_end

from days
