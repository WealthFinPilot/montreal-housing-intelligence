/*
    Every geographic entity this project can attach a figure to, in one table.

    Four levels live here, and they do NOT form a single clean tree:

        island        1 row    the whole agglomeration
        municipality 16 rows   15 linked cities + Ville de Montréal
        borough      19 rows   subdivisions of Ville de Montréal only
        apciq_sector 18 rows   how APCIQ cuts the island, which is different

    The first three nest properly: a borough is inside a municipality is inside
    the island. The fourth does not, which is the whole reason this project
    needs a bridge table beside this one.

    WHERE THE APCIQ SECTOR OUTLINES COME FROM

    Not from a file APCIQ publishes: there is none. They are the union of
    the census tract polygons of each sector, taken through
    bridge_census_tract_apciq_sector. One source file, so no two shorelines
    to reconcile.

    That is NOT the method settled in J3.1, which was to cut the two split
    boroughs with a neighbourhood file as a knife (ST_Intersection /
    ST_Difference across three files). J3.4 made that method unnecessary by
    resolving every tract to a sector, and a union of one file beats a cut
    across three: a cut inherits every disagreement between the files it
    cuts, and the tract polygons already disagree with the city's
    boundaries by up to 6.6 % of a tract.

    THE PROOF THAT NOTHING IS LOST OR DOUBLE-COUNTED

    An equality, not a tolerance. Measured 2026-08-31:

        sum of the 18 sector areas   499.627 km2
        area of their union          499.627 km2
        area of the 541 tracts       499.627 km2

    A drawing that dropped or duplicated a tract would not produce those
    three identical numbers. It is the geometric counterpart of the
    population reconciliation of J3.4, and a test holds it.

    TWO THINGS THIS GEOMETRY IS NOT

    It is not APCIQ's own line. Where APCIQ splits a borough it publishes
    two names and no boundary, so the tracts on each side were settled in
    J3.4 against a city neighbourhood file -- a DERIVED assumption, carried
    on every bridge row by assignment_method.

    And it does not tile in the topological sense. The union is exact in
    AREA, but the source polygons do not all touch: sector 3 comes out as
    two halves 13.3 m apart with nothing between them. At that size nothing
    is visible on any map this project draws, but it is measured, so it is
    stated rather than rounded up to "it tiles".
*/

with boundaries as (

    select * from {{ ref('stg_montreal_open_data__administrative_boundaries') }}

),

sectors as (

    select distinct
        apciq_sector_number,
        apciq_sector_name
    from {{ ref('apciq_sector_composition') }}

),

island as (

    select
        'island:mtl'                              as geography_key,
        'island'                                  as geography_type,
        'mtl'                                     as geography_code,
        'Île de Montréal (agglomeration)'         as name,
        cast(null as text)                        as parent_geography_key,
        st_union(geometry)                        as geometry,
        round(sum(area_km2), 3)                   as area_km2,
        cast(null as text)                        as admin_place_name
    from boundaries

),

municipalities as (

    -- A linked city is a municipality in its own right, so it passes straight
    -- through.
    select
        'municipality:' || codemamh               as geography_key,
        'municipality'                            as geography_type,
        codemamh                                  as geography_code,
        name,
        'island:mtl'                              as parent_geography_key,
        geometry,
        area_km2,
        cast(null as text)                        as admin_place_name
    from boundaries
    where geography_type = 'linked_city'

    union all

    -- Ville de Montréal is not a feature in the source file: it exists only as
    -- the sum of its 19 boroughs, so it is assembled here. 66023 is its MAMH
    -- code, read off the assessment roll, not chosen.
    select
        'municipality:66023'                      as geography_key,
        'municipality'                            as geography_type,
        '66023'                                   as geography_code,
        'Montréal'                                as name,
        'island:mtl'                              as parent_geography_key,
        st_union(geometry)                        as geometry,
        round(sum(area_km2), 3)                   as area_km2,
        cast(null as text)                        as admin_place_name
    from boundaries
    where geography_type = 'borough'

),

boroughs as (

    select
        'borough:' || codemamh                    as geography_key,
        'borough'                                 as geography_type,
        codemamh                                  as geography_code,
        name,
        'municipality:66023'                      as parent_geography_key,
        geometry,
        area_km2,
        cast(null as text)                        as admin_place_name
    from boundaries
    where geography_type = 'borough'

),

sector_geometry as (

    /*
        The outline of each APCIQ sector, assembled from the census tracts
        it DRAWS.

        is_drawn_in_this_sector, not the row simply existing: one tract has
        residents in two sectors and would otherwise be painted in both,
        which is an overlap rather than a shared shape. The bridge header
        explains what that rule costs -- 476 residents counted in one
        sector and drawn in another.

        Area in km2 through ::geography, never through EPSG:3347: a
        conformal conic preserves angles, not areas, and overstates this
        island by 3.3 % while returning a perfectly plausible number
        (docs/geography.md section 6).
    */
    select
        bridge.apciq_sector_number,
        st_union(tracts.geometry)                 as geometry,
        round(
            (st_area(st_union(tracts.geometry)::geography) / 1000000.0)::numeric,
            3
        )                                         as area_km2
    from {{ ref('bridge_census_tract_apciq_sector') }} as bridge
    join {{ ref('stg_statcan__census_tracts') }} as tracts
      on tracts.ct_uid = bridge.ct_uid
    where bridge.is_drawn_in_this_sector
    group by bridge.apciq_sector_number

),

apciq_sectors as (

    select
        'apciq_sector:' || sectors.apciq_sector_number    as geography_key,
        'apciq_sector'                                    as geography_type,
        cast(sectors.apciq_sector_number as text)         as geography_code,
        sectors.apciq_sector_name                         as name,

        /*
            Parented to the island, not to a municipality, and that is not
            laziness. Sector 1 spans seven municipalities; sector 8 spans one
            linked city and half a borough. The only entity that contains every
            sector is the island itself.
        */
        'island:mtl'                                      as parent_geography_key,

        sector_geometry.geometry,
        sector_geometry.area_km2,
        cast(null as text)                        as admin_place_name
    from sectors
    /*
        An inner join would hide a sector that lost its tracts by removing
        the row entirely, and 18 rows would silently become 17. Left join,
        so the row survives with a NULL geometry and the test that counts
        geometries fails loudly.
    */
    left join sector_geometry
      on sector_geometry.apciq_sector_number = sectors.apciq_sector_number

),

census_tracts as (

    /*
        The 541 census tracts of the Island, parented to their municipality.

        WHY NOT TO THE BOROUGH, WHICH WOULD BE FINER

        Because no published source says which borough a tract is in. A tract
        nests inside a municipality -- measured, zero exceptions, and guarded
        by a test -- but boroughs are a municipal creation and Statistics
        Canada does not carry them. Ville de Montréal therefore holds 485
        tracts directly, which looks coarse and is honest. Attaching them to
        boroughs and to APCIQ sectors is a spatial problem, and it is J3.4.

        This is the level at which household income exists, so it is the level
        fact_affordability will need in J4.
    */

    select
        'census_tract:' || tracts.ct_uid          as geography_key,
        'census_tract'                            as geography_type,
        tracts.ct_uid                             as geography_code,
        'CT ' || tracts.ct_name                   as name,
        'municipality:' || tracts.municipality_code
                                                  as parent_geography_key,
        tracts.geometry,
        tracts.area_km2,

        /*
            THE ONLY LEVEL THAT CARRIES THIS COLUMN, AND WHY IT IS HERE RATHER
            THAN LEFT TO A MEASURE

            'CT 0250.00' names nothing a reader recognises, so the page 2 map
            has to say where a tract is. The APCIQ sector cannot: sector 9 is
            called "Centre" and holds Westmount, and sector 1 gathers seven
            municipalities.

            Attached to the dimension rather than read through a measure
            because the map groups by this very table: the column then sits in
            the same row context as the shape and needs no relationship to
            propagate. Reading it from the fact table instead is what produced
            a tooltip naming the same borough on all 541 shapes -- a
            many-to-one relationship does not carry a filter back up.

            A LEFT join: an inner one would drop a tract that lost its
            placement and turn 541 rows into 540 without a word. The singular
            test assert_every_tract_is_named_by_one_place fails on a NULL
            instead.
        */
        places.admin_name                         as admin_place_name
    from {{ ref('stg_statcan__census_tracts') }} as tracts
    left join {{ ref('bridge_census_tract_admin_place') }} as places
           on places.ct_uid = tracts.ct_uid

),

administrative as (

    select * from island
    union all
    select * from municipalities
    union all
    select * from boroughs

)

/*
    WHY area_km2 CARRIES A SECOND COLUMN SAYING WHAT IT MEASURES

    The families of rows below do not mean the same thing by "area", and
    summing them together would produce a number with no referent.

    The city's administrative boundaries run out into the water -- Verdun is
    22.30 km² officially against 9.85 km² for its three neighbourhoods, because
    the borough reaches the middle of the river. The island measures 619 km²
    that way.

    The census tract polygons are cartographic boundaries, clipped to the
    shoreline. The same island measures 499 km² that way, which is its land
    area, and the two figures are both correct about different questions.

    APCIQ sectors sit with the tracts, not with the administrative rows,
    because they are BUILT from tract polygons: the 18 of them measure the
    same 499 km² of land. A sector and a borough therefore cannot be
    compared on area without reading this column first -- which is exactly
    what it is for.

    Rather than pick one and leave the reader to discover the discrepancy in a
    dashboard, every row states which it is.
*/

select
    *,
    'boundary_including_water'                    as area_basis
from administrative

union all

select
    *,
    'land_only'                                   as area_basis
from apciq_sectors

union all

select
    *,
    'land_only'                                   as area_basis
from census_tracts
