{{
    config(
        materialized = 'view'
    )
}}

/*
    Bank of Canada interest rates, typed and labelled.

    This is the only place where the text stored in raw becomes a number. The
    raw layer records what the source said; this layer decides what it means.
    Keeping those two acts apart is what lets us re-interpret the data without
    re-downloading it, and re-download without losing our interpretation.

    The cast is guarded by a pattern check rather than written as a bare
    value_raw::numeric. A bare cast would abort the whole run the day the API
    returns something unexpected. Here, anything that is not a plain number
    becomes NULL, and the not_null test on rate_percent fails loudly on exactly
    the rows concerned -- which tells us WHICH values broke, not just that
    something did.
*/

with source as (

    /*
        Days with no publication are dropped here, and only here.

        Valet can send an empty value to mean "nothing was published that day".
        That is not a rate of zero and it is not an observation, so it has no
        place in a table of observations. The raw layer keeps every one of them
        untouched, so nothing is lost -- this is a reading decision, not a
        deletion.

        The useful consequence: after this filter, a value that fails to parse
        can only mean one thing, that the source changed its format. The
        not_null test on rate_percent becomes a format alarm with no false
        positives.

        Measured on 2026-08-22 over 2015-2026: zero empty values on both
        series, so this filter currently drops nothing.
    */
    select *
    from {{ source('bank_of_canada', 'boc_observation') }}
    where value_raw is not null
      and value_raw <> ''

),

typed as (

    select
        series_id,
        observation_date,

        -- Percentage points: 2.25 means 2.25 %, not 0.0225. Named
        -- rate_percent so nobody has to guess which of the two it is.
        case
            when value_raw ~ '^-?[0-9]+(\.[0-9]+)?$'
            then value_raw::numeric(8, 4)
        end as rate_percent,

        -- Kept alongside the typed value so a failing test can be traced back
        -- to what the source actually sent.
        value_raw,

        source_url,
        run_id,
        first_seen_at,
        updated_at

    from source

),

labelled as (

    select
        series_id,

        /*
            Labels mirror the catalogue in ingestion/bank_of_canada/series.py,
            which is the source of truth. They are duplicated here on purpose
            rather than joined from a seed, and the duplication is made safe by
            the accepted_values test on series_id: adding a series upstream
            without updating this CASE makes `dbt test` fail. The drift cannot
            go unnoticed.
        */
        case series_id
            when 'V39079'              then 'Target for the overnight rate'
            when 'V80691335'           then 'Conventional mortgage: 5-year (posted)'
            when 'FVI_MTG_RATE_5Y_FIX' then '5-year fixed, high-ratio mortgage (contracted)'
        end as series_label,

        -- The observed publication rhythm of each series. Two different grains
        -- live in this table and must never be averaged together blindly.
        case series_id
            when 'V39079'              then 'business daily'
            when 'V80691335'           then 'weekly'
            when 'FVI_MTG_RATE_5Y_FIX' then 'weekly'
        end as frequency,

        /*
            The 5-year mortgage rate is the rate chartered banks ADVERTISE, not
            the rate a borrower negotiates -- discounts of one to two points are
            ordinary. Same distinction as asking_price versus sale_price. This
            flag exists so no downstream model can use it as a contract rate by
            accident.
        */
        series_id = 'V80691335' as is_posted_rate,

        /*
            The counterpart flag, added on 2026-08-26. FVI_MTG_RATE_5Y_FIX is a
            CONTRACTED rate on a high-ratio mortgage -- the very loan a buyer
            putting down the legal minimum takes out. On 2026 Q2 it stood 1.80
            points below the posted series, and that gap runs through the
            qualifying rate into every income figure downstream, so which of
            the two a model picked must never be guessable from the number.
        */
        series_id = 'FVI_MTG_RATE_5Y_FIX' as is_contracted_rate,

        observation_date,
        rate_percent,
        value_raw,
        source_url,
        run_id,
        first_seen_at,
        updated_at

    from typed

)

select * from labelled
