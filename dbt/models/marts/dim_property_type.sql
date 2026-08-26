/*
    The three property categories APCIQ reports on, and nothing else.

    Three rows. It would be tempting to derive them from the fact table with a
    SELECT DISTINCT and save the typing, and that is exactly what this file
    refuses to do: a dimension built from the fact can never disagree with it,
    so the relationship test between the two would be true by construction and
    would prove nothing.

    Declared here instead, and checked against the source by
    tests/assert_property_types_still_match_the_source.sql. That is the same
    arrangement as the Bank of Canada series labels, which are deliberately
    duplicated between series.py and the staging model so that a new series
    added on one side and not the other fails the build loudly.

    WHAT THESE CATEGORIES ARE NOT

    They are APCIQ's categories, not a property classification of this
    project's own. A "plex" here is what APCIQ counts as a plex -- a building
    of 2 to 5 dwellings, as its own label states. The municipal assessment roll
    cuts the housing stock differently, and joining the two on a category name
    would be the sort of resemblance-based join this project refuses.

    Section 5 of the brief also wants condo configurations (studio, 1 bedroom,
    2 bedrooms). Those live in listings, which is phase 2. Nothing in the
    Baromètre goes below the three categories below.
*/

with declared as (

    /*
        source_label_fr is the label as APCIQ prints it in Tableau 2, kept for
        two reasons: it is what makes a figure traceable back to its page, and
        it is what the test compares against, so a wording change in a future
        edition surfaces as a failed build rather than as a silent mismatch.
    */

    select *
    from (
        values
            ('single_family', 1, 'Single-family',        'Unifamiliale'),
            ('condo',         2, 'Condominium',          'Copropriété'),
            ('plex',          3, 'Plex (2 to 5 units)',  'Plex (2 à 5 logements)')
    ) as t (property_type_code, sort_order, name_en, source_label_fr)

)

select
    property_type_code,
    sort_order,
    name_en,
    source_label_fr
from declared
