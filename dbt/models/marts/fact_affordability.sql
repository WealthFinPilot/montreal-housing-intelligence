{{
    config(
        materialized = 'table'
    )
}}

/*
    Can this household buy in this tract, and how far off is it.

    One row per quarter x census tract x property type x household profile.
    141 462 of them: 542 tract-sector pairs x 29 quarters x 3 categories x 3
    profiles. That number is not an estimate -- it is the product of four
    counts that each have their own test upstream, which is what lets
    assert_fact_affordability_is_complete.sql assert it exactly.

    THE ONE ASSUMPTION THIS TABLE IS BUILT ON, NAMED IN A COLUMN

    The price is published for an APCIQ SECTOR. The income is published for a
    CENSUS TRACT. They do not share a grain, and the tempting move -- average
    the forty tract incomes of a sector into one sector income -- is arithmetic
    nonsense: eighteen medians do not average into a nineteenth, weighted or
    not. This model does the opposite. It carries the sector price DOWN to each
    of its tracts and computes the ratio there, which turns the problem into a
    single assumption that can be stated, carried on every row, and switched
    off by a reader who rejects it: price_basis says
    'apciq_sector_price_applied_to_tract' on all 141 462 rows.

    Measured on 2026-08-26, before the model was written, this is not a matter
    of taste. 58.4 % of the variance of tract median incomes on the island is
    WITHIN an APCIQ sector, not between sectors. Collapsing to the sector would
    throw away the larger half of the signal, and would misstate a typical
    tract by 10.6 % -- 37.6 % at the ninth decile, and more than 20 % on 27.1 %
    of tracts.

    WHAT THE RATIO DIVIDES, AND WHY IT IS NOT AN OBSERVATION

    A 2026 sale price by a 2020 census income, in 2020 constant dollars. Six
    years apart at the far end of the series. Nothing here indexes one to the
    other -- section 41.1 of the brief forbids inventing the missing years --
    so the gap is carried as price_year_minus_income_year and the income year
    is on every row. A reader dividing 2026 by 2020 does it knowingly.

    The income is TOTAL income, before tax, decided on 2026-08-26. That is the
    base a lender's gross debt service rule looks at, which is what makes it
    comparable to income_required_lower_bound. After-tax income answers a
    different question -- what a household can actually pay each month -- and is
    loaded in staging, unused here on purpose.

    THREE PROFILES, NOT SEVENTY-SEVEN

    The census publishes 77 household size x type combinations per tract. On
    the island their coverage runs from 530 published tracts down to 0, and 20
    of the 77 have fewer than half. dim_household_profile keeps the three that
    a first-time buyer can be, all three at 530 of 541. The missing eleven are
    the near-empty tracts suppressed under the Statistics Act; they keep their
    rows, with a status, and are never filled in.

    WHAT MUST NOT BE SUMMED

    income_required_lower_bound comes from fact_mortgage_scenario and depends
    only on the price, so it REPEATS ACROSS THE THREE PROFILES. It is carried
    here anyway, because the whole point of the table is the gap between it and
    a household income, and a cross-grain join in Power BI to fetch one scalar
    would be worse. It is non-additive: average it, take its minimum, never sum
    it. Everything else in the table is profile-specific.
*/

with bridge as (

    /*
        Rows of weight zero are excluded. There is one: a tract that genuinely
        reaches into a second sector over ground where nobody lives (J3.4). Its
        tract is already present through its majority row, and keeping the
        empty one would pair the tract's income with a second sector's price
        for a population of nobody.
    */
    select
        census_tract_geography_key,
        ct_uid,
        apciq_geography_key,
        apciq_sector_number,
        population_weight,
        weight_basis,
        assignment_method,
        neighbourhood_names,
        tract_is_shared,
        tract_population
    from {{ ref('bridge_census_tract_apciq_sector') }}
    where population_weight > 0

),

scenario as (

    /*
        The sectors only. The island row is a total of the eighteen, not a
        nineteenth sector, and no census tract belongs to it.
    */
    select
        mortgage_scenario_key,
        quarter_start_date,
        quarter_end_date,
        edition_year,
        edition_quarter,
        edition_label,
        geography_key,
        area_code,
        property_type_code,
        median_price,
        median_price_value_status,
        contract_rate_percent,
        qualifying_rate_percent,
        amortization_years,
        monthly_payment_qualifying_rate,
        income_required_lower_bound,
        income_required_basis,
        insurance_status
    from {{ ref('fact_mortgage_scenario') }}
    where not is_island_aggregate

),

profile as (

    select
        household_profile_code,
        sort_order,
        name_en,
        household_size_label,
        household_type_label
    from {{ ref('dim_household_profile') }}

),

income as (

    /*
        The 2021 census release, which publishes income for the 2020 and 2015
        years. Only 2020 is used; the status column is what distinguishes a
        suppressed figure from an inapplicable one, and neither is a zero.
    */
    select
        ct_uid,
        household_size,
        household_type,
        median_total_income_2020,
        median_total_income_2020_status,
        households_2021,
        households_2021_status
    from {{ ref('stg_statcan__household_income') }}
    where census_year = 2021

),

joined as (

    select
        bridge.census_tract_geography_key,
        bridge.ct_uid,
        bridge.apciq_geography_key,
        bridge.apciq_sector_number,
        bridge.population_weight,
        bridge.weight_basis,
        bridge.assignment_method,
        bridge.neighbourhood_names,
        bridge.tract_is_shared,
        bridge.tract_population,

        scenario.quarter_start_date,
        scenario.quarter_end_date,
        scenario.edition_year,
        scenario.edition_quarter,
        scenario.edition_label,
        scenario.area_code,
        scenario.property_type_code,
        scenario.median_price,
        scenario.median_price_value_status,
        scenario.contract_rate_percent,
        scenario.qualifying_rate_percent,
        scenario.amortization_years,
        scenario.monthly_payment_qualifying_rate,
        scenario.income_required_lower_bound,
        scenario.income_required_basis,
        scenario.insurance_status,

        profile.household_profile_code,
        profile.sort_order as household_profile_sort_order,

        income.median_total_income_2020        as household_income,
        income.median_total_income_2020_status as household_income_status,
        income.households_2021                 as household_count,
        income.households_2021_status          as household_count_status

    from bridge
    join scenario on scenario.geography_key = bridge.apciq_geography_key
    cross join profile
    /*
        LEFT, and it matters. Eleven tracts have no published income at all,
        and dropping them would quietly shrink the island by eleven tracts in
        every affordability visual. They stay, with a status and a null.
    */
    left join income
           on income.ct_uid = bridge.ct_uid
          and income.household_size = profile.household_size_label
          and income.household_type = profile.household_type_label

)

select
    /*
        A single concatenated key, the same shape as market_key in
        fact_market, so that the grain can be asserted with the built-in
        unique test rather than by adding a package for one assertion. The
        sector is part of it: the one genuinely shared tract appears twice in
        a quarter, once per sector, and that is a fact rather than a duplicate.
    */
    quarter_start_date || '|' || census_tract_geography_key || '|'
        || apciq_geography_key || '|' || property_type_code || '|'
        || household_profile_code                           as affordability_key,

    -- Grain.
    quarter_start_date,
    quarter_end_date,
    edition_year,
    edition_quarter,
    edition_label,
    census_tract_geography_key,
    ct_uid,
    property_type_code,
    household_profile_code,
    household_profile_sort_order,

    -- Where the price came from, and how the tract was placed in that sector.
    apciq_geography_key,
    apciq_sector_number,
    area_code,
    assignment_method,
    neighbourhood_names,
    tract_is_shared,
    population_weight,
    weight_basis,
    tract_population,

    -- Observed: the price, published for the sector.
    median_price,
    median_price_value_status,
    'apciq_sector_price_applied_to_tract'                   as price_basis,

    -- Observed: the income, published for the tract.
    household_income,
    household_income_status,
    household_count,
    household_count_status,
    2020                                                    as income_year,
    edition_year - 2020                                     as price_year_minus_income_year,

    -- Derived, and repeated across the three profiles. Never sum these two.
    contract_rate_percent,
    qualifying_rate_percent,
    amortization_years,
    monthly_payment_qualifying_rate,
    income_required_lower_bound,
    income_required_basis,
    insurance_status,

    /*
        The three profile-specific measures. Each is null whenever either side
        is null, which is the whole point: a missing income produces a missing
        ratio, never a ratio computed against a zero.
    */
    round(median_price / nullif(household_income, 0), 3)    as price_to_income_ratio,

    round(income_required_lower_bound - household_income, 2)
                                                            as income_shortfall,

    case
        when median_price is null or household_income is null then null
        else household_income >= income_required_lower_bound
    end                                                     as meets_income_requirement

from joined
