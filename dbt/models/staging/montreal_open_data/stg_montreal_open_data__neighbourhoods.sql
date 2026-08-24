{{
    config(
        materialized = 'view'
    )
}}

/*
    The neighbourhood polygons of Ville de Montréal, from two files, kept apart.

    123 rows: 32 sociological neighbourhoods and 91 housing-reference ones. They
    are NOT unioned, reconciled or deduplicated, and that is the point of this
    model rather than an omission.

    WHY TWO FILES SIT IN ONE TABLE WITHOUT BEING MERGED

    They describe the same city twice, at different dates, for different
    purposes, and their borders do not coincide -- 0.44 % apart on
    Côte-des-Neiges–Notre-Dame-de-Grâce, measured 2026-08-23. Combining them
    would produce slivers and overlaps that no measurement could later
    disentangle, which is exactly the failure docs/geography.md section 5
    describes for administrative polygons.

    So each file answers only the question it alone can answer:

        quartiers-sociologiques   splits Côte-des-Neiges from
                                  Notre-Dame-de-Grâce  ->  APCIQ sectors 8 and 7
        quartiers                 splits Ile-des-Soeurs from the rest of
                                  Verdun               ->  APCIQ sectors 10 and 4

    The seed apciq_sector_neighbourhood names which file is authoritative for
    which borough, so a point is never asked a question the wrong file would
    also answer.

    WHAT THIS MODEL IS NOT FOR

    It is not a geography anyone joins market figures to. Nothing in
    dim_geography carries a neighbourhood level, and nothing should until a
    published source keys figures on one. These polygons exist to be stood in,
    by a representative point, and for nothing else.
*/

with source_rows as (

    select * from {{ source('montreal_open_data', 'mtl_neighbourhood') }}

),

converted as (

    select
        source_dataset,
        neighbourhood_code,
        neighbourhood_name,

        /*
            Present only where the file published a borough CODE, never derived
            from a matching name. The sociological file publishes none, so all
            32 of its rows carry NULL here -- see migration 08 for why that NULL
            is the honest answer rather than a gap to be filled.
        */
        borough_code,
        borough_name_source,
        municipality_name_source,
        properties_json,

        /*
            ST_SetSRID is not decoration, for the same reason as the boundary
            model: ST_GeomFromGeoJSON returns SRID 0, and PostGIS refuses to
            compare a geometry in SRID 0 with one in 4326. Skipping it produces
            an error at best and an empty spatial result at worst.

            Both files declare CRS84, checked at ingestion before a row was
            written, so 4326 here is stated by the source and not assumed.
        */
        st_setsrid(st_geomfromgeojson(geometry_geojson), 4326) as geometry,
        source_crs,

        first_seen_at,
        updated_at

    from source_rows

),

measured as (

    select
        *,

        /*
            Cast to geography before measuring. ST_Area on a geometry in 4326
            returns square DEGREES -- a number near zero that looks like a bug
            in someone else's code, and the trap this project already documented
            twice. In metres on the ellipsoid, then to km².
        */
        round((st_area(geometry::geography) / 1000000.0)::numeric, 4) as area_km2

    from converted

)

select * from measured
