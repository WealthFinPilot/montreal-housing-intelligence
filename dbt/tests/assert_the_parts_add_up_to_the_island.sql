/*
    The levels of dim_geography must be consistent with each other.

    Two assertions, and neither needs a figure from outside the project --
    which is the point. A test written against "the island is about 500 km²"
    would be a test against my memory. These compare the model to itself:

        the 16 municipalities        must cover exactly the island
        the 19 boroughs              must cover exactly Ville de Montréal

    Measured on 2026-08-23: 619.320 km² for the island and for the 16
    municipalities, 433.0 km² for the boroughs. These are boundary areas, which
    include the water each entity extends over -- not land area.

    A one-hundredth of a km² tolerance absorbs the rounding applied per entity;
    anything larger means a shape is counted twice or not at all.

    THE UNIT GUARD

    The third check looks pointless and is not. ST_Area on a geometry in
    EPSG:4326 returns square degrees -- roughly 0.06 for this island -- and the
    number looks like an area, prints like an area, and is meaningless. Dropping
    the ::geography cast in the staging model is a one-character mistake that no
    other test here would catch.

    A returned row is a failure.
*/

with levels as (

    select
        sum(area_km2) filter (where geography_type = 'island')       as island,
        sum(area_km2) filter (where geography_type = 'municipality') as municipalities,
        sum(area_km2) filter (where geography_type = 'borough')      as boroughs,
        max(area_km2) filter (where geography_key = 'municipality:66023')
                                                                     as ville_de_montreal
    from {{ ref('dim_geography') }}

),

checks as (

    select 'municipalities do not cover the island' as failure,
           island as expected, municipalities as actual
    from levels
    where abs(island - municipalities) > 0.01

    union all

    select 'boroughs do not cover Ville de Montréal',
           ville_de_montreal, boroughs
    from levels
    where abs(ville_de_montreal - boroughs) > 0.01

    union all

    select 'island area is not in km² -- check the ::geography cast in staging',
           null, island
    from levels
    where island < 100 or island > 2000

)

select * from checks
