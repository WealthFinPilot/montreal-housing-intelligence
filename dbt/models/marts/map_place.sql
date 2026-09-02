/*
    The shapes the page 1 map draws: 36 of them, each belonging to exactly one
    APCIQ sector, each drawn on land.

    32 are administrative entities taken whole -- 17 boroughs and 15 linked
    cities. 4 are the halves of the two boroughs APCIQ cuts in two.

    WHY THE GEOMETRY IS CUT BY THE TRACTS

    dim_geography already holds these entities, as the city publishes them, and
    the city's boundaries run to the middle of the river: 619.3 km2 against
    499.6 km2 of actual land. A map drawn from those polygons swallows the St.
    Lawrence, the Rivière des Prairies and part of Lac Saint-Louis -- 119.7 km2,
    a quarter of the island -- and the island stops being recognisable.
    Measured 2026-09-01, and it is why the map was rejected before it was built.

    So every polygon here is intersected with the union of the census tract
    polygons, which stop at the shoreline. Same basis as the 18 sector outlines
    built on 2026-08-31, and the two agree to 0.047 %.

    WHY 36 SHAPES AND NOT 18, AND WHAT IT MAY NOT CLAIM

    APCIQ publishes 18 prices. This table draws 36 shapes and lets each take
    the colour of the one sector it belongs to, so several shapes carry the
    same figure: the seven municipalities of sector 1 are one published number,
    not seven. That is a readability trade, asked for on 2026-09-01 so a reader
    can find the place they live in. It is NOT a new grain. Nothing joins a
    fact to place_key, and nothing ever should.

    WHY THE TWO SPLIT BOROUGHS ARE CUT RATHER THAN GREYED OUT

    Verdun and Côte-des-Neiges–Notre-Dame-de-Grâce each sit in two sectors. The
    first version of this model left them without a sector, and the map lost a
    whole published sector: L'Île-des-Sœurs is sector 10 and is not an
    administrative entity, so nothing on the island drew it. It was seen on
    the first render, by eye.

    They are cut instead, using the neighbourhood polygons the seed
    apciq_sector_neighbourhood already declares -- the same declaration J3.4
    uses to place census tracts. No second source of truth.

    A majority rule was measured and refused before this: 61/39 on Verdun and
    59/40 on CDN–NDG by land area, near-halves, where the majority rule that
    draws census tracts displaces 0.024 % of the population.

    THE CUT CANNOT LEAVE A GAP, BY CONSTRUCTION

    The declared neighbourhoods do not quite cover their borough -- 0.032 km2
    left over on Verdun, 0.049 on CDN–NDG, the same two-shoreline disagreement
    J3.4 measured at 0.44 %. Taking one intersection per sector would leave
    those slivers unpainted, which is exactly the gap J3.1 warned about.

    So only the SMALLER piece is an intersection. The larger one is the borough
    MINUS the smaller one, so the two pave the borough exactly whatever the
    edges do. The leftover lands in the larger piece, which is a boundary rule
    and is stated rather than hidden: at most 0.33 % of one borough.

    WHAT IS ASSUMED RATHER THAN OBSERVED

    APCIQ publishes no line between its sector 7 (NDG) and its sector 8
    (Côte-des-Neiges) -- only the two names. The city's 2014 sociological
    boundary stands in for it, over 40 tracts and 170 583 people.
    boundary_is_assumed carries that on the two shapes concerned. Verdun does
    not run that risk: the line between its two sectors is water.
*/

with land as (

    select st_union(geometry) as geometry
    from {{ ref('dim_geography') }}
    where geography_type = 'census_tract'

),

places as (

    /*
        19 boroughs + 15 linked cities = 34 entities, before any cutting.

        Ville de Montréal is excluded deliberately: it is the union of its own
        19 boroughs, so drawing it would lay a second shape over a third of the
        island and that surface would be painted twice.
    */
    select
        geo.geography_key,
        geo.geography_type,
        geo.geography_code,
        geo.name,
        st_intersection(geo.geometry, land.geometry) as geometry
    from {{ ref('dim_geography') }} as geo
    cross join land
    where geo.geography_type = 'borough'
       or (
            geo.geography_type = 'municipality'
            and geo.geography_key <> 'municipality:66023'
          )

),

sector_of_place as (

    /*
        How many sectors each place reaches, from the bridge's 36 rows.
        count(distinct) because the bridge carries one row per (place, sector)
        pair, and the question is how many SECTORS, not how many rows.
    */
    select
        admin_geography_key,
        count(distinct apciq_geography_key) as sector_count
    from {{ ref('bridge_apciq_sector_geography') }}
    group by admin_geography_key

),

knife as (

    /*
        One polygon per (split borough, sector), from the seed that already
        declares which neighbourhood of which file belongs to which sector.

        The join is on neighbourhood_code, never on the name: the seed
        addresses its polygons by their published id, exactly as J3.4 does.
    */
    select
        'borough:' || seed.borough_codemamh   as admin_geography_key,
        seed.apciq_sector_number,
        st_union(hoods.geometry)              as geometry
    from {{ ref('apciq_sector_neighbourhood') }} as seed
    join {{ ref('stg_montreal_open_data__neighbourhoods') }} as hoods
      on hoods.source_dataset = seed.source_dataset
     and hoods.neighbourhood_code = seed.neighbourhood_code
    group by 1, 2

),

knife_sized as (

    /*
        Rank the pieces of each split borough by size. Rank 1 is the largest,
        and it is the one rebuilt by difference so it absorbs the leftover.
    */
    select
        knife.admin_geography_key,
        knife.apciq_sector_number,
        knife.geometry,
        row_number() over (
            partition by knife.admin_geography_key
            order by st_area(st_intersection(places.geometry, knife.geometry)::geography) desc
        ) as size_rank
    from knife
    join places
      on places.geography_key = knife.admin_geography_key

),

cut_pieces as (

    select
        places.geography_key                                   as admin_geography_key,
        places.geography_type,
        places.geography_code || '-' || knife_sized.apciq_sector_number as place_code,
        places.name,
        knife_sized.apciq_sector_number,
        case
            -- The largest piece: everything the other pieces do not take.
            when knife_sized.size_rank = 1
            then st_difference(places.geometry, others.geometry)
            else st_intersection(places.geometry, knife_sized.geometry)
        end                                                    as geometry,
        true                                                   as is_cut_from_a_larger_place
    from places
    join sector_of_place
      on sector_of_place.admin_geography_key = places.geography_key
     and sector_of_place.sector_count > 1
    join knife_sized
      on knife_sized.admin_geography_key = places.geography_key
    left join lateral (
        select st_union(other.geometry) as geometry
        from knife_sized as other
        where other.admin_geography_key = knife_sized.admin_geography_key
          and other.apciq_sector_number <> knife_sized.apciq_sector_number
    ) as others on true

),

whole_pieces as (

    select
        places.geography_key                                   as admin_geography_key,
        places.geography_type,
        places.geography_code                                  as place_code,
        places.name,
        cast(null as integer)                                  as apciq_sector_number,
        places.geometry,
        false                                                  as is_cut_from_a_larger_place
    from places
    join sector_of_place
      on sector_of_place.admin_geography_key = places.geography_key
     and sector_of_place.sector_count = 1

),

all_pieces as (

    select * from whole_pieces
    union all
    select * from cut_pieces

),

with_sector as (

    /*
        A whole place takes the single sector the bridge gives it; a cut piece
        matches on its own sector number. Either way the sector key and name
        come from the bridge, so a sector renamed upstream cannot be silently
        lost here.
    */
    select
        all_pieces.admin_geography_key,
        all_pieces.geography_type,
        all_pieces.place_code,
        all_pieces.name,
        all_pieces.geometry,
        all_pieces.is_cut_from_a_larger_place,
        bridge.apciq_geography_key,
        bridge.apciq_sector_number,
        bridge.apciq_sector_name
    from all_pieces
    join {{ ref('bridge_apciq_sector_geography') }} as bridge
      on bridge.admin_geography_key = all_pieces.admin_geography_key
     and (
            all_pieces.apciq_sector_number is null
         or bridge.apciq_sector_number = all_pieces.apciq_sector_number
         )

)

select
    admin_geography_key || case
        when is_cut_from_a_larger_place
        then ':sector-' || apciq_sector_number
        else ''
    end                                                          as place_key,
    admin_geography_key,
    place_code,
    case
        when is_cut_from_a_larger_place
        then name || ' (' || apciq_sector_name || ')'
        else name
    end                                                          as place_name,
    geography_type                                               as place_type,

    apciq_geography_key,
    apciq_sector_number,
    apciq_sector_name,
    is_cut_from_a_larger_place,

    /*
        True only where APCIQ publishes no boundary and the city's 2014
        sociological line stands in for it -- sectors 7 and 8. Verdun is cut on
        water, which is not an assumption.
    */
    is_cut_from_a_larger_place and apciq_sector_number in (7, 8) as boundary_is_assumed,

    geometry,
    round((st_area(geometry::geography) / 1000000.0)::numeric, 3) as area_km2,
    'land_only'                                                  as area_basis
from with_sector
