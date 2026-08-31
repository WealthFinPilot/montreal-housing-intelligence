/*
    The theoretical income must be missing whenever it cannot be computed,
    and it must never quietly be the 2020 figure wearing a newer label.

    THREE WAYS THIS CAN GO WRONG, AND ALL THREE ARE CHECKED

    1. A row has both an income and a factor, and yet no indexed income. The
       arithmetic silently dropped something.

    2. A row has no factor -- an incomplete quarter -- and yet carries an
       indexed income anyway. That is the blank-versus-zero failure this
       project has met five times: it would read as "no inflation occurred".

    3. A row is flagged 'cpi_rmr462' while carrying no factor, or flagged
       'not_indexed' while carrying one. The column that names the assumption
       would then be describing a different row than the one it sits on.

    The eleven tracts with no published 2020 income are NOT a failure here:
    no income in means no income out, and multiplying an absence by 1.26
    leaves it absent. They are counted by
    assert_affordability_never_invents_a_missing_figure.

    A dbt test passes when it returns no rows.
*/

with rows_to_check as (

    select
        affordability_key,
        household_income,
        income_index_factor,
        income_index_basis,
        household_income_indexed
    from {{ ref('fact_affordability') }}

)

select
    affordability_key,
    'income and factor both present, but no indexed income' as problem
from rows_to_check
where household_income is not null
  and income_index_factor is not null
  and household_income_indexed is null

union all

select
    affordability_key,
    'indexed income computed without a factor' as problem
from rows_to_check
where income_index_factor is null
  and household_income_indexed is not null

union all

select
    affordability_key,
    'the basis column contradicts the factor it sits beside' as problem
from rows_to_check
where (income_index_basis = 'cpi_rmr462' and income_index_factor is null)
   or (income_index_basis = 'not_indexed' and income_index_factor is not null)
