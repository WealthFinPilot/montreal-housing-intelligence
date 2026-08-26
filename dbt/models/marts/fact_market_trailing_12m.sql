/*
    The same market, over the twelve months ending with each quarter.

    1 653 rows again, one per edition x geography x category, and the same five
    measures. It is a separate table from fact_market and not a period_type
    column inside it, for one reason: CONSECUTIVE ROWS HERE OVERLAP BY NINE
    MONTHS. Summing four of them counts most sales four times, and no dbt test
    can protect against a slicer left on the wrong value in a report. Two
    tables make that mistake impossible to make rather than possible to detect.

    WHY IT EXISTS AT ALL, WHEN IT LOOKS LIKE A ROLLING SUM OF fact_market

    Because it is not one, and that was measured before this file was written.

    1. IT CANNOT BE DERIVED. A twelve-month median is not the average of four
       quarterly medians -- there is no arithmetic that recovers it. And on the
       counts, where arithmetic does exist, APCIQ's published 12-month total
       does not equal the sum of its four quarters: it is smaller in 974 of
       1 482 windows, larger in 18, and on the island it is below every single
       time (78 of 78, median -0.46 %, worst -1.67 %). The long comment at the
       top of fact_market.sql records how the two boring explanations for that
       -- a window off by one quarter, a misread column -- were eliminated.

    2. IT CARRIES FIGURES THAT EXIST NOWHERE ELSE. 430 of the 1 653 quarterly
       median prices are withheld as '**', APCIQ having judged the quarter too
       thin to publish a reliable statistic. Over twelve months the sample is
       four times larger, and 341 of those 430 are published here -- 79 %.
       They fall almost entirely on plex and on the small sectors, which is
       precisely where fact_market is blind: only 300 of 551 quarterly plex
       median prices exist, and five sectors have no plex price series at all.

    So the two tables answer different questions. fact_market says what
    happened in a quarter; this one says what the market has done over a year,
    on a sample large enough that APCIQ will speak about the thin sectors.

    WHAT IT SHARES WITH fact_market

    Everything else: the value statuses, the year-over-year change columns
    published rather than recomputed, and the island row that is a total and
    not a nineteenth sector. Read the header of fact_market.sql for those.
*/

with trailing_rows as (

    select *
    from {{ ref('stg_apciq__barometer_statistics') }}
    where period_code = 'trailing_12m'

),

island_control as (

    /*
        Only one of the two J3.2 controls reaches this period. The page control
        compares Tableau 1 with Tableau 2, and Tableau 1 prints the quarter
        only, so nothing on the page can check a 12-month figure against
        another figure on the same page.

        Of the cross-page controls, the parser records ('active_listings',
        'trailing_12m') but not ('sales', 'trailing_12m') -- see
        SECTOR_CONTROLLED in ingestion/apciq/parse.py. The 12-month sales
        column therefore has no stored verdict, and says so below rather than
        borrowing the quarter's. It is checked instead by
        assert_trailing_sales_reconciles_to_the_island.sql, which applies the
        same arithmetic in SQL: eighteen sectors, one island, 84 agreements out
        of 87 and the three failures on an edition already declared.
    */

    select
        edition_year,
        edition_quarter,
        property_category,
        metric_code,
        bool_and(is_reconciled)                    as reconciled
    from {{ ref('stg_apciq__control_totals') }}
    where control_code = 'sectors_vs_island'
      and period_code = 'trailing_12m'
    group by 1, 2, 3, 4

),

pivoted as (

    select
        period_start_date,
        period_end_date,
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

        max(source_pdf)                            as source_pdf,
        max(source_page)                           as source_page,

        min(first_seen_at)                         as first_seen_at,
        max(updated_at)                            as updated_at

    from trailing_rows
    group by 1, 2, 3, 4, 5, 6, 7, 8

)

select
    pivoted.period_end_date || '|' || pivoted.geography_key
        || '|' || pivoted.property_type_code       as trailing_key,

    /*
        The window this row describes: twelve months ending with the edition's
        own quarter. period_end_date is what a chart should be plotted on, and
        it is also what joins to dim_date -- period_start_date lands nine
        months before the previous row's end, which is the overlap this table
        is built to keep visible.
    */
    pivoted.period_start_date,
    pivoted.period_end_date,
    pivoted.edition_year,
    pivoted.edition_quarter,
    pivoted.edition_label,

    -- The quarter this edition reports, so a row here can be lined up with the
    -- fact_market row of the same edition without recomputing a date.
    date_trunc('quarter', pivoted.period_end_date)::date
                                                   as edition_quarter_start_date,

    pivoted.geography_key,
    pivoted.area_code,
    pivoted.property_type_code,
    pivoted.geography_key = 'island:mtl'           as is_island_aggregate,

    pivoted.sales_count,
    pivoted.active_listings,
    pivoted.median_price,
    pivoted.average_price,
    pivoted.days_on_market,

    pivoted.sales_count_change_pct_yoy,
    pivoted.active_listings_change_pct_yoy,
    pivoted.median_price_change_pct_yoy,
    pivoted.average_price_change_pct_yoy,
    pivoted.days_on_market_change_pct_yoy,

    pivoted.sales_value_status,
    pivoted.active_listings_value_status,
    pivoted.median_price_value_status,
    pivoted.average_price_value_status,
    pivoted.days_on_market_value_status,

    /*
        Same three verdicts as fact_market, plus a fourth this period needs:
        'not_controlled_at_ingestion' where the parser recorded no verdict at
        all. It is not a synonym for "fine" -- it says the check was never run
        at load time, which is a different statement from "the check ran and
        passed", and telling those two apart is the whole point of storing
        verdicts rather than exceptions.
    */
    {% for metric in ['sales', 'active_listings'] %}
    case
        when island_{{ metric }}.reconciled is false
            then 'not_reconciled_across_pages'
        when island_{{ metric }}.reconciled
            then 'corroborated'
        else 'not_controlled_at_ingestion'
    end                                            as {{ metric }}_corroboration,
    {% endfor %}

    pivoted.source_pdf,
    pivoted.source_page,
    pivoted.first_seen_at,
    pivoted.updated_at

from pivoted

{% for metric in ['sales', 'active_listings'] %}
left join island_control as island_{{ metric }}
       on island_{{ metric }}.edition_year      = pivoted.edition_year
      and island_{{ metric }}.edition_quarter   = pivoted.edition_quarter
      and island_{{ metric }}.property_category = pivoted.property_type_code
      and island_{{ metric }}.metric_code       = '{{ metric }}'
{% endfor %}
