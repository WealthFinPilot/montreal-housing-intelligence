/*
    Every tract, every quarter, every category, every profile -- and nothing
    extra.

    The expected count is COMPUTED from the four upstream counts, never written
    as 141 462. A literal would go stale the day a quarter is added and would
    then have to be edited by hand, which is precisely how a row-count test
    stops being a test. Here, adding an edition makes both sides move together
    and the assertion still means something.

    The four factors, and what each one is:

        542   tract-sector pairs carrying population (the bridge of J3.4;
              541 tracts, one of which is genuinely split between two sectors)
         29   quarters, 2019 Q2 to 2026 Q2
          3   APCIQ property categories
          3   household profiles

    A row count alone proves very little -- J3.5 showed a mis-wired pivot
    keeping its count intact. It is the companion test on the values that does
    the real work. This one catches the other failure: a join that multiplies
    or drops rows.
*/

with expected as (

    select
        (select count(*)
         from {{ ref('bridge_census_tract_apciq_sector') }}
         where population_weight > 0)
      * (select count(distinct quarter_start_date) from {{ ref('fact_market') }})
      * (select count(*) from {{ ref('dim_property_type') }})
      * (select count(*) from {{ ref('dim_household_profile') }})
        as expected_rows

),

actual as (

    select
        count(*)                                    as actual_rows,
        count(distinct affordability_key)           as distinct_keys,
        count(distinct ct_uid)                      as distinct_tracts
    from {{ ref('fact_affordability') }}

)

select
    expected.expected_rows,
    actual.actual_rows,
    actual.distinct_keys,
    actual.distinct_tracts
from expected
cross join actual
where actual.actual_rows  <> expected.expected_rows
   or actual.distinct_keys <> expected.expected_rows
   -- The island has 541 census tracts. Losing one would still leave a tidy
   -- table; it would just quietly stop being the island.
   or actual.distinct_tracts <> (
        select count(*) from {{ ref('dim_geography') }}
        where geography_type = 'census_tract'
      )
