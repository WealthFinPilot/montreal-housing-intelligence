/*
    The three Bank of Canada series this project reads, and nothing else.

    Three rows, declared here rather than derived with a SELECT DISTINCT over
    the staging table -- the same arrangement as dim_property_type and
    dim_household_profile. A dimension built from the fact can never disagree
    with it, so the relationship test between the two would be true by
    construction and would prove nothing. The declaration is checked against
    the source instead, in both directions, by
    tests/assert_interest_rate_series_still_match_the_source.sql.

    WHY THIS DIMENSION EARNS ITS PLACE RATHER THAN JUST RENAMING COLUMNS

    Staging carries `is_posted_rate` and `is_contracted_rate` as two booleans
    that are never true together. That is the right shape for a quality test,
    and the wrong shape for a report: the policy rate is the combination
    (false, false), which no slicer can express and no reader can guess. A
    single `rate_kind` with three stated values says the same thing in a form a
    visual can put on an axis.

    THE DISTINCTION THIS COLUMN EXISTS TO PROTECT

    posted     what a lender ADVERTISES. Not a price anyone pays.
    contracted what a borrower actually signs, on a high-ratio loan --
               exactly the loan this project models.
    policy     the Bank of Canada's own target. Neither of the above, and not
               a mortgage rate at all.

    Measured on 2026 Q2: posted stood 1.84 points above contracted. Reading one
    as the other is the same class of error as reading an asking price as a
    sale price, and it moves the required income by about 15 %.
*/

with declared as (

    /*
        series_label is the label the Bank of Canada publishes, kept so a
        figure stays traceable to its series, and so a reworded label surfaces
        as a failed build rather than as a silent mismatch.
    */

    select *
    from (
        values
            (
                'V39079', 1,
                'Target for the overnight rate',
                'policy', 'business daily', false,
                'The rate the Bank of Canada targets. Drives mortgage pricing; is not itself a mortgage rate.'
            ),
            (
                'FVI_MTG_RATE_5Y_FIX', 2,
                '5-year fixed, high-ratio mortgage (contracted)',
                'contracted', 'weekly', true,
                'A rate actually contracted on a high-ratio loan. This is the rate fact_mortgage_scenario prices with.'
            ),
            (
                'V80691335', 3,
                'Conventional mortgage: 5-year (posted)',
                'posted', 'weekly', true,
                'A rate lenders advertise. Carried for comparison only; never used to compute a payment.'
            )
    ) as t (
        series_id, sort_order, series_label,
        rate_kind, frequency, is_mortgage_rate,
        what_it_is
    )

)

select
    series_id,
    sort_order,
    series_label,
    rate_kind,
    frequency,
    is_mortgage_rate,
    what_it_is
from declared
