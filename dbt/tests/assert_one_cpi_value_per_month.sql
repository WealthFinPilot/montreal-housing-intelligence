/*
    One index value per series per month, and one factor per quarter.

    A dbt test passes when its query returns NO rows, so this looks for what
    must not exist and passing means finding nothing.

    The primary key on raw.statcan_cpi_observation already makes a duplicate
    month impossible at the source. What it cannot guard is the layer above:
    the quarterly model groups months into quarters, and a grouping mistake
    there -- a join that fans out, a base year cross-joined wrongly -- would
    produce two factors for one quarter with no complaint from the database.

    Both grains are asserted here because they are the same assertion at two
    resolutions, and splitting them into two files would hide that.
*/

with monthly_duplicates as (

    select
        vector_id::text                 as grain_key,
        ref_month::text                 as grain_period,
        count(*)                        as row_count,
        'monthly'                       as grain
    from {{ ref('stg_statcan__consumer_price_index') }}
    group by vector_id, ref_month
    having count(*) > 1

),

quarterly_duplicates as (

    select
        'quarterly_factor'              as grain_key,
        ref_year || ' Q' || ref_quarter as grain_period,
        count(*)                        as row_count,
        'quarterly'                     as grain
    from {{ ref('int_statcan__cpi_quarterly_index') }}
    group by ref_year, ref_quarter
    having count(*) > 1

)

select * from monthly_duplicates
union all
select * from quarterly_duplicates
