{{
    config(
        materialized = 'view'
    )
}}

/*
    One row per dissemination area: which of the 34 administrative entities of
    the island it sits in, after the one declared misplacement is corrected.

    WHY THIS IS ITS OWN MODEL, AS OF 2026-09-02

    Every line below was lifted VERBATIM out of bridge_census_tract_apciq_sector,
    where it had been since J3.4. Nothing was changed on the way out -- the
    extraction is a move, not a rewrite, so the sector bridge must rebuild to
    exactly the same 543 rows.

    It moved because a second reader appeared. bridge_census_tract_admin_place
    needs the same placement to name the borough or linked city a census tract
    belongs to. Two point-in-polygon joins answering the same question would
    agree today and drift the day one of them is corrected -- which is the
    reasoning that keeps the Bank of Canada series labels in one place with a
    test to make a divergence loud.

    A view, and it stays one: 3 228 points against 34 polygons take 0.18 s
    (measured 2026-09-02), and a view can never hold a stale copy of staging.

    WHAT THIS MODEL DOES NOT DECIDE

    It places an AREA, not a tract. A census tract holding areas in two
    entities is not resolved here and must not be: the two consumers need
    different rules -- population weights for the sector bridge, a single
    majority name for the place bridge -- and each states its own.
*/

with areas as (

    select * from {{ ref('stg_statcan__dissemination_areas') }}

),

boundaries as (

    select * from {{ ref('stg_montreal_open_data__administrative_boundaries') }}

),

located as (

    /*
        The point decides. ST_Covers rather than ST_Contains: a point sitting
        exactly on a shared border is inside both under Covers and inside
        neither under Contains, and this project has already been caught by
        that difference (docs/geography.md section 6).
    */
    select
        areas.da_uid,
        areas.ct_uid,
        areas.population_2021,
        areas.land_area_km2,
        areas.representative_point,
        boundaries.codemamh
    from areas
    join boundaries
      on st_covers(boundaries.geometry, areas.representative_point)

),

declared_misplacement as (

    /*
        The one dissemination area whose point is known to have landed on the
        wrong side, with the measurement that proves it rather than an opinion.

        This is a declaration, not an exception list. The singular test
        assert_representative_point_fits_where_it_landed fails in BOTH
        directions: on an area that no longer fits and nobody declared, and on a
        declaration that no longer corresponds to anything. The second direction
        is the important one -- a derogation nobody re-examines is how a
        workaround becomes permanent.
    */
    select * from {{ ref('statcan_misplaced_representative_point') }}

)

select
    located.da_uid,
    located.ct_uid,
    located.population_2021,
    located.land_area_km2,
    located.representative_point,

    /*
        Only a declaration that says 'reassign' moves anything. The other
        declared area straddles a boundary just as genuinely, but holds no
        residents, so moving it would change no number while erasing a true
        geographic fact. Both are declared; the resolution says which is
        which, and why is written in the seed's own finding column.
    */
    case
        when declared.resolution = 'reassign' then declared.tract_mostly_in_codemamh
        else located.codemamh
    end                                                     as codemamh,
    coalesce(declared.resolution = 'reassign', false)        as point_was_corrected

from located
left join declared_misplacement as declared
       on declared.da_uid = located.da_uid
      and declared.point_falls_in_codemamh = located.codemamh
