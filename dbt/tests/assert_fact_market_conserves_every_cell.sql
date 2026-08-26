/*
    The pivot loses nothing and invents nothing.

    fact_market turns five rows of the raw layer into one row of five columns.
    That is the one operation in this model where a figure can quietly move:
    a metric mapped to the wrong column, a filter that drops a category, an
    aggregate that keeps the larger of two values. None of it would show up as
    an error, and the row count would stay at 1 653 throughout.

    So the fact is unpivoted back to one row per cell and compared with the
    source, both ways, on the value AND on the status. 8 265 cells in, 8 265
    cells out, each with the same figure and the same reason for being absent
    when it is absent.

    This is the same reasoning as the population reconciliation that proved the
    census tract bridge in J3.4: a table that loses or duplicates a member does
    not reconcile.

    is distinct from, not <>, because most of what is being compared is NULL --
    a withheld price on both sides must count as a match, not as an unknown.
*/

with fact_long as (

    {% for metric in ['sales', 'active_listings', 'median_price',
                      'average_price', 'days_on_market'] %}
    select
        quarter_start_date,
        geography_key,
        property_type_code,
        '{{ metric }}'                as metric_code,
        {{ 'sales_count' if metric == 'sales' else metric }} as value_numeric,
        {{ metric }}_value_status     as value_status
    from {{ ref('fact_market') }}
    {{ "union all" if not loop.last }}
    {% endfor %}

),

source_long as (

    select
        period_start_date             as quarter_start_date,
        geography_key,
        property_category             as property_type_code,
        metric_code,
        value_numeric,
        case
            when value_text is null    then 'not_printed'
            when is_withheld_by_source then 'withheld'
            when is_nothing_to_report  then 'nothing_to_report'
            else 'published'
        end                           as value_status
    from {{ ref('stg_apciq__barometer_statistics') }}
    where period_code = 'quarter'

),

lost as (

    select
        'cell in the source, absent or altered in fact_market' as direction,
        source_long.quarter_start_date,
        source_long.geography_key,
        source_long.property_type_code,
        source_long.metric_code,
        source_long.value_status      as source_status,
        fact_long.value_status        as fact_status
    from source_long
    left join fact_long
           on fact_long.quarter_start_date = source_long.quarter_start_date
          and fact_long.geography_key      = source_long.geography_key
          and fact_long.property_type_code = source_long.property_type_code
          and fact_long.metric_code        = source_long.metric_code
    where fact_long.metric_code is null
       or fact_long.value_numeric is distinct from source_long.value_numeric
       or fact_long.value_status  is distinct from source_long.value_status

),

invented as (

    select
        'cell in fact_market matching nothing in the source' as direction,
        fact_long.quarter_start_date,
        fact_long.geography_key,
        fact_long.property_type_code,
        fact_long.metric_code,
        null                          as source_status,
        fact_long.value_status        as fact_status
    from fact_long
    left join source_long
           on source_long.quarter_start_date = fact_long.quarter_start_date
          and source_long.geography_key      = fact_long.geography_key
          and source_long.property_type_code = fact_long.property_type_code
          and source_long.metric_code        = fact_long.metric_code
    where source_long.metric_code is null

)

select * from lost
union all
select * from invented
