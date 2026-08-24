/*
    Every tract, every dissemination area and every resident must come out of
    the bridge exactly once.

    This is the test that catches the failure mode the bridge is most exposed
    to, and it is a SILENT one. A tract in a split borough reaches its sector
    through a second point-in-polygon, against a neighbourhood file. If that
    file ever moves a border, or drops a polygon, or renumbers itself, a point
    can fall outside every eligible polygon -- and then its dissemination area
    simply does not appear in the join.

    Nothing about that looks wrong afterwards. The remaining areas of the tract
    still produce weights that sum to 1.0, because the weight is a share of
    whatever survived. The tract keeps its row, keeps a plausible sector, and
    quietly reports the income of fewer people than live there.

    Counting is what exposes it. Measured 2026-08-24:

        541 tracts          in staging, 541 out of the bridge
        3 228 areas         in staging, 3 228 out of the bridge
        2 004 265 residents in staging, 2 004 265 out of the bridge

    The population identity is the sharp one: it fails on a lost area AND on a
    double-counted one, which the tract count alone would miss.

    A returned row is a failure.
*/

with from_tracts as (

    select
        count(*)                                as tracts,
        sum(dissemination_area_count)           as areas,
        sum(population_2021)                    as residents
    from {{ ref('stg_statcan__census_tracts') }}

),

from_bridge as (

    select
        count(distinct ct_uid)                  as tracts,
        sum(dissemination_area_count)           as areas,
        sum(population_in_sector)               as residents
    from {{ ref('bridge_census_tract_apciq_sector') }}

),

compared as (

    select
        'census tracts'         as counting,
        from_tracts.tracts      as in_staging,
        from_bridge.tracts      as in_bridge
    from from_tracts, from_bridge

    union all

    select
        'dissemination areas',
        from_tracts.areas,
        from_bridge.areas
    from from_tracts, from_bridge

    union all

    select
        'residents',
        from_tracts.residents,
        from_bridge.residents
    from from_tracts, from_bridge

)

select
    counting,
    in_staging,
    in_bridge,
    in_bridge - in_staging as difference
from compared
where in_staging is distinct from in_bridge
