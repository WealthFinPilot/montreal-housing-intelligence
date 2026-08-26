/*
    The realised market: one row per quarter x geography x property type.

    1 653 rows -- 29 quarters (2019 Q2 to 2026 Q2) x 19 geographies (the island
    and its 18 APCIQ sectors) x 3 categories. That figure is not an estimate:
    the raw layer holds exactly 285 quarterly cells per edition, 19 x 3 x 5,
    with no edition short and none over, so anything other than 1 653 rows
    means the pivot below lost or duplicated something.
    assert_fact_market_is_complete.sql and
    assert_fact_market_conserves_every_cell.sql are what say so.

    WHAT THIS TABLE IS A RECORD OF

    Sales that happened, at the price they happened. Page 65 of the source,
    verbatim: the median price is the « valeur médiane des ventes effectuées »
    and the sale date is that of « l'acceptation de la promesse d'achat ». It
    is not an asking price and not a municipal assessment, and section 41.3 of
    the brief turns on those three staying apart.

    THREE THINGS THAT CANNOT BE DONE WITH THESE ROWS

    1. active_listings NEVER ADDS UP ACROSS TIME. It is « la moyenne des
       données mensuelles pour la période visée » -- an average of month-end
       counts. Adding four quarters of it produces a number that describes
       nothing. It does add up across geographies.

    2. THE ISLAND ROW IS NOT A NINETEENTH SECTOR. It is the total of the other
       eighteen, published separately, so summing all 19 rows counts the island
       twice. is_island_aggregate marks it without needing a join, and it is
       not decoration: the sectors do not always add up to the island exactly
       (2023 Q4 exceeds it by 0.25 % to 1.07 %), so the island row carries
       information no aggregation of sectors reproduces. Prices make the point
       harder still -- eighteen medians never average into a nineteenth.

    3. THE CHANGE COLUMNS ARE YEAR OVER YEAR, AS PUBLISHED. Page 65: « calculés
       par rapport au même trimestre de l'année précédente ». They are APCIQ's
       own arithmetic, kept rather than recomputed, and the two would not agree
       -- see the vintage note below.

    THESE FIGURES ARE A VINTAGE, AND THAT WAS MEASURED

    Each edition publishes its own quarter once and never revisits it, so every
    figure here is what APCIQ printed at the time. Measured on 2026-08-25, on
    the 12-month column those same editions also print:

        the published 12-month sales total is SMALLER than the sum of the four
        quarterly figures it spans, in 974 of 1 482 windows and larger in 18.
        On the island, where the counts are large: 0 windows out of 78 above,
        median gap -0.46 %, worst -1.67 %.

    Two boring explanations were eliminated before this was believed. The
    window is not off by one quarter (33.1 % exact matches as read, 4.1 %
    shifted). The column is not misread: the eighteen sectors add up to the
    island exactly on 84 of 87 comparisons, the three failures being 2023 Q4,
    an edition already declared defective -- and that control had never been
    applied to the 12-month column before.

    What remains is APCIQ's, and the source does not say what it is. So this
    table states the fact rather than explaining it: SUMMING FOUR QUARTERS DOES
    NOT PRODUCE APCIQ'S OWN 12-MONTH FIGURE, and overstates it by around half a
    percent. When the 12-month figure is what is wanted, read
    fact_market_trailing_12m, which holds the one APCIQ publishes.
    assert_trailing_12m_stays_under_the_sum_of_its_quarters.sql keeps that
    relationship under test.
*/

with quarterly as (

    select *
    from {{ ref('stg_apciq__barometer_statistics') }}
    where period_code = 'quarter'

),

/*
    THE TWO CONTROLS, AND WHY THEY DO NOT ANSWER THE SAME QUESTION

    page_table1_vs_table2 asks "did we read this page correctly?" -- two totals
    printed a few centimetres apart, read with the same column anchors. Its
    scope is one area of one edition.

    sectors_vs_island asks "is the source consistent from one page to the
    next?" -- the eighteen sector pages against the island page. Its scope is
    one category of one edition, and its verdict therefore applies to all
    nineteen areas of that edition, not to one of them.

    Keeping them apart is what let J3.2 tell a source defect from a reading
    defect: when the sales row of a page reconciles and the listings row does
    not, the columns are demonstrably right and the contradiction is the
    publisher's.
*/

page_control as (

    select
        edition_year,
        edition_quarter,
        scope                                      as area_code,
        metric_code,
        bool_and(is_reconciled)                    as reconciled
    from {{ ref('stg_apciq__control_totals') }}
    where control_code = 'page_table1_vs_table2'
      and period_code = 'quarter'
    group by 1, 2, 3, 4

),

island_control as (

    select
        edition_year,
        edition_quarter,
        property_category,
        metric_code,
        bool_and(is_reconciled)                    as reconciled
    from {{ ref('stg_apciq__control_totals') }}
    where control_code = 'sectors_vs_island'
      and period_code = 'quarter'
    group by 1, 2, 3, 4

),

pivoted as (

    /*
        Long to wide. One row of the raw layer is one printed cell, and this
        turns the five metric rows of a (quarter, area, category) into one row
        of five columns.

        filter (where ...) rather than a CASE inside the aggregate: there is at
        most one cell per metric -- the raw primary key guarantees it -- so max
        is here to collapse a single value, not to choose between several. If
        the guarantee ever broke, the conservation test would fail rather than
        this silently keeping the larger of two figures.
    */

    select
        period_start_date                          as quarter_start_date,
        period_end_date                            as quarter_end_date,
        edition_year,
        edition_quarter,
        edition_label,
        geography_key,
        area_code,
        property_category                          as property_type_code,

        max(value_numeric) filter (where metric_code = 'sales')
                                                   as sales_count,
        max(value_numeric) filter (where metric_code = 'active_listings')
                                                   as active_listings,
        max(value_numeric) filter (where metric_code = 'median_price')
                                                   as median_price,
        max(value_numeric) filter (where metric_code = 'average_price')
                                                   as average_price,
        max(value_numeric) filter (where metric_code = 'days_on_market')
                                                   as days_on_market,

        max(change_percent) filter (where metric_code = 'sales')
                                                   as sales_count_change_pct_yoy,
        max(change_percent) filter (where metric_code = 'active_listings')
                                                   as active_listings_change_pct_yoy,
        max(change_percent) filter (where metric_code = 'median_price')
                                                   as median_price_change_pct_yoy,
        max(change_percent) filter (where metric_code = 'average_price')
                                                   as average_price_change_pct_yoy,
        max(change_percent) filter (where metric_code = 'days_on_market')
                                                   as days_on_market_change_pct_yoy,

        /*
            Why each measure is what it is. The four states a Baromètre cell
            can be in survive the pivot instead of collapsing into one NULL:

              published          a figure
              withheld           '**' -- « Nombre de transactions insuffisant
                                 pour produire une statistique fiable ». The
                                 market exists; the statistic is not reliable
                                 enough to print
              nothing_to_report  '-' -- there is nothing of this kind here.
                                 L'Île-des-Sœurs has no plex at all
              not_printed        nothing appeared on the page. Seen only on
                                 days-on-market rows of the 2019 template

            A withheld price and an absent price are different facts about the
            market, and a dashboard that shows both as a blank has lost the
            difference.
        */
        {% for metric in ['sales', 'active_listings', 'median_price',
                          'average_price', 'days_on_market'] %}
        max(case
                when value_text is null            then 'not_printed'
                when is_withheld_by_source         then 'withheld'
                when is_nothing_to_report          then 'nothing_to_report'
                else 'published'
            end) filter (where metric_code = '{{ metric }}')
                                                   as {{ metric }}_value_status,
        {% endfor %}

        -- Provenance. Every figure on a row comes off the same page.
        max(source_pdf)                            as source_pdf,
        max(source_page)                           as source_page,

        min(first_seen_at)                         as first_seen_at,
        max(updated_at)                            as updated_at

    from quarterly
    group by 1, 2, 3, 4, 5, 6, 7, 8

),

corroborated as (

    select
        pivoted.*,

        /*
            What the controls say about the two count metrics of this row.

              corroborated              every control touching it reconciled
              contradicted_on_its_page  the page disagrees with itself. The
                                        reading of that page is not settled
              not_reconciled_across_pages
                                        the page is coherent with itself but
                                        the eighteen sectors do not match the
                                        island for this edition and category

            The second is the graver verdict, so it wins when both apply.

            THERE IS NO SUCH COLUMN FOR PRICES OR DAYS ON MARKET, AND THAT IS
            NOT AN OVERSIGHT. Both controls are sums, and eighteen medians do
            not add up to a nineteenth: no arithmetic available on these pages
            can check a median or an average. Inventing a column that always
            said "corroborated" would claim a verification that never happened.
        */
        {% for metric in ['sales', 'active_listings'] %}
        case
            when page_{{ metric }}.reconciled is false
                then 'contradicted_on_its_page'
            when island_{{ metric }}.reconciled is false
                then 'not_reconciled_across_pages'
            when page_{{ metric }}.reconciled
             and island_{{ metric }}.reconciled
                then 'corroborated'
        end                                        as {{ metric }}_corroboration{{ "," if not loop.last }}
        {% endfor %}

    from pivoted

    {% for metric in ['sales', 'active_listings'] %}
    left join page_control as page_{{ metric }}
           on page_{{ metric }}.edition_year    = pivoted.edition_year
          and page_{{ metric }}.edition_quarter = pivoted.edition_quarter
          and page_{{ metric }}.area_code       = pivoted.area_code
          and page_{{ metric }}.metric_code     = '{{ metric }}'

    left join island_control as island_{{ metric }}
           on island_{{ metric }}.edition_year       = pivoted.edition_year
          and island_{{ metric }}.edition_quarter    = pivoted.edition_quarter
          and island_{{ metric }}.property_category  = pivoted.property_type_code
          and island_{{ metric }}.metric_code        = '{{ metric }}'
    {% endfor %}

)

select
    /*
        A single-column key, so that "one row per quarter, geography and
        category" can be tested with the built-in unique test rather than by
        adding a package for one assertion. Power BI does not need it -- its
        relationships are single-column and it joins on the three keys
        separately -- but the guarantee is worth stating in the table.
    */
    quarter_start_date || '|' || geography_key || '|' || property_type_code
                                                   as market_key,

    quarter_start_date,
    quarter_end_date,
    edition_year,
    edition_quarter,
    edition_label,

    geography_key,
    area_code,
    property_type_code,

    -- See point 2 at the top. Summing across this without filtering counts the
    -- island twice.
    geography_key = 'island:mtl'                   as is_island_aggregate,

    sales_count,
    active_listings,
    median_price,
    average_price,
    days_on_market,

    sales_count_change_pct_yoy,
    active_listings_change_pct_yoy,
    median_price_change_pct_yoy,
    average_price_change_pct_yoy,
    days_on_market_change_pct_yoy,

    sales_value_status,
    active_listings_value_status,
    median_price_value_status,
    average_price_value_status,
    days_on_market_value_status,

    sales_corroboration,
    active_listings_corroboration,

    source_pdf,
    source_page,
    first_seen_at,
    updated_at

from corroborated
