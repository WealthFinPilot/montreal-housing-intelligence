/*
    The diffusion carries the right price, and the profile join reads the right
    income.

    This is the test that would have caught the J3.5 failure had it happened
    here. fact_affordability performs two lookups and nothing else of substance:
    it fetches a price by (quarter, sector, category) and an income by
    (tract, household size, household type). Both can be wired to the wrong
    thing -- the sector next door, the average price instead of the median, the
    couple profile reading the one-person row -- and NONE of it changes the row
    count, the uniqueness of the key, the relationships, or the statuses. The
    table would be 141 462 rows of confident nonsense.

    So both sides are compared back to their own source, row by row, on the
    value AND on the status.

    is distinct from, not <>, because 430 of the 1 653 sector-quarter-category
    combinations have no published price and eleven tracts have no published
    income: a NULL on both sides must count as a match, not as an unknown.
*/

with price_disagrees as (

    select
        fa.affordability_key,
        'price' as side,
        fa.median_price::text        as in_the_fact,
        fm.median_price::text        as in_the_source
    from {{ ref('fact_affordability') }} as fa
    join {{ ref('fact_market') }} as fm
      on fm.quarter_start_date  = fa.quarter_start_date
     and fm.geography_key       = fa.apciq_geography_key
     and fm.property_type_code  = fa.property_type_code
    where fa.median_price is distinct from fm.median_price
       or fa.median_price_value_status is distinct from fm.median_price_value_status

),

income_disagrees as (

    select
        fa.affordability_key,
        'income' as side,
        fa.household_income::text                as in_the_fact,
        si.median_total_income_2020::text        as in_the_source
    from {{ ref('fact_affordability') }} as fa
    join {{ ref('dim_household_profile') }} as dhp
      on dhp.household_profile_code = fa.household_profile_code
    join {{ ref('stg_statcan__household_income') }} as si
      on si.ct_uid         = fa.ct_uid
     and si.household_size = dhp.household_size_label
     and si.household_type = dhp.household_type_label
     and si.census_year    = 2021
    where fa.household_income is distinct from si.median_total_income_2020
       or fa.household_income_status is distinct from si.median_total_income_2020_status

)

select * from price_disagrees
union all
select * from income_disagrees
