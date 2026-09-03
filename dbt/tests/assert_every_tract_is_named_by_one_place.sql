/*
    Every census tract must be named after exactly one administrative entity,
    and dim_geography must carry that name on all 541 of them.

    WHAT THIS GUARDS THAT THE GENERIC TESTS DO NOT

    unique and not_null on the bridge prove the bridge is well formed. They
    say nothing about the LEFT JOIN in dim_geography, which is where a name
    actually reaches the map. An inner join dropping a tract would show up as
    540 rows and might pass unnoticed; a left join keeping the row with a NULL
    name paints a shape whose tooltip says nothing at all. Both are silent in
    Power BI -- a map with one uninformative shape still looks like a map.

    WHY THE POPULATION CEILING IS DELIBERATELY CRUDE

    The naming rule makes a tract carry a neighbour's name when its residents
    straddle a boundary: 476 people, 0.0237 % of the island, on 2 tracts of
    541 -- the same two tracts the drawing rule isolated on 2026-08-31.

    The 1 % ceiling below does NOT validate that 0.0237 %. It catches a change
    of ORDER OF MAGNITUDE: an upstream boundary file that starts cutting
    tracts, a placement that stops being corrected, a join that fans out. The
    measured value and the threshold are more than an order of magnitude
    apart, and the day they get close the failure is the right outcome.

    A returned row is a failure.
*/

with named as (

    select * from {{ ref('bridge_census_tract_admin_place') }}

),

placed as (

    /*
        The placement the bridge is built from, read again here so this test
        RECOMPUTES the majority instead of reading back the column the model
        wrote. A test that reads the model's own answer proves only that the
        column exists.
    */
    select * from {{ ref('int_geography__dissemination_area_place') }}

),

largest_place_of_each_tract as (

    select ct_uid, max(pop) as largest_population
    from (
        select ct_uid, codemamh, sum(population_2021) as pop
        from placed
        group by ct_uid, codemamh
    ) as per_place
    group by ct_uid

),

dimension as (

    select *
    from {{ ref('dim_geography') }}
    where geography_type = 'census_tract'

),

counted as (

    select
        /*
            count DISTINCT, and that was found by a positive control rather
            than by reading. A fan-out in the bridge doubles rows in the
            dimension too -- both counts move together and a plain count(*)
            on each side compares 603 with 603. The distinct count of tracts
            does not move, so the comparison sees the duplication.
        */
        (select count(distinct geography_code) from dimension)      as tracts_in_dimension,
        (select count(*) from named)                                as tracts_named,
        (select count(*) from dimension where admin_place_name is null)
                                                                    as tracts_without_a_name,
        (select sum(population_named_elsewhere) from named)          as residents_named_elsewhere,
        (select sum(tract_population) from named)                    as residents_total,
        (select count(*)
           from dimension
           join named on named.ct_uid = dimension.geography_code
          where dimension.admin_place_name is distinct from named.admin_name)
                                                                    as names_that_disagree,
        (select count(*)
           from named
           join largest_place_of_each_tract as largest using (ct_uid)
          where named.population_in_place < largest.largest_population)
                                                                    as names_that_are_not_a_majority,
        (select count(*) from (
            select distinct codemamh from placed
            except
            select codemamh from named
         ) as unreached)                                            as places_no_tract_names

),

checks as (

    select
        'the bridge and the dimension hold a different number of tracts' as failure,
        tracts_in_dimension::numeric                                     as expected,
        tracts_named::numeric                                            as actual
    from counted
    where tracts_named <> tracts_in_dimension

    union all

    -- The left join kept the row and lost the name. Invisible in a row count.
    select
        'a census tract carries no place name in dim_geography',
        0::numeric,
        tracts_without_a_name::numeric
    from counted
    where tracts_without_a_name > 0

    union all

    /*
        Two sources of the same name must not drift. dim_geography reads the
        bridge through a join today, so a disagreement means the join key
        stopped being the tract -- the kind of fault that returns plausible
        names for the wrong shapes.
    */
    select
        'dim_geography names a tract differently from the bridge',
        0::numeric,
        names_that_disagree::numeric
    from counted
    where names_that_disagree > 0

    union all

    /*
        THE CHECK THE FIRST VERSION OF THIS FILE DID NOT HAVE.

        Found by a positive control on 2026-09-02: reversing the rule to name
        each tract after its MINORITY entity left all 39 tests green. Tract
        4620421.05 came out named after a place holding 0 of its 2 339
        residents, and the island total moved only from 0.0237 % to 0.4256 %
        -- comfortably under the ceiling below, which is why the ceiling could
        not see it.

        A ceiling measures a MAGNITUDE. This measures the RULE, per tract, and
        it is the one that would notice an ordering silently losing its
        population term.
    */
    select
        'a tract is named after an entity that is not its largest',
        0::numeric,
        names_that_are_not_a_majority::numeric
    from counted
    where names_that_are_not_a_majority > 0

    union all

    /*
        THE QUESTION NOBODY ASKED ON 2026-09-01, WHEN THE PLACE MAP DREW ALL
        THE LAND AND STILL LOST SECTOR 10.

        Every check above asks whether every TRACT got a name. This asks the
        other direction: is every PLACE the name of at least one tract? A place
        no tract names is a place a reader can never find on the map, and no
        count of tracts, no null check and no area total can see it.

        Five places hang on a single tract -- L Ile-Dorval has 30 residents on
        one -- so the margin is thinner than the 541 makes it look.

        ⚠️ UNREACHABLE TODAY, AND WRITTEN ANYWAY. 539 of the 541 tracts touch
        exactly one place, so every place is named by construction and no
        positive control can make this fire on its own: any change big enough
        to orphan a place trips one of the checks above first. It becomes
        reachable the day a boundary file starts cutting tracts. Same standing
        as the sixth branch of Verdict -- written, not verified.
    */
    select
        'a place exists that no census tract is named after',
        0::numeric,
        places_no_tract_names::numeric
    from counted
    where places_no_tract_names > 0

    union all

    select
        'the naming rule now moves more than 1 % of the island''s residents',
        1::numeric,
        round(100.0 * residents_named_elsewhere / nullif(residents_total, 0), 4)
    from counted
    where residents_named_elsewhere > 0.01 * residents_total

)

select * from checks
