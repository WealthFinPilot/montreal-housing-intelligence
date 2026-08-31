/*
    The index restates income FROM a base year. That base year must be the
    census income year the model actually carries -- otherwise the arithmetic
    is impeccable and the answer is wrong.

    This is the failure the base year is exposed to: 2020 appears in two
    places, hard-coded in int_statcan__cpi_quarterly_index and derived from
    the census in fact_affordability. Two constants that must agree, and no
    database constraint can make them. So they are compared.

    A dbt test passes when it returns no rows.

    When this fails, do not edit it to agree. It means the model moved to a
    later census release, and the base year of the index has to move with it.
*/

select distinct
    fact.income_year        as census_income_year,
    fact.income_index_base_year as index_base_year,
    'the index restates from a year the census does not describe' as problem

from {{ ref('fact_affordability') }} as fact

where fact.income_index_base_year is not null
  and fact.income_index_base_year <> fact.income_year
