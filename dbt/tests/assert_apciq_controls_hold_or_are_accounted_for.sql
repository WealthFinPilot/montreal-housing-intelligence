/*
    Every APCIQ control must either pass, or be one of the defects already
    investigated and written down.

    THE POINT OF THIS TEST

    Once a pipeline is allowed to load an edition whose source does not add
    up, "the control failed" stops being an event. Ninety-odd failing rows sit
    in the database, and the ninety-first goes unnoticed. This test is what
    keeps them noticeable: the known ones are declared in the seed
    apciq_known_publisher_defect, and anything else is a failure.

    IT CHECKS BOTH DIRECTIONS, AND THE SECOND ONE MATTERS MORE

        an unexplained failure   a control is off and no seed row covers it.
                                 Either APCIQ published a new defect, or a
                                 change to the parser broke something. Both
                                 need a person.

        a stale exemption        a seed row covers nothing. The defect is
                                 gone: APCIQ republished a corrected edition,
                                 or the reading changed. Either way the
                                 written record no longer matches reality, and
                                 an exemption nobody re-examines is how a
                                 workaround quietly becomes permanent.

    A returned row is a failure. The columns say which direction it is, on
    which edition, and how far off.

    WHAT THIS TEST DOES NOT DO

    It does not judge severity. 2023 Q4 misses by 8 sales out of 2 850 and
    2021 Q4 misses by 462 listings out of 1 013; both are declared here, and
    the difference between them belongs in the mart that decides what to show.
*/

with controls as (

    select * from {{ ref('stg_apciq__control_totals') }}

),

known as (

    select * from {{ ref('apciq_known_publisher_defect') }}

),

unexplained as (

    select
        'unexplained control failure' as direction,
        controls.edition_label,
        controls.control_code,
        controls.metric_code,
        controls.scope,
        controls.property_category,
        controls.published_total,
        controls.computed_total,
        controls.difference

    from controls
    left join known
           on known.edition_year   = controls.edition_year
          and known.edition_quarter = controls.edition_quarter
          and known.control_code    = controls.control_code
          and known.metric_code     = controls.metric_code

    where not controls.is_reconciled
      and known.edition_year is null

),

stale as (

    select
        'declared defect no longer occurs' as direction,
        known.edition_year || ' Q' || known.edition_quarter as edition_label,
        known.control_code,
        known.metric_code,
        null as scope,
        null as property_category,
        null::integer as published_total,
        null::integer as computed_total,
        null::integer as difference

    from known
    where not exists (
        select 1
          from controls
         where controls.edition_year    = known.edition_year
           and controls.edition_quarter = known.edition_quarter
           and controls.control_code    = known.control_code
           and controls.metric_code     = known.metric_code
           and not controls.is_reconciled
    )
    -- Only for editions actually loaded. A seed row for an edition nobody has
    -- ingested yet is a note about the future, not a stale exemption.
    and exists (
        select 1
          from controls
         where controls.edition_year    = known.edition_year
           and controls.edition_quarter = known.edition_quarter
    )

)

select * from unexplained
union all
select * from stale
