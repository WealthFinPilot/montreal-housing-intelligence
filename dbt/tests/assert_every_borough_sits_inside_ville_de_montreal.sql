/*
    A topological check, not an arithmetic one.

    dim_geography claims every borough has municipality:66023 as its parent.
    That claim is currently made by a CASE statement in staging -- it is true
    because the model says so. This test makes the geometry agree: each borough
    polygon must actually sit inside the Ville de Montréal polygon.

    ST_Covers rather than ST_Within or ST_Contains: Ville de Montréal is built
    as the union of these very boroughs, so every borough shares its entire
    outer edge with the union. ST_Contains excludes shapes that touch the
    boundary from the inside, which every one of them does -- it would fail all
    19. ST_Covers is the version that allows boundary contact, and it is the
    right predicate whenever the container was assembled from the contained.

    That distinction is the kind of thing that turns a spatial model into a
    week of confusion, so it is written down rather than remembered.

    A returned row is a failure.
*/

with ville_de_montreal as (

    select geometry
    from {{ ref('dim_geography') }}
    where geography_key = 'municipality:66023'

),

boroughs as (

    select geography_key, name, geometry
    from {{ ref('dim_geography') }}
    where geography_type = 'borough'

)

select
    boroughs.geography_key,
    boroughs.name
from boroughs
cross join ville_de_montreal
where not st_covers(ville_de_montreal.geometry, boroughs.geometry)
