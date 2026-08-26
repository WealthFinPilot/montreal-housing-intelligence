/*
    The three declared profiles still name three real combinations of the
    census file, and each still covers the island.

    dim_household_profile is typed by hand rather than derived, which is what
    makes the relationship test downstream worth anything -- and also what makes
    it fragile: a single character out of place in a label, an en dash that
    became a hyphen, a wording changed in a future census, and the left join in
    fact_affordability returns nothing while every structural test stays green.
    141 462 rows of null income, and only this test would say why.

    Checked in both directions:

      1. each declared pair must exist in the source, and must cover the same
         541 tracts as every other combination does -- the census file is
         perfectly rectangular, 77 rows per tract, so anything less means the
         labels do not match;
      2. each pair must still have at least 500 tracts with a PUBLISHED income.
         Measured on 2026-08-26 all three sit at 530 of 541. The threshold sits
         in the gap: the next best profiles after these three are at 529, 525
         and 524, and the ones that collapse are at 250 and below. A profile
         drifting under 500 has stopped being one of the well-covered ones and
         the choice of the three must be revisited, which is the behaviour
         wanted -- not a number quietly degrading behind a green build.
*/

with declared as (

    select
        household_profile_code,
        household_size_label,
        household_type_label
    from {{ ref('dim_household_profile') }}

),

island_tracts as (

    select distinct ct_uid
    from {{ ref('bridge_census_tract_apciq_sector') }}

),

measured as (

    select
        declared.household_profile_code,
        count(si.ct_uid)                                                as tracts_present,
        count(*) filter (
            where si.median_total_income_2020_status = 'published'
        )                                                               as tracts_published
    from declared
    left join {{ ref('stg_statcan__household_income') }} as si
           on si.household_size = declared.household_size_label
          and si.household_type = declared.household_type_label
          and si.census_year    = 2021
    left join island_tracts on island_tracts.ct_uid = si.ct_uid
    where island_tracts.ct_uid is not null or si.ct_uid is null
    group by 1

)

select
    measured.household_profile_code,
    measured.tracts_present,
    measured.tracts_published,
    case
        when measured.tracts_present <> (select count(*) from island_tracts)
            then 'label does not match the census file, or coverage changed'
        when measured.tracts_published < 500
            then 'this profile is no longer well covered; revisit the three'
    end as fault
from measured
where measured.tracts_present <> (select count(*) from island_tracts)
   or measured.tracts_published < 500
