/*
    The five neighbourhood codes the seed maps to APCIQ sectors must still name
    the places they named when the mapping was written.

    The seed apciq_sector_neighbourhood addresses polygons by the code their
    file publishes -- id 4 and id 5 in the sociological file, no_qr 64, 65 and
    66 in the housing-reference one -- because a code is what this project joins
    on and a name is not. That is the right key, and it has one failure mode:
    a code is a position in someone else's file, and the file can be reissued
    with the positions moved.

    If that happened, nothing would break. Côte-des-Neiges would simply become
    whatever polygon now holds id 4, and 136 935 residents would be credited to
    APCIQ sector 8 on the strength of a number. The build would pass, the
    weights would sum to 1.0, and the map would look fine.

    So the seed carries the name beside the code -- not to join on, but to be
    checked against. This test compares them, and a rename or a renumber stops
    the build and names the row.

    It also fails if a seeded code matches nothing at all, which is what a
    dropped polygon looks like.

    A returned row is a failure.
*/

with seeded as (

    select * from {{ ref('apciq_sector_neighbourhood') }}

),

published as (

    select * from {{ ref('stg_montreal_open_data__neighbourhoods') }}

)

select
    seeded.source_dataset,
    seeded.neighbourhood_code,
    seeded.apciq_sector_number,
    seeded.neighbourhood_name_source        as name_the_seed_expects,
    published.neighbourhood_name            as name_the_file_now_carries,
    case
        when published.neighbourhood_code is null
            then 'this code matches no polygon in that file any more'
        else 'this code now names a different place'
    end                                     as problem
from seeded
left join published
       on published.source_dataset     = seeded.source_dataset
      and published.neighbourhood_code = seeded.neighbourhood_code
where published.neighbourhood_code is null
   or published.neighbourhood_name is distinct from seeded.neighbourhood_name_source
