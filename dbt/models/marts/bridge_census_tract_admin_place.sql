/*
    One row per census tract: the administrative entity -- borough or linked
    city -- that a reader would call the tract's neighbourhood.

    WHY THIS TABLE EXISTS, AND WHY THE EXISTING BRIDGES COULD NOT ANSWER

    Asked on 2026-09-02 while building the page 2 map: its tooltip named an
    APCIQ sector, and an APCIQ sector is not a place people know. Sector 9 is
    called "Centre" and holds Hampstead, Mont-Royal, Outremont and Westmount;
    sector 1 gathers seven municipalities.

    Neither bridge already in the model can answer it:

      bridge_census_tract_apciq_sector   tract -> APCIQ sector
      bridge_apciq_sector_geography      place -> APCIQ sector
      map_place                          drawn place -> APCIQ sector

    Composing the first two runs tract -> sector -> places and returns EVERY
    place of that sector: up to seven names for one tract. The direction that
    was missing is tract -> place, and it is in no table. It is built here from
    the same dissemination-area placement the sector bridge uses, so the two
    can never disagree about where an area sits.

    THE RULE, AND WHAT IT COSTS

    A tract is named after the entity where the MAJORITY OF ITS RESIDENTS live.
    This is a third rule in the project, and the three are deliberately not the
    same because they answer different questions:

      population weights      bridge_census_tract_apciq_sector -- an income
                              describes people, so a shared tract sends its
                              income to both sectors in proportion
      drawing majority        is_drawn_in_this_sector -- a polygon cannot be
                              painted twice
      naming majority         here -- a tooltip has room for one name

    The cost is a column, not a footnote: population_named_elsewhere counts the
    residents of a tract who live in a different entity from the one naming
    them. Measured at build time, the island total is small enough to state
    exactly and too large to call zero, and the singular test bounds it.

    WHAT THIS TABLE IS NOT

    It is not a geography a figure may be aggregated by. APCIQ publishes at the
    sector, and 26 of the 34 places show a territory larger than themselves
    (docs/geography.md section 4). This column names a tract; it never groups
    a price.
*/

with placed as (

    select * from {{ ref('int_geography__dissemination_area_place') }}

),

places as (

    /*
        The 34 entities with their key and their name, taken from the bridge
        that already derives them rather than re-deriving 'REM' || no_arr here.
        Two of its 36 rows are the halves of the two boroughs APCIQ cuts, and
        both halves carry the same place: distinct collapses them to 34.

        If a codemamh ever carried two names, this would return 35 rows, the
        join below would double a tract, and the unique test on ct_uid fails.
        That is the intended way to find out.
    */
    select distinct
        codemamh,
        admin_geography_key,
        admin_name,
        admin_geography_type
    from {{ ref('bridge_apciq_sector_geography') }}

),

per_tract_place as (

    select
        ct_uid,
        codemamh,
        sum(population_2021)    as population_in_place,
        count(*)                as dissemination_area_count
    from placed
    group by ct_uid, codemamh

),

ranked as (

    select
        *,
        sum(population_in_place)      over (partition by ct_uid) as tract_population,
        sum(dissemination_area_count) over (partition by ct_uid) as tract_area_count,
        count(*)                      over (partition by ct_uid) as places_touched,

        /*
            Population decides. The seven tracts with no residents at all have
            no population to rank, so they fall back to counting areas -- each
            holds exactly one, so each has a single candidate anyway.
            assignment_basis says which rule applied instead of leaving a
            reader to work it out, exactly as weight_basis does next door.

            codemamh breaks a tie last, so the naming is reproducible rather
            than dependent on scan order. No tie exists today; the test
            assert_every_tract_is_named_by_one_place would notice a duplicate
            if the ordering ever stopped being total.
        */
        row_number() over (
            partition by ct_uid
            order by population_in_place desc, dissemination_area_count desc, codemamh
        )                                                        as rk
    from per_tract_place

),

winner as (

    select * from ranked where rk = 1

),

runner_up as (

    -- The residents this naming sends to a neighbour. Zero on 538 of 541.
    select
        ct_uid,
        sum(population_in_place) as population_named_elsewhere
    from ranked
    where rk > 1
    group by ct_uid

)

select
    'census_tract:' || winner.ct_uid                 as census_tract_geography_key,
    winner.ct_uid,

    places.admin_geography_key,
    winner.codemamh,
    places.admin_name,
    places.admin_geography_type,

    winner.population_in_place,
    winner.tract_population,
    coalesce(runner_up.population_named_elsewhere, 0)
                                                    as population_named_elsewhere,
    winner.places_touched,

    -- True where the tract sits in more than one entity and a majority had to
    -- decide. A reader comparing this name to a map needs to find these.
    winner.places_touched > 1                       as name_is_a_majority_call,

    case
        when winner.tract_population > 0 then 'population'
        else 'dissemination_area_count'
    end                                             as assignment_basis

from winner
join places
  on places.codemamh = winner.codemamh
left join runner_up
  on runner_up.ct_uid = winner.ct_uid
