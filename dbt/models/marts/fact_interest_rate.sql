/*
    One row per series per observation date. The macro context of the market.

    WHY THIS MODEL EXISTS AT ALL, GIVEN THAT STAGING ALREADY HAS THE ROWS

    Until J4.2 the Power BI report read staging directly. That worked, and it
    quietly contradicted the architecture the project claims: raw is close to
    the source, staging is typed and filtered, marts is what a consumer reads.
    A report file that names a staging table is a report file that documents
    the exception rather than the rule -- and since J4.2 the report definition
    is a versioned text file, the exception would be the first thing a reader
    sees.

    So this model is a thin one, and deliberately so. It adds no arithmetic. It
    exists to give the consumption layer a fact table with a dimension beside
    it, and to keep the staging layer for transformation.

    THE GRAIN IS THE DAY, NOT THE QUARTER

    The three series do not share a rhythm: the policy rate publishes every
    business day, both mortgage rates once a week. Averaging them here into a
    quarter would bake one aggregation choice into the table and hide the
    difference the brief (section 22) asks to keep visible. dim_date is at the
    day grain for exactly this reason, so the aggregation is a measure, not a
    column.

    WHAT MUST NEVER BE DONE WITH rate_percent

    It must never be summed. A rate is an intensive quantity: adding the
    Tuesday rate to the Wednesday rate produces a number with no referent. Any
    visual over this table aggregates with an average, and a weekly series
    averaged over a quarter is the mean of about 13 observations while the
    daily one is the mean of about 65. That is not a defect -- it is what the
    publishers publish -- but it is a difference no chart should imply away.

    RELATION TO fact_mortgage_scenario

    fact_mortgage_scenario already carries a quarterly contract rate, computed
    upstream and used to price a loan. This table does NOT feed it and is not
    derived from it. The two answer different questions: one prices a mortgage
    at a stated quarter, the other shows the series moving. They are expected
    to agree in shape, and comparing them is a legitimate check, not a
    duplication to remove.
*/

with observed as (

    select
        series_id,
        observation_date,
        rate_percent,
        source_url,
        first_seen_at,
        updated_at
    from {{ ref('stg_bank_of_canada__interest_rates') }}

    /*
        Staging has already dropped the empty values -- a day on which a series
        published nothing produces no row at all, neither a zero nor a carried
        forward figure. Nothing to filter again here; restating the filter
        would only create a second place for it to drift.
    */

)

select
    series_id || '|' || to_char(observation_date, 'YYYY-MM-DD')  as interest_rate_key,
    series_id,
    observation_date,
    rate_percent,
    source_url,
    first_seen_at,
    updated_at
from observed
