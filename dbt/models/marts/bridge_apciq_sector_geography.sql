/*
    Which administrative entities each APCIQ sector is made of.

    THIS TABLE IS A WARNING DEVICE, NOT A CONVENIENCE

    APCIQ publishes market statistics by sector. Everything else in this
    project -- the assessment roll, the census, the boundary file -- is
    organised by municipality and borough. The two carvings do not line up, and
    the temptation is to join them on whichever names look alike and move on.

    Doing that would invent precision. So the relationship is stored the way it
    actually is, many-to-many, with the quality of each link stated:

        coverage = 'full'   the sector contains this entity entirely
        coverage = 'part'   the sector contains only a piece of it

    The consequence is deliberate and should not be engineered away: joining
    market figures to boroughs through this table returns TWO rows for
    Côte-des-Neiges–Notre-Dame-de-Grâce and TWO for Verdun. Anyone who writes
    that join sees the ambiguity in the result instead of being reassured by a
    single wrong number.

    36 links for 34 entities: the two extras are exactly the two split
    boroughs. A test asserts that arithmetic, so a mistranscription of the
    source cannot pass unnoticed.

    SOURCE

    Transcribed from page 6, "Définition des secteurs", of
    202602-bar-mtl.pdf (APCIQ, Baromètre résidentiel, 2026 Q2), retrieved
    2026-08-23. The same page in 201902-bar-mtl.pdf and 202204-bar-mtl.pdf
    carries the same eighteen sectors in the same order, so the mapping is
    stable across the whole 2019Q2-2026Q2 history and needs no validity dates.

    Source: APCIQ, by the Centris system. Non-commercial use with attribution.

    OPEN QUESTION, TO SETTLE IN J3.2

    APCIQ describes sector 4 as "Le Sud-Ouest (Montréal), Verdun (Montréal)"
    while sector 10 is L'Île-des-Sœurs, which is part of Verdun. Either sector
    4 excludes the island, or the two overlap. The Baromètre reports a total
    for the Island of Montréal on page 8: if the eighteen sectors sum to it,
    there is no double count. That is an arithmetic check, and it needs the
    parser -- so it is recorded here rather than guessed at.
*/

with composition as (

    select * from {{ ref('apciq_sector_composition') }}

)

select
    'apciq_sector:' || apciq_sector_number as apciq_geography_key,
    apciq_sector_number,
    apciq_sector_name,

    -- Resolved against the boundary file rather than trusted from the seed:
    -- a codemamh that matches nothing must fail the relationship test.
    case
        when boundaries.geography_type = 'linked_city'
            then 'municipality:' || boundaries.codemamh
        when boundaries.geography_type = 'borough'
            then 'borough:' || boundaries.codemamh
    end as admin_geography_key,

    composition.codemamh,
    boundaries.name as admin_name,
    boundaries.geography_type as admin_geography_type,

    /*
        How much of that entity the sector takes. 'part' is the interesting
        value and there are exactly four rows carrying it: sectors 7 and 8
        splitting Côte-des-Neiges–Notre-Dame-de-Grâce, sectors 4 and 10
        splitting Verdun.
    */
    composition.coverage,

    -- What APCIQ itself calls this component, kept verbatim. A reader
    -- comparing this table to the PDF must be able to find the wording.
    composition.component_label_source

from composition
left join {{ ref('stg_montreal_open_data__administrative_boundaries') }} as boundaries
       on boundaries.codemamh = composition.codemamh
