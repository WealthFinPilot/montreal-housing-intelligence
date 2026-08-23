{{
    config(
        materialized = 'view'
    )
}}

/*
    The 34 administrative entities of the island of Montréal, typed.

    This is where GeoJSON text becomes a PostGIS geometry -- the same division
    of labour as the Bank of Canada model, where text becomes a number. The raw
    layer records what the city published; this layer decides what it means.

    WHY THE ISLAND IS 16 MUNICIPALITIES AND 19 BOROUGHS AT THE SAME TIME

    The file mixes two levels in one list, and the CODEMAMH column mixes two
    nomenclatures with them:

        Ville liée      -> a municipality in its own right.
                           codemamh is its 5-digit MAMH code (66112).
        Arrondissement  -> NOT a municipality. It is a subdivision of Ville de
                           Montréal, whose own MAMH code is 66023.
                           codemamh is a REMxx borough code.

    So the island is 15 linked cities + Ville de Montréal = 16 municipalities,
    of which exactly one is subdivided, into 19 boroughs.

    Both derived codes below are observations, not assumptions. The MAMH
    assessment roll extracted on 2026-08-21 carries municipality_code = 66023
    together with borough_code = REMxx on every Ville de Montréal unit, and
    municipality_code = 66xxx with an empty borough_code on every linked city
    unit. Verified against ingestion/mamh_roll on 2026-08-23.
*/

with source as (

    select *
    from {{ source('montreal_open_data', 'mtl_administrative_boundary') }}
    where source_dataset = 'limites-administratives-agglomeration'

),

typed as (

    select
        codemamh,

        /*
            English, stable values, because the rest of the model keys on them.
            The French labels stay available in entity_type_source: a reader
            comparing this table to the city's file must be able to see the
            original wording.
        */
        case entity_type
            when 'Arrondissement' then 'borough'
            when 'Ville liée'     then 'linked_city'
        end as geography_type,

        entity_type as entity_type_source,
        nom as name,
        abrev as abbreviation,

        /*
            Which municipality this entity belongs to. A linked city is its
            own; a borough belongs to Ville de Montréal.

            66023 is not a constant invented here -- it is the code the MAMH
            roll carries on all 437 192 Ville de Montréal units.
        */
        case entity_type
            when 'Ville liée'     then codemamh
            when 'Arrondissement' then '66023'
        end as municipality_code,

        -- NULL for a linked city, and that is the right answer rather than a
        -- gap: a linked city has no borough, which is exactly why the roll
        -- leaves borough_code empty on 15 % of its rows.
        case entity_type
            when 'Arrondissement' then codemamh
        end as borough_code,

        /*
            ST_SetSRID is not decoration. ST_GeomFromGeoJSON returns a geometry
            with SRID 0 -- "coordinates in no declared system" -- and PostGIS
            refuses to compare a geometry in SRID 0 with one in 4326. Skipping
            it makes every later spatial join raise, or worse, quietly compare
            nothing.

            4326 is safe to state here because the ingestion refuses to load a
            file that does not declare CRS84.
        */
        st_setsrid(st_geomfromgeojson(geometry_geojson), 4326) as geometry,

        source_crs,
        datemodif as source_modified_on,
        first_seen_at,
        updated_at

    from source

),

measured as (

    select
        *,

        /*
            Cast to geography before measuring: ST_Area on a geometry in 4326
            returns square DEGREES, a number with no physical meaning that
            still looks like an area. The geography type measures on the
            ellipsoid and returns square metres.

            Kept as a plausibility check rather than for analysis -- the island
            is about 500 km², so the 34 values must sum to roughly that.
        */
        round((st_area(geometry::geography) / 1000000.0)::numeric, 3) as area_km2

    from typed

)

select * from measured
