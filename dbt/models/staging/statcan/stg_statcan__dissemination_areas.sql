{{
    config(
        materialized = 'view'
    )
}}

/*
    The 3 228 dissemination areas of the Island, one row each, with the point
    Statistics Canada publishes to stand for them.

    Built by rolling the 13 844 dissemination blocks up to their area, exactly
    as stg_statcan__census_tracts rolls them up to their tract. The difference
    is what this grain carries and the tract grain destroys: a POINT, and the
    population attached to it.

    WHY THIS MODEL EXISTS AT ALL

    Because an APCIQ sector is not a Statistics Canada geography and never will
    be, so no attribute file will ever state which sector a tract is in. It has
    to be established, and the only sound way to establish it is the rule this
    project settled on 2026-08-24: membership comes from a published code, and
    where no code exists, from a representative point -- never from a polygon
    edge. This model is the supply of points.

    WHY A POINT AND NOT THE POLYGON IT STANDS IN

    Measured on 2026-08-24: 18 of the 541 tract polygons spill outside the
    city's administrative boundaries, by up to 6.6 % of their own area, because
    Statistics Canada and Ville de Montréal did not draw the same shoreline.
    Over the same geography, all 3 228 representative points fall cleanly
    inside, each in exactly one of the 34 entities, none in two. 3 219 of them
    carry population; the 9 that do not are counted here all the same, because
    an area with no residents still has to belong somewhere.

    An edge is where two organisations disagree. A point is not.

    WHAT THIS MODEL CANNOT DO, AND SAYS SO HERE

    A representative point commits its whole area to one side of any line. Where
    an area genuinely straddles a borough boundary, that is an error bounded by
    the area's own population -- and it is detectable, because Statistics Canada
    also publishes each area's LAND AREA. An area cannot fit in a space smaller
    than itself, and the singular test
    assert_representative_point_fits_where_it_landed enforces exactly that.

    On the Island the check flags one populated area out of 3 228, declared in
    the seed statcan_misplaced_representative_point with its measurement, and
    one unpopulated area, which carries no weight and changes nothing.
*/

with blocks as (

    select *
    from {{ source('statcan', 'statcan_geographic_attribute') }}
    where da_uid <> ''

),

aggregated as (

    select
        da_uid,

        /*
            Every coarser geography this area belongs to. max() is legitimate
            only because these are constant across the blocks of an area -- a
            dissemination area nests inside its tract and its municipality by
            construction, which is what Statistics Canada builds them to do.
        */
        max(ct_uid)                 as ct_uid,
        max(ct_dguid)               as ct_dguid,
        max(csd_uid)                as csd_uid,
        max(substr(csd_uid, 3))     as municipality_code,
        max(cd_uid)                 as cd_uid,

        count(*)                    as block_count,
        count(distinct ct_uid)      as census_tract_count,

        sum(nullif(trim(population_2021), '')::int)            as population_2021,
        sum(nullif(trim(total_dwellings_2021), '')::int)       as dwellings_2021,

        /*
            The area's own land area, summed from its blocks. This is the column
            that turns the representative point from an assumption into
            something falsifiable: an area of 0.0427 km² cannot sit inside a
            0.0076 km² sliver, whatever its point says.
        */
        round(sum(nullif(trim(land_area_km2), '')::numeric), 4) as land_area_km2,

        /*
            The representative point, published once per area and repeated on
            every block of it. Taken as latitude and longitude rather than as
            the Lambert pair beside it: both are published, they agree to 5 cm,
            and 4326 is the system every other geometry in this project lives
            in. Mixing systems is the trap that already cost this repository a
            day (docs/geography.md section 6).
        */
        max(nullif(trim(da_latitude), ''))::float8   as representative_latitude,
        max(nullif(trim(da_longitude), ''))::float8  as representative_longitude,

        min(first_seen_at)          as first_seen_at,
        max(updated_at)             as updated_at

    from blocks
    group by da_uid

)

select
    *,
    st_setsrid(
        st_makepoint(representative_longitude, representative_latitude),
        4326
    ) as representative_point
from aggregated
