/*
    A time series has one value per date. This asserts it survived the
    transformation.

    A dbt test passes when its query returns NO rows. So this looks for the
    thing that must not exist -- a series and date appearing more than once --
    and passing means finding nothing.

    The primary key on raw.boc_observation already makes duplicates impossible
    at the source. This guards the layer above it: a future join or union in
    staging could reintroduce them, and the database has no way to know that
    was a mistake.
*/

select
    series_id,
    observation_date,
    count(*) as row_count

from {{ ref('stg_bank_of_canada__interest_rates') }}

group by series_id, observation_date
having count(*) > 1
