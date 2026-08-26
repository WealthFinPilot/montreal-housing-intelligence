/*
    The same arithmetic on the twelve-month column, which nothing else checks.

    WHY THIS FILE EXISTS SEPARATELY

    The parser controls three metric-period pairs -- see SECTOR_CONTROLLED in
    ingestion/apciq/parse.py -- and ('sales', 'trailing_12m') is not one of
    them. That column went into the database in J3.2 with no verdict attached
    to it, and nobody noticed until J3.5 leaned on it: the finding that APCIQ's
    published 12-month total differs from the sum of its four quarters rests
    entirely on this column being read correctly.

    So it was checked, on 2026-08-25, before that finding was believed:
    eighteen sectors add up to the island on 84 of 87 comparisons, the three
    failures being 2023 Q4, an edition already declared. The column is sound
    and the difference belongs to the publisher.

    This test is what keeps that true. The proper fix is to add the pair to
    SECTOR_CONTROLLED so the verdict is recorded at ingestion like the others;
    that costs a full re-read of 29 PDFs and is worth doing the next time the
    parser runs, not now. Until then the check lives here, and its result is
    the same.

    The seed rows it honours are the existing ones: a defect declared for
    sectors_vs_island on sales covers both periods of that edition, because it
    is one publisher error showing up in two columns.
*/

with sector_totals as (

    select
        period_end_date,
        edition_year,
        edition_quarter,
        edition_label,
        property_type_code,
        sum(sales_count)                          as computed_total,
        count(*)                                  as sectors_counted
    from {{ ref('fact_market_trailing_12m') }}
    where not is_island_aggregate
    group by 1, 2, 3, 4, 5

),

island_totals as (

    select
        period_end_date,
        property_type_code,
        sales_count                               as published_total
    from {{ ref('fact_market_trailing_12m') }}
    where is_island_aggregate

),

compared as (

    select
        sector_totals.edition_label,
        sector_totals.edition_year,
        sector_totals.edition_quarter,
        sector_totals.property_type_code,
        sector_totals.sectors_counted,
        sector_totals.computed_total,
        island_totals.published_total,
        sector_totals.computed_total - island_totals.published_total as difference
    from sector_totals
    join island_totals using (period_end_date, property_type_code)

)

select
    compared.edition_label,
    compared.property_type_code,
    compared.sectors_counted,
    compared.difference
from compared
where (
        compared.computed_total is distinct from compared.published_total
        or compared.sectors_counted <> 18
      )
  and not exists (
        select 1
        from {{ ref('apciq_known_publisher_defect') }} as declared
        where declared.edition_year    = compared.edition_year
          and declared.edition_quarter = compared.edition_quarter
          and declared.control_code    = 'sectors_vs_island'
          and declared.metric_code     = 'sales'
      )
