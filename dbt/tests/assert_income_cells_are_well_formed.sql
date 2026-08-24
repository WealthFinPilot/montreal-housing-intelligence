/*
    Three things must hold of every income cell, and each one guards against a
    different way of losing the distinction the source went to the trouble of
    making.

    1. THE CUBE IS COMPLETE

       The published table crosses 7 household sizes with 11 household types,
       so every geography carries exactly 77 rows -- measured over all 1 005
       geographies of the metropolitan area. The primary key is the three
       published labels, so a re-worded dimension member would INSERT a row
       rather than update one, leaving a tract with 78. Nothing else here would
       notice: every individual value would still be plausible.

    2. A VALUE APPEARS ONLY WHERE THE SOURCE PUBLISHED ONE

       'x' means a real number exists and the Statistics Act forbids printing
       it; '...' means the question does not arise. Both must arrive as NULL
       with their reason intact. A number sitting beside a non-published status
       means the value and symbol columns have drifted apart -- which is
       exactly what reading this file with a dictionary reader would cause,
       since six of its columns are named `Symbol`.

    3. NO CELL IS SILENTLY EMPTY

       A status of 'published' with a NULL value would mean the source printed
       nothing and no symbol at all. That has never been observed, and if it
       starts happening it is a change worth stopping for rather than a NULL to
       absorb.

    A returned row is a failure.
*/

with cube_shape as (

    select
        ct_uid,
        count(*) as rows_for_this_tract
    from {{ ref('stg_statcan__household_income') }}
    group by ct_uid
    having count(*) <> 77

),

cells as (

    select * from {{ ref('stg_statcan__household_income') }}

),

failures as (

    select
        'a tract does not carry 77 rows'          as failure,
        ct_uid                                    as ct_uid,
        cast(rows_for_this_tract as text)         as detail
    from cube_shape

    union all

    select
        'a value is present where the source published none',
        ct_uid,
        household_size || ' / ' || household_type || ' -> ' ||
        median_total_income_2020_status
    from cells
    where median_total_income_2020 is not null
      and median_total_income_2020_status <> 'published'

    union all

    select
        'a value is present where the source published none (after-tax)',
        ct_uid,
        household_size || ' / ' || household_type || ' -> ' ||
        median_aftertax_income_2020_status
    from cells
    where median_aftertax_income_2020 is not null
      and median_aftertax_income_2020_status <> 'published'

    union all

    select
        'the source published a value and none arrived',
        ct_uid,
        household_size || ' / ' || household_type
    from cells
    where median_total_income_2020_status = 'published'
      and median_total_income_2020 is null

    union all

    /*
        4. NO PLACEHOLDER ZERO GOT THROUGH

        The source does not print an empty cell for "not applicable". It
        prints the digit 0, beside the '...' symbol -- 36 808 times in the
        Montréal metropolitan area alone, measured on 2026-08-24. A parser
        that ignored the symbol column would not produce NULLs somebody might
        question; it would produce median household incomes of zero dollars
        that average quietly into every figure downstream.

        A median household income is never zero: a tract with no households
        has no row published, and one with households has a positive median.
        So a zero here can only mean a placeholder leaked past the symbol.
    */
    select
        'a placeholder zero reached the model -- the symbol column was ignored',
        ct_uid,
        household_size || ' / ' || household_type
    from cells
    where median_total_income_2020 = 0
       or median_aftertax_income_2020 = 0
       or median_total_income_2015 = 0
       or median_aftertax_income_2015 = 0

)

select * from failures
