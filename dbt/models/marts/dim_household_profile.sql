/*
    The three household profiles the affordability model reports on.

    Three rows, declared here and not derived with a SELECT DISTINCT over the
    census table -- same arrangement as dim_property_type, and for the same
    reason: a dimension built from its own fact can never disagree with it, so
    the relationship test would be true by construction and would prove
    nothing. tests/assert_household_profiles_still_match_the_source.sql is what
    checks these labels against what Statistics Canada actually publishes.

    WHY THREE, AND WHY THESE THREE

    Table 98100058 crosses 7 household sizes with 11 household types, so 77
    combinations exist for every census tract. Measured on 2026-08-26 across
    the 541 Island tracts, coverage runs from 530 published tracts down to 0:
    twenty of the seventy-seven have fewer than half their tracts published,
    and thirteen have none at all. Picking three well-covered profiles is
    therefore not a convenience, it is what keeps a dashboard from showing
    holes it cannot explain. All three below sit at 530 of 541, the missing
    eleven being the near-empty tracts suppressed under the Statistics Act.

    They are also the three a first-time buyer can actually be:

        total         the median household of the tract, whatever its shape.
                      The reference figure, and the one that is NOT a
                      first-time buyer: it includes owners who bought twenty
                      years ago.
        one_person    a single buyer.
        couple        two people, with or without children.

    WHAT A PROFILE IS NOT

    It is not a filter on who may buy. It is the income denominator of the
    ratio, and nothing else. Section 41.2 of the brief: the price is observed,
    the income is observed, the pairing of one with the other is the
    assumption -- and it is the profile column that names which pairing.
*/

with declared as (

    /*
        household_size_label and household_type_label are the labels exactly as
        Statistics Canada prints them, en dash included. They are what the test
        compares against, so a relabelled dimension in a future census surfaces
        as a failed build instead of as three empty profiles.
    */

    select *
    from (
        values
            (
                'total', 1, 'All households',
                'Total - Households by household size',
                'Total – Household type including census family structure'
            ),
            (
                'one_person', 2, 'One person',
                '1 person',
                'Non-census family households'
            ),
            (
                'couple', 3, 'Couple, two persons',
                '2 persons',
                'One couple, with or without children in their census family'
            )
    ) as t (
        household_profile_code,
        sort_order,
        name_en,
        household_size_label,
        household_type_label
    )

)

select
    household_profile_code,
    sort_order,
    name_en,
    household_size_label,
    household_type_label
from declared
