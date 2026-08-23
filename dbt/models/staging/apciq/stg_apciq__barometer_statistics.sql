{{
    config(
        materialized = 'view'
    )
}}

/*
    APCIQ Baromètre figures, typed and dated. One row per published cell.

    The raw layer stores every cell as the text APCIQ printed. This is where
    that text becomes a number, a date range and a geography key -- the same
    division of labour as the other two staging models. Nothing is reshaped
    here: the pivot into fact_market belongs to J3.4.

    WHAT A CELL CAN SAY, AND WHY THAT SURVIVES THE CAST

    Four states, and flattening them into one NULL would lose real
    information:

        '123 456 $'  a figure
        '**'         APCIQ withheld it: « Nombre de transactions insuffisant
                     pour produire une statistique fiable ». The market exists,
                     the statistic is not reliable enough to print
        '-'          nothing to report. On a count row that means zero
        NULL         nothing was printed at all. Only ever seen on
                     days-on-market rows of the 2019-era template

    So the model carries value_numeric alongside two flags. A reader who
    ignores the flags still gets correct arithmetic; a reader who wants to know
    why a value is missing can find out.

    WHY A DASH IS READ AS ZERO ON A COUNT ROW, AND NOWHERE ELSE

    L'Île-des-Sœurs has no plex at all, so its plex count rows carry a dash
    quarter after quarter while its plex price rows carry '**'. Reading the
    dash as zero is an interpretation, and it is one the data verifies rather
    than one this model assumes: with the dash read as zero, the eighteen
    sectors add up to the island page exactly on every archived quarter. The
    test assert_apciq_sectors_add_up_to_the_island re-checks it in SQL on every
    dbt run.

    A dash on a PRICE row would mean no transaction to price, not a price of
    zero, so prices and delays keep their NULL.

    WHAT MUST NOT BE DONE WITH THESE ROWS

    * period_code = 'trailing_12m' rows OVERLAP between editions by
      construction -- each covers the twelve months ending with its own
      quarter. Summing them counts most sales four times.
    * active_listings is « la moyenne des données mensuelles pour la période
      visée », an average of month-end counts. It adds up across geographies
      and never across time.
    * change_percent is year over year -- « par rapport au même trimestre de
      l'année précédente » -- not quarter over quarter.
    * median_price is a SALE price (« valeur médiane des ventes effectuées »).
      Not an asking price, not a municipal assessment. Section 41.3 of the
      brief turns on keeping those three apart.
*/

with source as (

    select * from {{ source('apciq', 'apciq_barometer_statistic') }}

),

dated as (

    select
        *,

        -- First day of the edition's own quarter.
        make_date(edition_year, 3 * (edition_quarter - 1) + 1, 1) as quarter_start_date

    from source

),

typed as (

    select
        edition_year,
        edition_quarter,
        edition_year || ' Q' || edition_quarter as edition_label,

        /*
            The key into marts.dim_geography. The raw layer keeps APCIQ's own
            vocabulary ('island', 'sector-07'); the join key belongs here.
            Zero padding is dropped because dim_geography numbers its sectors
            without it.
        */
        case
            when area_code = 'island' then 'island:mtl'
            else 'apciq_sector:' || ltrim(substring(area_code from 8), '0')
        end as geography_key,

        area_code,
        property_category,
        metric_code,
        period_code,

        /*
            What the figure covers. A quarter row covers its own quarter; a
            trailing row covers the twelve months ending with it. The five-year
            row is a change with no period of its own, so it gets no dates
            rather than a made-up range.
        */
        case period_code
            when 'quarter'      then quarter_start_date
            when 'trailing_12m' then (quarter_start_date + interval '3 months'
                                      - interval '12 months')::date
        end as period_start_date,

        case
            when period_code in ('quarter', 'trailing_12m')
            then (quarter_start_date + interval '3 months' - interval '1 day')::date
        end as period_end_date,

        -- The unit of value_numeric. A long table mixes counts, dollars and
        -- days in one column; this says which is which without a lookup.
        case metric_code
            when 'sales'            then 'count'
            when 'active_listings'  then 'count'
            when 'median_price'     then 'cad'
            when 'average_price'    then 'cad'
            when 'days_on_market'   then 'days'
        end as unit,

        /*
            The cast. regexp_replace strips the currency sign, the percent
            sign and the non-breaking spaces APCIQ uses between thousands;
            what is left is either a whole number or nothing.

            A count row reads a dash as zero. A price or delay row does not.
        */
        case
            when value_text is null then null
            when value_text = '**'  then null
            when value_text = '-'
                then case when metric_code in ('sales', 'active_listings')
                          then 0 end
            when regexp_replace(value_text, '[^0-9-]', '', 'g') ~ '^-?\d+$'
                then regexp_replace(value_text, '[^0-9-]', '', 'g')::bigint
        end as value_numeric,

        case
            when change_percent_text is null then null
            when change_percent_text in ('**', '-') then null
            when regexp_replace(change_percent_text, '[^0-9-]', '', 'g') ~ '^-?\d+$'
                then regexp_replace(change_percent_text, '[^0-9-]', '', 'g')::int
        end as change_percent,

        /*
            Why the value is missing, kept apart. Same reasoning as
            is_posted_rate on the Bank of Canada model: a flag that a
            downstream model can honour, rather than a silence it has to guess
            at.
        */
        value_text = '**' as is_withheld_by_source,
        value_text = '-'  as is_nothing_to_report,

        -- Kept for audit. Any figure can be checked against its page.
        value_text,
        change_percent_text,
        source_area_label,
        source_category_label,
        source_metric_label,
        source_pdf,
        source_page,

        first_seen_at,
        updated_at

    from dated

)

select * from typed
