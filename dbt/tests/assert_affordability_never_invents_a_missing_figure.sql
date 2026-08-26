/*
    A missing price or a missing income produces a missing ratio -- never a
    number.

    Section 41.1 of the brief, made mechanical. There are two ways this table
    could quietly fabricate an answer, and both are ordinary mistakes rather
    than exotic ones:

      1. a coalesce(income, 0) or a coalesce(price, 0) slipped in later, which
         would turn 430 withheld prices and 11 suppressed incomes into ratios
         of zero or into division by zero;
      2. a ratio computed while one side is null -- which SQL renders as NULL
         today, but which a later rewrite using a CASE could get wrong.

    So the rule is stated in both directions: the ratio is null EXACTLY when
    one of its two inputs is null, and never otherwise. Same for the verdict.

    The eleven tracts without income are the near-empty ones suppressed under
    the Statistics Act. Seven of them hold no population at all. They are not
    interpolated, not borrowed from a neighbour, and not dropped.
*/

select
    affordability_key,
    median_price,
    household_income,
    price_to_income_ratio,
    meets_income_requirement,
    case
        when (median_price is null or household_income is null)
             and price_to_income_ratio is not null
            then 'ratio computed from a missing input'
        when median_price is not null and household_income is not null
             and household_income <> 0
             and price_to_income_ratio is null
            then 'ratio missing although both inputs are present'
        when (median_price is null or household_income is null)
             and meets_income_requirement is not null
            then 'verdict issued on a missing input'
        when price_to_income_ratio <= 0
            then 'ratio is zero or negative'
        when household_income = 0
            then 'an income of zero was treated as a figure'
    end as fault

from {{ ref('fact_affordability') }}

where (median_price is null or household_income is null)
      and (price_to_income_ratio is not null or meets_income_requirement is not null)
   or (median_price is not null and household_income is not null
       and household_income <> 0 and price_to_income_ratio is null)
   or price_to_income_ratio <= 0
   or household_income = 0
