/*
    The 18 APCIQ sector outlines must cover the island exactly once.

    They are not published anywhere: they are the union of the census tract
    polygons each sector draws. A union is a cheap way to build a map and a
    silent way to get one wrong -- a tract attached to two sectors is painted
    twice, a tract attached to none leaves a hole, and both look like a normal
    map to anyone who has not counted.

    So the test is an EQUALITY, not a tolerance. Measured 2026-08-31:

        sum of the 18 sector areas   499.627 km²
        area of their union          499.627 km²
        area of the 541 tracts       499.627 km²

    Only a partition produces those three numbers at once. Dropping a tract
    lowers the first two, duplicating one raises the first alone.

    The 0.01 km² allowance absorbs the per-sector rounding to three decimals,
    exactly as in assert_the_parts_add_up_to_the_island. A tract of the island
    is never that small: the smallest measures several hectares.

    THE OVERLAP CHECK IS NOT REDUNDANT WITH THE AREA CHECK

    It looks it, and it is not. Two sectors could overlap on a strip while a
    third lost the same area, and the sum would still land. The pair check
    names the sectors, which is what makes a failure diagnosable rather than
    merely detectable.

    1 m² rather than 0: PostGIS intersections of shared borders produce
    slivers of a few square millimetres from floating-point arithmetic. The
    real overlap this rule removes is 1.833 km² -- six orders of magnitude
    away, so the threshold sits in a measured gap and is not a dial.

    A returned row is a failure.
*/

with sectors as (

    select geography_key, geography_code, geometry, area_km2
    from {{ ref('dim_geography') }}
    where geography_type = 'apciq_sector'

),

tracts as (

    select st_union(geometry) as geometry
    from {{ ref('dim_geography') }}
    where geography_type = 'census_tract'

),

totals as (

    select
        (select count(*) from sectors)                                   as sector_rows,
        (select count(*) from sectors where geometry is null)            as without_geometry,
        (select sum(area_km2) from sectors)                              as sum_of_areas,
        (select st_area(st_union(geometry)::geography) / 1000000.0
           from sectors)                                                 as union_area,
        (select st_area(geometry::geography) / 1000000.0 from tracts)    as tract_area

),

checks as (

    select
        'a sector lost its geometry'                    as failure,
        without_geometry::numeric                       as expected,
        0::numeric                                      as actual
    from totals
    where without_geometry > 0

    union all

    select
        'there are no longer 18 sectors',
        18, sector_rows
    from totals
    where sector_rows <> 18

    union all

    -- Tracts drawn twice, or drawn nowhere.
    select
        'the sectors do not add up to their own union',
        union_area, sum_of_areas
    from totals
    where abs(sum_of_areas - union_area) > 0.01

    union all

    -- The sectors are built from the tracts, so their union IS the tracts.
    -- A gap here means a tract reaches no sector at all.
    select
        'the sectors do not cover every census tract',
        tract_area, union_area
    from totals
    where abs(union_area - tract_area) > 0.01

    union all

    -- Same unit guard as assert_the_parts_add_up_to_the_island: ST_Area on a
    -- 4326 geometry returns square degrees, which look like an area and are not.
    select
        'sector area is not in km² -- check the ::geography cast',
        null, union_area
    from totals
    where union_area < 100 or union_area > 2000

    union all

    select
        'sectors ' || a.geography_code || ' and ' || b.geography_code || ' overlap',
        0,
        round((st_area(st_intersection(a.geometry, b.geometry)::geography))::numeric, 1)
    from sectors a
    join sectors b
      on a.geography_code::int < b.geography_code::int
     and st_intersects(a.geometry, b.geometry)
    where st_area(st_intersection(a.geometry, b.geometry)::geography) > 1

)

select * from checks
