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

    WHY APCIQ SECTORS HAVE NO GEOMETRY HERE

    Two of the eighteen cut a borough in half:

        Côte-des-Neiges–Notre-Dame-de-Grâce  ->  sector 7 takes NDG,
                                                 sector 8 takes Côte-des-Neiges
        Verdun                               ->  sector 10 takes L'Île-des-Sœurs,
                                                 sector 4 takes the rest

    Their true outlines are reconstructible -- the city publishes both
    "Quartiers sociologiques" (which names Côte-des-Neiges and
    Notre-Dame-de-Grâce) and "Quartiers de référence en habitation" (which
    names Ile-des-Soeurs), both CC-BY, both checked on 2026-08-23. Assembling
    them and proving the result tiles the island without gaps or overlaps is a
    piece of work in its own right, and it has not been done.

    Until it is, geometry is NULL for these rows. A NULL that says "not
    established" is worth more than a polygon that looks authoritative and is
    approximate -- especially on a map, where nobody would ever question it.
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
        round(sum(area_km2), 3)                   as area_km2
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
        area_km2
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
        round(sum(area_km2), 3)                   as area_km2
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
        area_km2
    from boundaries
    where geography_type = 'borough'

),

apciq_sectors as (

    select
        'apciq_sector:' || apciq_sector_number    as geography_key,
        'apciq_sector'                            as geography_type,
        cast(apciq_sector_number as text)         as geography_code,
        apciq_sector_name                         as name,

        /*
            Parented to the island, not to a municipality, and that is not
            laziness. Sector 1 spans seven municipalities; sector 8 spans one
            linked city and half a borough. The only entity that contains every
            sector is the island itself.
        */
        'island:mtl'                              as parent_geography_key,

        cast(null as geometry)                    as geometry,
        cast(null as numeric)                     as area_km2
    from sectors

)

select * from island
union all
select * from municipalities
union all
select * from boroughs
union all
select * from apciq_sectors
