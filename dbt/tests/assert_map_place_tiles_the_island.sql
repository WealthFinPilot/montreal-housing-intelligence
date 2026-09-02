/*
    The 36 place outlines must cover the island exactly once, and every one of
    the 18 published sectors must appear on the map.

    THE SECTOR-COVERAGE CHECK IS HERE BECAUSE A HUMAN FOUND IT MISSING

    On 2026-09-01 the first version of this map drew 34 administrative
    entities. It tiled perfectly, every count held, all fifteen tests passed --
    and sector 10, L'Île-des-Sœurs, was nowhere on it: it is a published APCIQ
    sector and not an administrative entity, so it fell between the shapes.
    It was seen on the first render, by comparing with the older map.

    No area test could have caught that, because nothing was missing from the
    island: the surface was all there, wearing the wrong sector's colour or no
    colour at all. The check below counts SECTORS REACHED, which is a different
    question from how much land is drawn, and it is the one that was not asked.

    THE AREA CHECK IS AN EQUALITY. Measured 2026-09-01:

        sum of the 36 place areas    499.388 km²
        area of their union          499.390 km²

    The 0.01 km² allowance absorbs per-shape rounding to three decimals over
    36 rows, exactly as in the sector test.

    THE COMPARISON WITH THE TRACTS IS A BOUND, NOT AN EQUALITY

    The sector outlines ARE a union of tracts, so they equal the tracts exactly.
    These are administrative polygons CUT BY the tracts, and the two sources
    draw the shoreline differently: 18 tracts overrun the city's boundaries by
    up to 6.6 % of their own area, measured in J3.3. The cut loses that overrun
    -- 0.237 km², 0.047 % -- and always will.

    The 1 km² allowance is an order-of-magnitude guard, NOT a validation of the
    0.237. Unlike the sector test's 0.01 it does not sit in a measured gap:
    nothing bounds how far two agencies could disagree about a shoreline in a
    future edition. If it fires, the question is which source moved.

    A returned row is a failure.
*/

with places as (

    select
        place_key,
        place_name,
        place_code,
        admin_geography_key,
        apciq_geography_key,
        apciq_sector_number,
        is_cut_from_a_larger_place,
        boundary_is_assumed,
        geometry,
        area_km2
    from {{ ref('map_place') }}

),

tracts as (

    select st_union(geometry) as geometry
    from {{ ref('dim_geography') }}
    where geography_type = 'census_tract'

),

sectors as (

    select geography_key
    from {{ ref('dim_geography') }}
    where geography_type = 'apciq_sector'

),

totals as (

    select
        (select count(*) from places)                                    as place_rows,
        (select count(*) from places where geometry is null)             as without_geometry,
        (select count(*) from places
          where apciq_geography_key is null)                             as without_sector,
        (select count(*) from places where is_cut_from_a_larger_place)   as cut_pieces,
        (select count(*) from places where boundary_is_assumed)          as assumed_pieces,
        (select count(distinct apciq_geography_key) from places)         as sectors_drawn,
        (select count(*) from sectors)                                   as sectors_published,
        (select sum(area_km2) from places)                               as sum_of_areas,
        (select st_area(st_union(geometry)::geography) / 1000000.0
           from places)                                                  as union_area,
        (select st_area(geometry::geography) / 1000000.0 from tracts)    as tract_area

),

checks as (

    select
        'a place lost its geometry'                     as failure,
        0::numeric                                      as expected,
        without_geometry::numeric                       as actual
    from totals
    where without_geometry > 0

    union all

    select
        'there are no longer 36 shapes',
        36, place_rows
    from totals
    where place_rows <> 36

    union all

    /*
        THE CHECK THAT WAS MISSING. Every published sector must own at least
        one shape, or the map silently drops a whole published market -- which
        is what happened to L'Île-des-Sœurs on 2026-09-01.
    */
    select
        'a published APCIQ sector is drawn by no shape at all',
        sectors_published, sectors_drawn
    from totals
    where sectors_drawn <> sectors_published

    union all

    select
        'a shape carries no sector, so it would be drawn with no colour',
        0, without_sector
    from totals
    where without_sector > 0

    union all

    -- Verdun and CDN–NDG, two pieces each. A third split borough means APCIQ
    -- changed its geography, which is the day this must stop being silent.
    select
        'the number of shapes cut out of a larger place has changed',
        4, cut_pieces
    from totals
    where cut_pieces <> 4

    union all

    /*
        Only the CDN/NDG line is assumed -- APCIQ publishes no boundary there
        and the city's 2014 sociological line stands in for it. Verdun is cut
        on water. If this count grows, an assumption was silently extended.
    */
    select
        'the number of shapes on an assumed boundary has changed',
        2, assumed_pieces
    from totals
    where assumed_pieces <> 2

    union all

    /*
        THE CUT PIECES MUST RECOMPOSE THEIR OWN BOROUGH, AND THIS CHECK IS
        LOCAL BECAUSE THE ISLAND-WIDE ONE CANNOT SEE IT.

        Added 2026-09-01 after a positive control stayed silent. Both halves of
        a split borough were taken as intersections, which leaves the 0.03 to
        0.05 km² the neighbourhood file does not cover unpainted -- and the
        island total moved by 0.08 km², far under the 1 km² shoreline guard.
        A hole that small is a few pixels on screen and would never be noticed.

        Measured against the borough cut by the same shoreline, so the only
        thing under test is the cut itself. 1000 m² is three orders of
        magnitude below the gap the failing version produced.
    */
    select
        'the pieces of ' || cut.place_name || ' do not recompose it',
        round(cut.borough_m2::numeric, 0),
        round(cut.pieces_m2::numeric, 0)
    from (
        select
            min(p.place_name)                                       as place_name,
            st_area(st_union(p.geometry)::geography)                as pieces_m2,
            max(st_area(st_intersection(g.geometry, t.geometry)::geography)) as borough_m2
        from places p
        join {{ ref('dim_geography') }} g on g.geography_key = p.admin_geography_key
        cross join tracts t
        where p.is_cut_from_a_larger_place
        group by p.admin_geography_key
    ) as cut
    where abs(cut.pieces_m2 - cut.borough_m2) > 1000

    union all

    -- Land drawn twice, or drawn nowhere.
    select
        'the shapes do not add up to their own union',
        union_area, sum_of_areas
    from totals
    where abs(sum_of_areas - union_area) > 0.01

    union all

    -- The cut can only lose land, never gain it: an intersection is a subset.
    select
        'the shapes cover more land than the census tracts do',
        tract_area, union_area
    from totals
    where union_area > tract_area + 0.01

    union all

    select
        'the shapes have drifted too far from the tract shoreline',
        tract_area, union_area
    from totals
    where tract_area - union_area > 1.0

    union all

    -- Same unit guard as the sector test: ST_Area on a 4326 geometry returns
    -- square degrees, which look like an area and are not.
    select
        'place area is not in km² -- check the ::geography cast',
        null, union_area
    from totals
    where union_area < 100 or union_area > 2000

    union all

    /*
        Overlap, named rather than merely detected. 1 m² rather than 0 because
        PostGIS intersections of shared borders produce slivers of a few square
        millimetres from floating-point arithmetic.

        This is also what would catch a cut gone wrong: the two halves of a
        split borough are built as intersection and difference, so an error
        there shows up as the halves overlapping, not as missing area.
    */
    select
        'shapes ' || a.place_name || ' and ' || b.place_name || ' overlap',
        0,
        round((st_area(st_intersection(a.geometry, b.geometry)::geography))::numeric, 1)
    from places a
    join places b
      on a.place_key < b.place_key
     and st_intersects(a.geometry, b.geometry)
    where st_area(st_intersection(a.geometry, b.geometry)::geography) > 1

)

select * from checks
