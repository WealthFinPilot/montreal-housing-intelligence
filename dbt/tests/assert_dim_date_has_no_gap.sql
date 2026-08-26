/*
    dim_date is contiguous, and every fact date falls inside it.

    Contiguity is not cosmetic here. Power BI refuses to mark a table as its
    date table unless the date column is continuous, and time intelligence
    computed on a table with a missing day is wrong rather than absent. A
    generate_series cannot skip a day, so this test is really guarding against
    the range being changed by hand later.

    The second half is the more useful one: a fact row dated outside the range
    would join to nothing, and in an imported Power BI model it would simply
    vanish from every visual filtered by date. Rates start in 2015 and the
    market archive in 2018 -- the second because the twelve-month window of the
    2019 Q2 edition opens on 1 July 2018.
*/

with span as (

    select
        min(date_key)                              as first_day,
        max(date_key)                              as last_day,
        count(*)                                   as rows_present,
        count(distinct date_key)                   as days_distinct
    from {{ ref('dim_date') }}

),

gaps as (

    select
        'dim_date is not contiguous'               as direction,
        first_day::text                            as detail,
        rows_present                               as expected_or_found
    from span
    where rows_present <> (last_day - first_day) + 1
       or days_distinct <> rows_present

),

market_outside as (

    select
        'fact_market quarter falls outside dim_date' as direction,
        quarter_start_date::text                     as detail,
        count(*)::int                                as expected_or_found
    from {{ ref('fact_market') }}
    where quarter_start_date not in (select date_key from {{ ref('dim_date') }})
    group by 1, 2

),

trailing_outside as (

    select
        'fact_market_trailing_12m window falls outside dim_date' as direction,
        period_start_date::text                                  as detail,
        count(*)::int                                            as expected_or_found
    from {{ ref('fact_market_trailing_12m') }}
    where period_start_date not in (select date_key from {{ ref('dim_date') }})
       or period_end_date   not in (select date_key from {{ ref('dim_date') }})
    group by 1, 2

),

rates_outside as (

    select
        'a rate observation falls outside dim_date' as direction,
        min(observation_date)::text                 as detail,
        count(*)::int                               as expected_or_found
    from {{ ref('stg_bank_of_canada__interest_rates') }}
    where observation_date not in (select date_key from {{ ref('dim_date') }})
    having count(*) > 0

)

select * from gaps
union all
select * from market_outside
union all
select * from trailing_outside
union all
select * from rates_outside
