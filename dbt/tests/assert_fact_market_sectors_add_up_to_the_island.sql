/*
    The eighteen sectors add up to the island, on the modelled table.

    J3.2 already ran this arithmetic while reading the PDFs and stored the
    verdicts. This runs it again on fact_market, which is a different claim:
    the first says APCIQ is coherent from one page to the next, this one says
    the pivot did not move a figure from one sector to another. A swap between
    two sectors leaves every stored verdict intact and every row count correct.

    SALES ONLY, AND ON PURPOSE

    Sales are counted, so eighteen of them add up to a nineteenth exactly, with
    no tolerance to choose. Active listings are averages of month-end counts:
    eighteen rounded averages need a few units of slack against a rounded
    nineteenth, and that slack is already declared once, at ingestion, in
    parse.py. Restating it here would mean two constants that can drift apart
    and a test that passes because the looser of the two won. Listings stay
    covered by the stored verdicts and by
    assert_apciq_controls_hold_or_are_accounted_for.

    Prices and days on market are not summed anywhere in this file, for the
    reason the parser gives: eighteen medians do not add up to a nineteenth.

    A returned row is a failure unless the edition is declared in
    apciq_known_publisher_defect -- 2023 Q4, whose sectors exceed the island by
    0.25 % to 1.07 % while every page agrees with itself.
*/

with sector_totals as (

    select
        quarter_start_date,
        edition_year,
        edition_quarter,
        edition_label,
        property_type_code,
        sum(sales_count)                          as computed_total,
        count(*)                                  as sectors_counted
    from {{ ref('fact_market') }}
    where not is_island_aggregate
    group by 1, 2, 3, 4, 5

),

island_totals as (

    select
        quarter_start_date,
        property_type_code,
        sales_count                               as published_total
    from {{ ref('fact_market') }}
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
    join island_totals using (quarter_start_date, property_type_code)

)

select
    compared.edition_label,
    compared.property_type_code,
    compared.sectors_counted,
    compared.difference
from compared
where (
        compared.computed_total is distinct from compared.published_total
        -- A comparison built on anything other than the 18 sectors is itself a
        -- failure, whatever the totals say.
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
