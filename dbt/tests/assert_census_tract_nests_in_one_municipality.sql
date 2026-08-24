/*
    A census tract must sit inside exactly one municipality.

    This is the measurement that removed a spatial join from this project,
    turned into a permanent guard. On 2026-08-24 all 13 844 Island blocks were
    grouped by tract: none of the 541 tracts touched a second municipality, and
    none straddled the edge of the Island.

    WHY THE ZERO WAS NOT TAKEN AT FACE VALUE

    A clean zero is what a broken test looks like. The same code was run over
    the whole country, where it found 69 tracts that DO cross a census
    subdivision boundary and 12 that cross a census division. The test can see
    the phenomenon; it simply does not occur here.

    WHAT IT PROTECTS

    stg_statcan__census_tracts aggregates every tract-level attribute with
    max(), which is only meaningful while those attributes are constant across
    the tract's blocks. If Statistics Canada ever redraws one across a
    municipal boundary, this fails and names the tract, instead of the model
    quietly keeping whichever municipality sorted highest and attaching a
    tract's income to the wrong place.

    A returned row is a failure.
*/

select
    ct_uid,
    csd_name,
    municipality_count,
    block_count
from {{ ref('stg_statcan__census_tracts') }}
where municipality_count <> 1
