/*
    Which APCIQ sector each census tract belongs to, and in what proportion.

    This is the join the whole project was missing. Household income exists at
    census tract; price exists at APCIQ sector; nothing published relates the
    two. This table relates them, and states how sure it is about each row.

    541 tracts, 542 rows: exactly one tract is genuinely shared between two
    sectors, and it appears twice rather than being rounded to one.

    HOW A TRACT REACHES A SECTOR, IN ONE SENTENCE

    Each dissemination area is placed by the point Statistics Canada publishes
    for it, that point falls in one borough or linked city, and the bridge
    bridge_apciq_sector_geography says which sector that entity belongs to --
    except for the two entities APCIQ cuts in half, where a second point-in-
    polygon against a neighbourhood file finishes the job.

    WHY NO POLYGON IS CUT ANYWHERE IN HERE

    Because the plan to cut them turned out to be unnecessary, and that is the
    result of session J3.4 rather than a shortcut taken inside it. The method
    settled in J3.1 was to rebuild the eighteen sector polygons with
    ST_Intersection and ST_Difference, then attach tracts to them. Measured on
    2026-08-24, before any of it was written:

        3 228 / 3 228   representative points fall in exactly one of the 34
                        administrative entities -- none outside, none in two
          532 / 534     populated tracts fall entirely inside one entity
           62 / 62      tracts of the two split boroughs resolve entirely
                        through the neighbourhood files, none straddling
                        a sector line

    Cutting polygons would have produced the same assignment for 540 tracts and
    a worse one for the rest, because a cut inherits every disagreement between
    the files it cuts. 18 of the 541 tract polygons already spill outside the
    city's boundaries by up to 6.6 % of their own area, and one of the two
    genuinely shared tracts picks up a 0.00 % sliver of a third borough that
    exists only because two organisations drew the same shoreline differently.
    A point has no edge, so it collects none of that.

    WHAT REMAINS AN ASSUMPTION, AND IT IS NOT A SMALL ONE

    APCIQ never publishes where the line between its sector 7 (NDG) and its
    sector 8 (Côte-des-Neiges) runs. There is no such line in any APCIQ
    document -- only the two names, on page 6 of the Baromètre. What this model
    uses in its place is Ville de Montréal's 2014 sociological neighbourhood
    boundary, which is a community-planning line drawn by a different body for
    a different purpose.

    That substitution covers 40 tracts and 170 583 people. It is a DERIVED
    assumption, not an observation, and assignment_method says so on every row
    it touches, so nothing downstream can present it as measured.

    Verdun does not carry the same risk: the line between Ile-des-Soeurs and the
    rest of the borough is water, so any reasonable delineation puts the same
    tracts on the same side.
*/

with areas as (

    select * from {{ ref('stg_statcan__dissemination_areas') }}

),

boundaries as (

    select * from {{ ref('stg_montreal_open_data__administrative_boundaries') }}

),

located as (

    /*
        The point decides. ST_Covers rather than ST_Contains: a point sitting
        exactly on a shared border is inside both under Covers and inside
        neither under Contains, and this project has already been caught by
        that difference (docs/geography.md section 6).
    */
    select
        areas.da_uid,
        areas.ct_uid,
        areas.population_2021,
        areas.land_area_km2,
        areas.representative_point,
        boundaries.codemamh
    from areas
    join boundaries
      on st_covers(boundaries.geometry, areas.representative_point)

),

declared_misplacement as (

    /*
        The one dissemination area whose point is known to have landed on the
        wrong side, with the measurement that proves it rather than an opinion.

        This is a declaration, not an exception list. The singular test
        assert_representative_point_fits_where_it_landed fails in BOTH
        directions: on an area that no longer fits and nobody declared, and on a
        declaration that no longer corresponds to anything. The second direction
        is the important one -- a derogation nobody re-examines is how a
        workaround becomes permanent.
    */
    select * from {{ ref('statcan_misplaced_representative_point') }}

),

corrected as (

    select
        located.da_uid,
        located.ct_uid,
        located.population_2021,
        located.land_area_km2,
        located.representative_point,

        /*
            Only a declaration that says 'reassign' moves anything. The other
            declared area straddles a boundary just as genuinely, but holds no
            residents, so moving it would change no number while erasing a true
            geographic fact. Both are declared; the resolution says which is
            which, and why is written in the seed's own finding column.
        */
        case
            when declared.resolution = 'reassign' then declared.tract_mostly_in_codemamh
            else located.codemamh
        end                                                     as codemamh,
        coalesce(declared.resolution = 'reassign', false)        as point_was_corrected
    from located
    left join declared_misplacement as declared
           on declared.da_uid = located.da_uid
          and declared.point_falls_in_codemamh = located.codemamh

),

sector_links as (

    select * from {{ ref('bridge_apciq_sector_geography') }}

),

entity_sector_count as (

    -- 32 of the 34 entities belong to exactly one sector; 2 are cut in half.
    select
        codemamh,
        count(*)                    as sector_count,
        min(apciq_sector_number)    as only_sector_number
    from sector_links
    group by codemamh

),

resolved_by_code as (

    /*
        The easy 32. The entity's code determines the sector outright, so no
        geometry is consulted beyond the point that placed the area.
    */
    select
        corrected.da_uid,
        corrected.ct_uid,
        corrected.population_2021,
        corrected.codemamh,
        corrected.point_was_corrected,
        entity_sector_count.only_sector_number       as apciq_sector_number,
        'borough_code'                               as assignment_method,
        cast(null as text)                           as neighbourhood_name
    from corrected
    join entity_sector_count using (codemamh)
    where entity_sector_count.sector_count = 1

),

neighbourhoods as (

    select * from {{ ref('stg_montreal_open_data__neighbourhoods') }}

),

neighbourhood_sector as (

    select * from {{ ref('apciq_sector_neighbourhood') }}

),

resolved_by_neighbourhood as (

    /*
        The two split entities. A second point-in-polygon, against the ONE file
        that can cut this particular borough.

        The join carries borough_codemamh, which is what stops the wrong file
        from answering: both neighbourhood files cover the whole city, so a
        point in Côte-des-Neiges also sits inside a housing-reference polygon.
        Only the seed rows for this borough are eligible, and each names its own
        file.
    */
    select
        corrected.da_uid,
        corrected.ct_uid,
        corrected.population_2021,
        corrected.codemamh,
        corrected.point_was_corrected,
        neighbourhood_sector.apciq_sector_number,
        'neighbourhood_polygon'                      as assignment_method,
        neighbourhoods.neighbourhood_name
    from corrected
    join entity_sector_count using (codemamh)
    join neighbourhood_sector
      on neighbourhood_sector.borough_codemamh = corrected.codemamh
    join neighbourhoods
      on neighbourhoods.source_dataset     = neighbourhood_sector.source_dataset
     and neighbourhoods.neighbourhood_code = neighbourhood_sector.neighbourhood_code
     and st_covers(neighbourhoods.geometry, corrected.representative_point)
    where entity_sector_count.sector_count > 1

),

assigned as (

    select * from resolved_by_code
    union all
    select * from resolved_by_neighbourhood

),

per_tract_sector as (

    select
        ct_uid,
        apciq_sector_number,
        sum(population_2021)                                    as population_2021,
        count(*)                                                as dissemination_area_count,
        bool_or(point_was_corrected)                            as includes_corrected_point,
        max(assignment_method)                                  as assignment_method,
        string_agg(distinct neighbourhood_name, ' + '
                   order by neighbourhood_name)                 as neighbourhood_names
    from assigned
    group by ct_uid, apciq_sector_number

),

weighted as (

    select
        *,
        sum(population_2021)              over (partition by ct_uid) as tract_population_2021,
        sum(dissemination_area_count)     over (partition by ct_uid) as tract_area_count,
        count(*)                          over (partition by ct_uid) as sectors_touched,
        count(*) filter (where population_2021 > 0)
                                          over (partition by ct_uid) as sectors_with_residents
    from per_tract_sector

),

bridged as (

select
    'census_tract:' || ct_uid                       as census_tract_geography_key,
    ct_uid,
    'apciq_sector:' || apciq_sector_number          as apciq_geography_key,
    apciq_sector_number,

    /*
        How much of the tract this row accounts for.

        Population, because population is what a household income describes. A
        tract shared between two sectors sends its income to both, in the
        proportion of the people who live on each side -- never split evenly,
        and never rounded to whichever side is bigger.

        The 7 tracts with no residents at all have no population to weight, so
        they fall back to counting dissemination areas. Each of them holds
        exactly one, so each gets a single row at 1.0. weight_basis says which
        rule applied rather than leaving a reader to work it out, exactly as
        area_basis does in dim_geography.
    */
    case
        when tract_population_2021 > 0
            then round(population_2021::numeric / tract_population_2021, 6)
        else round(dissemination_area_count::numeric / tract_area_count, 6)
    end                                             as population_weight,

    case
        when tract_population_2021 > 0 then 'population'
        else 'dissemination_area_count'
    end                                             as weight_basis,

    population_2021                                 as population_in_sector,
    tract_population_2021                           as tract_population,
    dissemination_area_count,

    /*
        'borough_code'          the entity's published code determined the
                                sector on its own -- an observation
        'neighbourhood_polygon' a second point-in-polygon was needed, against a
                                neighbourhood boundary that stands in for a line
                                APCIQ does not publish -- a DERIVED assumption
    */
    assignment_method,
    neighbourhood_names,

    /*
        True on both rows of the one tract whose RESIDENTS are split between two
        sectors. A consumer that joins on this table without noticing will get
        two rows; that is the same deliberate behaviour as
        bridge_apciq_sector_geography.

        Counted on rows that carry population, not on rows that merely exist.
        One tract reaches into a second sector across land where nobody lives:
        it keeps its zero-weight row, because the reach is real and a later
        census could put people there -- but calling it shared would invent an
        ambiguity that no household actually experiences.
    */
    sectors_with_residents > 1                      as tract_is_shared,
    sectors_touched                                 as sectors_touched,

    -- True where a declared misplacement moved this row's area off the side its
    -- point had landed on. One tract carries it.
    includes_corrected_point

from weighted

)

/*
    WHY A SECOND RULE EXISTS HERE, FOR DRAWING ONLY

    Everything above shares a tract between sectors by POPULATION, because
    population is what a household income describes. A surface cannot be
    shared that way. A map colours whole polygons: a tract weighted 92.9 %
    / 7.1 % would have to be drawn in both sectors, and drawing it twice is
    an overlap -- 1.833 km2 of double-counted land across two pairs of
    sectors, measured on 2026-08-31.

    So one extra column says which single sector DRAWS each tract: the one
    where the majority of its residents live. Exactly one row per tract
    carries it, 541 of the 543.

    The rule needs no tie-break, and that was measured rather than assumed:
    no tract has two rows of equal weight. If one ever appears, the sector
    number decides, so the drawing stays reproducible.

    WHAT IT COSTS, AND WHY THE COLUMN EXISTS RATHER THAN THE RULE BEING
    APPLIED SILENTLY IN dim_geography

    On one tract, the drawing and the figures stop agreeing:

        4620511.02   476 residents COUNTED in sector 5, DRAWN in sector 2
        4620421.05   a zero-weight row in sector 6, drawn in sector 5

    476 people is 0.024 % of the island, on 1 tract out of 541 -- small, and
    not nothing. Anyone comparing a map to a table has to be able to find
    that difference, so it is a column that can be selected, counted and
    tested, exactly like assignment_method carries the CDN/NDG substitution.

    Cutting the shared polygon instead is what J3.4 examined and rejected,
    and nothing here reopens it: a cut inherits every disagreement between
    the files it cuts, and this one would be cut along a line APCIQ has
    never published.
*/
select
    *,
    row_number() over (
        partition by ct_uid
        order by population_weight desc, apciq_sector_number
    ) = 1                                           as is_drawn_in_this_sector

from bridged
