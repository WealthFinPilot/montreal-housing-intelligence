/*
    The weights of a census tract must add up to exactly one tract.

    A weight of 0.9286 only means "92.86 % of this tract" while the rest of the
    tract is somewhere in the table too. If a row is ever lost -- a point that
    fell outside every eligible polygon, a join that filtered one out -- the
    remaining weights still look reasonable, because each is computed as a share
    of whatever survived. They would simply describe a smaller tract than the
    one that exists.

    So the sum is checked rather than the individual weights. 541 tracts, every
    one summing to 1 within 2 parts per million, which is rounding at six
    decimal places and nothing else.

    This is a different question from
    assert_the_bridge_loses_no_census_tract_and_no_resident.sql, which counts
    rows and people across the whole table. This one is per tract, so it names
    the tract that went wrong instead of reporting that a total moved.

    A returned row is a failure.
*/

select
    ct_uid,
    count(*)                        as rows_for_this_tract,
    sum(population_weight)          as total_weight,
    sum(population_weight) - 1      as drift
from {{ ref('bridge_census_tract_apciq_sector') }}
group by ct_uid
having abs(sum(population_weight) - 1) > 0.000002
