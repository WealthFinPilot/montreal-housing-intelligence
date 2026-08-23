/*
    The bridge must account for the whole island, exactly once, twice only
    where APCIQ really does split a borough.

    This is the test that makes the transcription of the Baromètre trustworthy.
    A sector composition typed in by hand can fail in three ways, and all three
    are silent: an entity left out (its market figures vanish), an entity
    listed twice (its figures are double counted), or a codemamh that matches
    nothing (a link that joins to no row). The arithmetic below catches all
    three at once.

    Expected: 34 entities, 36 links. The two extras are the two boroughs APCIQ
    cuts in half --

        REM34  Côte-des-Neiges–Notre-Dame-de-Grâce  -> sectors 7 and 8
        REM12  Verdun                               -> sectors 4 and 10

    The exceptions are named here on purpose rather than derived. Naming them
    means the day the city merges a borough, or APCIQ redraws a sector, this
    test fails and someone reads the source again -- which is what should
    happen. A test that discovered its own exceptions would simply agree with
    whatever it was given.

    A returned row is a failure.
*/

with expected as (

    select
        codemamh,
        name,
        case
            when codemamh in ('REM34', 'REM12') then 2
            else 1
        end as expected_links
    from {{ ref('stg_montreal_open_data__administrative_boundaries') }}

),

actual as (

    select
        codemamh,
        count(*) as actual_links
    from {{ ref('bridge_apciq_sector_geography') }}
    group by codemamh

)

select
    expected.codemamh,
    expected.name,
    expected.expected_links,
    coalesce(actual.actual_links, 0) as actual_links
from expected
left join actual
       on actual.codemamh = expected.codemamh
where coalesce(actual.actual_links, 0) <> expected.expected_links
