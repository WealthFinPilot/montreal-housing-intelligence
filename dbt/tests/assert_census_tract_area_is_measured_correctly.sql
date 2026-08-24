/*
    The area this project measures must agree with the area the source states.

    THE MISTAKE THIS EXISTS TO CATCH

    Statistics Canada ships these polygons in EPSG:3347, NAD83 / Statistics
    Canada Lambert. It is a Lambert CONFORMAL conic, so it preserves angles and
    not areas, and Montréal sits well south of both its standard parallels.
    Measuring there returns square metres -- a plausible unit, a plausible
    magnitude, and 3.3 % too many. Measured on 2026-08-24 over all 541 tracts:

        ST_Area in EPSG:3347                514.69 km²   +3.29 %
        ST_Area on ::geography              499.63 km²   +0.27 %
        ST_Area in EPSG:32188 (MTM 8)       499.53 km²   +0.25 %
        published LANDAREA                  498.29 km²

    This is a nastier version of the square-degrees trap already guarded
    elsewhere. That one produces 0.06 and is obviously wrong; this one produces
    a number a reviewer would accept.

    THE TOLERANCE, AND WHY IT IS NOT ZERO

    A tract polygon may hold a little water, and the published figure is a LAND
    area, so a small positive gap is expected. Two per cent on the island total
    passes the correct measurement comfortably and fails the projected one just
    as comfortably -- the two are an order of magnitude apart.

    Per tract the gap is allowed to be much larger, because a single waterfront
    tract can be mostly river; only tracts whose polygon is smaller than the
    land area it is supposed to contain are reported individually, since that
    can only mean a geometry problem.

    A returned row is a failure.
*/

with totals as (

    select
        sum(area_km2)                 as measured_km2,
        sum(published_land_area_km2)  as published_km2
    from {{ ref('stg_statcan__census_tracts') }}

),

failures as (

    select
        'island area disagrees with the published land area by more than 2 % '
        || '-- check that area is measured on ::geography, not in EPSG:3347'
                                                        as failure,
        cast(null as text)                              as ct_uid,
        'measured ' || measured_km2 || ' km², published ' || published_km2
                                                        as detail
    from totals
    where abs(measured_km2 - published_km2) / nullif(published_km2, 0) > 0.02

    union all

    select
        'a tract polygon is smaller than the land area it should contain',
        ct_uid,
        'measured ' || area_km2 || ' km², published ' || published_land_area_km2
    from {{ ref('stg_statcan__census_tracts') }}
    where published_land_area_km2 > 0
      and area_km2 < published_land_area_km2 * 0.98

)

select * from failures
