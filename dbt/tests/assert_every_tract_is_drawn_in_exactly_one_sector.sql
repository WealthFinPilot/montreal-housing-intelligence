/*
    The drawing rule of bridge_census_tract_apciq_sector must place every
    census tract, and place it once.

    The bridge answers two different questions with two different rules, and
    this test guards the second one:

        population_weight        how much of a tract's INCOME each sector gets
        is_drawn_in_this_sector  which single sector PAINTS the tract

    A surface cannot be shared the way an income can, so exactly one row per
    tract carries the flag. Get it wrong in one direction and two sectors paint
    the same land; in the other and a hole opens where nobody notices, because
    a map with a missing tract still looks like a map.

        541 tracts, 543 bridge rows, 541 drawn -- measured 2026-08-31.

    WHY THE POPULATION CHECK IS HERE AND WHY IT IS A CRUDE ONE

    The rule makes the map and the figures disagree on one tract: 476 residents
    are COUNTED in sector 5 and DRAWN in sector 2. That is 0.024 % of the
    island, and it is the price of not cutting a polygon along a line APCIQ has
    never published.

    The 1 % ceiling below does not validate that 0.024 %. It catches a change
    of ORDER OF MAGNITUDE -- a bridge that starts sharing tracts widely, an
    upstream change that redistributes residents -- which would turn a footnote
    into a distortion. The measured value and the threshold are three orders of
    magnitude apart; if they ever get close, the failure is the right outcome
    and the rule deserves rediscussing.

    A returned row is a failure.
*/

with bridge as (

    select * from {{ ref('bridge_census_tract_apciq_sector') }}

),

counted as (

    select
        count(distinct ct_uid)                                        as tracts,
        count(*) filter (where is_drawn_in_this_sector)               as drawn,
        count(distinct ct_uid) filter (where is_drawn_in_this_sector) as tracts_drawn,
        sum(population_in_sector)                                     as residents,
        sum(population_in_sector) filter (where not is_drawn_in_this_sector)
                                                                      as residents_drawn_elsewhere
    from bridge

),

checks as (

    select
        'some tract is drawn twice or not at all'   as failure,
        tracts::numeric                             as expected,
        drawn::numeric                              as actual
    from counted
    where drawn <> tracts

    union all

    -- drawn = tracts would also hold if one tract carried two flags and
    -- another carried none. Counting distinct tracts closes that door.
    select
        'a tract carries two drawing flags',
        tracts::numeric, tracts_drawn::numeric
    from counted
    where tracts_drawn <> tracts

    union all

    select
        'the map and the figures now disagree on more than 1 % of residents',
        round(residents * 0.01, 0),
        residents_drawn_elsewhere
    from counted
    where residents_drawn_elsewhere > residents * 0.01

)

select * from checks
