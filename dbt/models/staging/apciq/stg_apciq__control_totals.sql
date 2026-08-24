{{
    config(
        materialized = 'view'
    )
}}

/*
    The verdict of every control run while reading an APCIQ edition.

    One row per reconciliation: what APCIQ printed as a total, what its own
    parts add up to, and how far apart the two are allowed to be. 47 rows per
    edition -- 19 pages x 2 metrics, plus 3 categories x 3 metric/period pairs
    across pages.

    WHY THIS MODEL EXISTS AT ALL

    Because "the source is wrong here" has to be something a query can answer.
    Before this table, it was a sentence in a commit message and an edition
    that refused to load.

    THE TWO CONTROLS DO NOT ANSWER THE SAME QUESTION

        page_table1_vs_table2   Did WE read this page correctly? Tableau 1 and
                                Tableau 2 print the same quarter for the same
                                area a few centimetres apart, and the parser
                                reads both with the same column anchors.

        sectors_vs_island       Is APCIQ coherent from one page to the next?
                                The 18 sector pages against the island page.

    Keeping them apart is what lets a reader tell a parsing bug from a
    publisher's defect. On 2021 Q4 both fail on active listings while both
    pass on sales -- same pages, same anchors, same code. That asymmetry is
    the evidence, and it is why the edition is loaded rather than refused.

    HOW A MODEL DOWNSTREAM SHOULD USE THIS

    Join on edition and metric, and honour is_reconciled. A figure whose
    control failed is not a wrong figure -- it is a figure the source does not
    corroborate, which is a different and more honest thing to say. What it
    must never be is presented without saying so.
*/

with source as (

    select * from {{ source('apciq', 'apciq_control_total') }}

)

select
    edition_year,
    edition_quarter,
    edition_year || ' Q' || edition_quarter as edition_label,
    make_date(edition_year, 3 * (edition_quarter - 1) + 1, 1) as quarter_start_date,

    control_code,
    scope,
    property_category,
    metric_code,
    period_code,

    published_total,
    computed_total,
    computed_total - published_total as difference,
    tolerance,

    /*
        The verdict, computed here rather than stored, so that it can never
        contradict the three numbers it is drawn from. abs() because a
        tolerance is a distance: a total that overshoots by 10 is as wrong as
        one that falls short by 10.
    */
    abs(computed_total - published_total) <= tolerance as is_reconciled,

    /*
        The size of the gap relative to what was published. A difference of +8
        means nothing on a total of 2 850 and everything on a total of 24, and
        a reader comparing editions needs the ratio, not the count. Null
        rather than a division by zero on the rare total of zero -- there is no
        such thing as a percentage of nothing.
    */
    case when published_total <> 0
         then round(100.0 * (computed_total - published_total) / published_total, 1)
    end as difference_percent,

    source_page,
    first_seen_at,
    updated_at

from source
