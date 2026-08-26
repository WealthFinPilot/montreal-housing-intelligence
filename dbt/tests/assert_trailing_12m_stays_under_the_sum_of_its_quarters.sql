/*
    The relationship between the two market tables, held under test.

    Measured on the island on 2026-08-25, over the 78 comparable windows:
    APCIQ's published 12-month sales total is BELOW the sum of the four
    quarterly figures it spans every single time -- 78 of 78 -- by a median of
    0.46 % and never by more than 1.67 %.

    That is a fact about the source, not a rule imposed on it, and this test
    exists so that the day it stops being true, somebody is told. Two things
    would break it, and both need a person rather than a fix:

        the gap turns positive     the quarterly figures are no longer the
                                   first vintage, or the 12-month column has
                                   started meaning something else
        the gap grows past 3 %     whatever APCIQ does between publications
                                   has changed scale, and the note in
                                   fact_market.sql no longer describes it

    WHERE 3 % COMES FROM

    Not from tuning. The worst observed gap is 1.67 % and the next order of
    magnitude up is where a real change would land, so the bound sits in the
    empty space between them -- the same reasoning as the 1.5 size ratio in
    J3.4, whose measured populations were 1.016 on one side and 2.87 on the
    other. Any bound between 2 % and 10 % selects the same rows today. If the
    day comes when the observed gap climbs into the bound, the test fails and
    the bound gets re-argued, which is the correct behaviour.

    THE ISLAND ONLY

    A sector can sell four houses in a quarter, where one transaction moving
    between vintages is 25 %. Small-number noise would drown the signal and
    force a tolerance so wide it would test nothing. The island carries the
    volume that makes half a percent meaningful.
*/

with quarterly as (

    select
        property_type_code,
        quarter_start_date,
        extract(year from quarter_start_date)::int * 4
            + extract(quarter from quarter_start_date)::int  as quarter_index,
        sales_count
    from {{ ref('fact_market') }}
    where is_island_aggregate

),

rolled as (

    select
        *,
        sum(sales_count) over (
            partition by property_type_code
            order by quarter_index
            rows between 3 preceding and current row
        )                                                    as sum_of_four,
        count(sales_count) over (
            partition by property_type_code
            order by quarter_index
            rows between 3 preceding and current row
        )                                                    as quarters_in_window
    from quarterly

),

published as (

    select
        property_type_code,
        extract(year from period_end_date)::int * 4
            + extract(quarter from period_end_date)::int     as quarter_index,
        edition_label,
        sales_count                                          as published_total
    from {{ ref('fact_market_trailing_12m') }}
    where is_island_aggregate

),

compared as (

    select
        published.edition_label,
        rolled.property_type_code,
        rolled.sum_of_four,
        published.published_total,
        (published.published_total - rolled.sum_of_four)::numeric
            / nullif(rolled.sum_of_four, 0)                  as relative_gap
    from rolled
    join published using (property_type_code, quarter_index)
    -- Only full windows: the first three editions have no four quarters behind
    -- them, and comparing a partial sum would manufacture a failure.
    where rolled.quarters_in_window = 4

)

select
    edition_label,
    property_type_code,
    round(relative_gap * 100, 2)                             as relative_gap_percent
from compared
where relative_gap > 0
   or relative_gap < -0.03
