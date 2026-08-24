/*
    A dissemination area cannot sit in a space smaller than itself.

    This is the guard that makes the representative point falsifiable instead of
    merely convenient. The point places a whole area on one side of a line, and
    where the area actually straddles that line, the placement is wrong by up to
    the area's entire population. Nothing in the point itself reveals that.

    But Statistics Canada publishes each area's LAND AREA. So the claim "this
    area is inside that entity" can be checked against arithmetic: the area
    cannot be larger than the intersection of its own tract with that entity.

    THE TOLERANCE, AND WHY IT IS A RATIO RATHER THAN A DIFFERENCE

    Small overshoots are expected and mean nothing. Statistics Canada and Ville
    de Montréal do not draw the same shoreline: 18 of the 541 tract polygons
    spill outside the city's boundaries by up to 6.6 % of their own area, so an
    intersection computed across the two files is short by a sliver almost
    everywhere along the water.

    Measured over all 3 228 Island areas on 2026-08-24, the two populations are
    not close together:

        12 areas overshoot by a ratio of 1.000 to 1.016   -- shoreline noise
         2 areas overshoot by 2.87 and 5.62               -- genuinely elsewhere

    Three orders of magnitude separate them, so the threshold is not a knob to
    be tuned: anything from 1.05 to 2.8 selects the same two rows. 1.5 sits in
    the middle of that gap. Should a future file close it, this test starts
    failing and the threshold gets re-argued -- which is the correct outcome,
    not a nuisance.

    IT FAILS IN BOTH DIRECTIONS, AND THE SECOND ONE MATTERS MORE

      * an area that no longer fits and that nobody declared
      * a declaration that no longer corresponds to anything

    The second direction is why the seed is a declaration and not an exclusion
    list. A derogation nobody re-examines is exactly how a workaround becomes
    permanent -- the same argument as apciq_known_publisher_defect, and the same
    two-way test.

    A returned row is a failure.
*/

{% set size_ratio_threshold = 1.5 %}

with areas as (

    select * from {{ ref('stg_statcan__dissemination_areas') }}

),

boundaries as (

    select * from {{ ref('stg_montreal_open_data__administrative_boundaries') }}

),

tracts as (

    select ct_uid, geometry from {{ ref('stg_statcan__census_tracts') }}

),

declared as (

    select * from {{ ref('statcan_misplaced_representative_point') }}

),

located as (

    select
        areas.da_uid,
        areas.ct_uid,
        areas.population_2021,
        areas.land_area_km2,
        boundaries.codemamh
    from areas
    join boundaries
      on st_covers(boundaries.geometry, areas.representative_point)

),

room as (

    -- How much of this area's own tract lies inside the entity its point chose.
    select
        located.da_uid,
        located.ct_uid,
        located.codemamh,
        located.population_2021,
        located.land_area_km2,
        st_area(st_intersection(tracts.geometry, boundaries.geometry)::geography)
            / 1000000.0                                     as room_km2
    from located
    join tracts     on tracts.ct_uid = located.ct_uid
    join boundaries on boundaries.codemamh = located.codemamh

),

measured as (

    select
        *,
        case
            when room_km2 > 0 then land_area_km2 / room_km2::numeric
            else null
        end as size_ratio
    from room

),

does_not_fit as (

    select * from measured
    where size_ratio is null
       or size_ratio > {{ size_ratio_threshold }}

),

-- Direction 1: an area that does not fit and that nobody has declared.
undeclared as (

    select
        does_not_fit.da_uid,
        does_not_fit.ct_uid,
        does_not_fit.codemamh,
        round(does_not_fit.size_ratio, 3)   as size_ratio,
        'not declared anywhere'             as problem
    from does_not_fit
    left join declared using (da_uid)
    where declared.da_uid is null

),

-- Direction 2: a declaration that no longer describes anything.
stale_declaration as (

    select
        declared.da_uid,
        declared.ct_uid,
        declared.point_falls_in_codemamh    as codemamh,
        cast(null as numeric)               as size_ratio,
        'declared, but this area now fits where its point landed -- '
        'the derogation must be re-examined and removed'
                                            as problem
    from declared
    left join does_not_fit using (da_uid)
    where does_not_fit.da_uid is null

)

select * from undeclared
union all
select * from stale_declaration
