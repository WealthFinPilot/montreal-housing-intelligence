/*
    dim_interest_rate_series says the same three things staging says.

    The dimension declares its three rows rather than deriving them, so that
    the relationship test against fact_interest_rate proves something. This is
    the other half of that arrangement, and it fails in both directions:

        a series in staging with no row here    a series was added to
                                                series.py and not here
        a row here matching no series           the declaration has gone stale

    IT ALSO CHECKS THE TRANSLATION, NOT ONLY THE MEMBERSHIP

    Staging states the kind of rate as two booleans that are never true
    together; the dimension restates it as one value with three names. That
    restatement is the only place in the project where `policy` is defined as
    "neither posted nor contracted", and a restatement nobody checks is exactly
    how a posted rate ends up priced as a contracted one -- the 1.84 point
    error J4.1 was built to prevent.

    So rate_kind is recomputed here from the booleans and compared. Frequency
    and label are compared too: the Bank of Canada rewords its series titles,
    and a label kept for traceability that no longer matches the source traces
    nothing.
*/

with declared as (

    select
        series_id,
        series_label,
        rate_kind,
        frequency
    from {{ ref('dim_interest_rate_series') }}

),

published as (

    select distinct
        series_id,
        series_label,
        case
            when is_posted_rate     then 'posted'
            when is_contracted_rate then 'contracted'
            else 'policy'
        end                                            as rate_kind,
        frequency
    from {{ ref('stg_bank_of_canada__interest_rates') }}

),

undeclared as (

    select
        p.series_id,
        'series is loaded but not declared in the dimension' as problem
    from published p
    left join declared d on d.series_id = p.series_id
    where d.series_id is null

),

stale as (

    select
        d.series_id,
        'series is declared but no longer loaded' as problem
    from declared d
    left join published p on p.series_id = d.series_id
    where p.series_id is null

),

disagreeing as (

    select
        d.series_id,
        'declaration disagrees with staging on label, kind or frequency' as problem
    from declared d
    join published p on p.series_id = d.series_id
    where d.series_label  is distinct from p.series_label
       or d.rate_kind     is distinct from p.rate_kind
       or d.frequency     is distinct from p.frequency

)

select * from undeclared
union all
select * from stale
union all
select * from disagreeing
