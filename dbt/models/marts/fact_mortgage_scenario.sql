{{
    config(
        materialized = 'table'
    )
}}

/*
    What it costs to buy the median property, before asking who is buying.

    One row per quarter x geography x property type -- the same 1 653 rows as
    fact_market, one for one. Everything here depends on the PRICE and on the
    rules in force, and on nothing about the household. That is why it is a
    separate table from fact_affordability: a monthly payment does not change
    when you look at it through a different household profile, and putting it
    in a table that repeats three times per profile would let a Power BI visual
    sum it three times over. Same reasoning as the two market tables of J3.5:
    make the wrong aggregation impossible, not merely detectable.

    EVERY NUMBER HERE IS DERIVED, NOT OBSERVED

    Section 41.2 of the brief. The only observed inputs are the median price
    (APCIQ) and the interest rate (Bank of Canada). Everything else is computed
    from published rules, and the rules themselves live in three seeds carrying
    their own source URL and retrieval date, never as constants in this file:

        mortgage_down_payment_bracket     what the buyer must put down
        mortgage_insurance_premium_band   what the insurance costs
        mortgage_underwriting_parameter   GDS, the qualifying rate, the rest

    THE RATE IS THE CONTRACTED ONE, AND THE POSTED ONE RIDES ALONG TO PROVE IT

    The payments below are computed from FVI_MTG_RATE_5Y_FIX, the 5-year fixed
    rate actually CONTRACTED on a high-ratio mortgage -- which is exactly the
    loan modelled here, since a buyer putting down the legal minimum is
    high-ratio by definition. It was added to the ingestion catalogue on
    2026-08-26 for that reason.

    V80691335, the POSTED 5-year rate, is carried in the same row rather than
    dropped. On 2026 Q2 the two stood at 4.29 % and 6.09 %: a 1.80-point gap
    that, run through the qualifying rate and a 25-year amortization, moves the
    required income on the median island condo by roughly a third. Keeping both
    turns that gap from a caveat somebody has to remember into a column anyone
    can subtract, and posted_minus_contract_rate_points is that column.

    CMHC states the qualifying rate on the CONTRACT rate -- "the greater of the
    contract interest rate plus 2 per cent, or 5.25 per cent" -- so stressing a
    posted rate would have applied the buffer twice.

    Both series are weekly, the market table is quarterly. The rate used is the
    MEAN of the weekly observations falling inside the quarter, per section 23
    of the brief, and the observation counts are carried so a quarter built on
    two observations cannot pass for one built on thirteen.

    HALF-YEARLY COMPOUNDING IS AN ASSUMPTION, AND IT MOVES EVERY PAYMENT

    Canadian fixed-rate mortgages are quoted half-yearly, not in advance. The
    Interest Act permits yearly OR half-yearly, so this is market practice
    rather than law, and the seed row that carries it says so
    (value_basis = 'market_convention'). The monthly rate is therefore
    (1 + annual/2)^(1/6) - 1 and not annual/12. Using the simpler form would
    overstate every payment in this table.

    INCOME REQUIRED IS A LOWER BOUND, AND THE NAME SAYS SO

    The Gross Debt Service ratio is not the mortgage payment over income. It is
    the mortgage payment PLUS property tax, PLUS heating, PLUS half of any
    condo fees, over income. This project holds none of those three: the
    sixteen municipal tax rates are not identified and condo fees exist only in
    listings, which are phase 2. So the figure below is what the mortgage
    payment alone requires -- a floor. A real applicant needs more, never less.
    The column is named income_required_lower_bound for that reason, and
    housing_burden_ratio is deliberately absent rather than approximated.
*/

with parameter as (

    select
        max(case when parameter_name = 'gds_max_ratio'
                 then parameter_value end) / 100.0            as gds_max_ratio,
        max(case when parameter_name = 'qualifying_rate_buffer'
                 then parameter_value end)                    as qualifying_rate_buffer,
        max(case when parameter_name = 'qualifying_rate_floor'
                 then parameter_value end)                    as qualifying_rate_floor,
        max(case when parameter_name = 'max_amortization_years_standard'
                 then parameter_value end)                    as amortization_years,
        max(case when parameter_name = 'interest_compounding_periods_per_year'
                 then parameter_value end)                    as compounding_per_year,
        max(case when parameter_name = 'max_insurable_price_ltv_over_80'
                 then parameter_value end)                    as max_insurable_price
    from {{ ref('mortgage_underwriting_parameter') }}

),

market as (

    select
        market_key,
        quarter_start_date,
        quarter_end_date,
        edition_year,
        edition_quarter,
        edition_label,
        geography_key,
        area_code,
        property_type_code,
        is_island_aggregate,
        median_price,
        median_price_value_status
    from {{ ref('fact_market') }}

),

quarterly_rate as (

    /*
        The mean of the weekly observations inside each quarter, for both
        mortgage series at once. A LEFT join below rather than an inner one:
        an inner join would silently drop a quarter with no observation, and
        the whole point of carrying the counts is that a thin quarter must be
        visible rather than absent.
    */
    select
        date_trunc('quarter', observation_date)::date as quarter_start_date,

        avg(rate_percent) filter (where is_contracted_rate)
            as contract_rate_percent,
        count(*) filter (where is_contracted_rate)
            as contract_rate_observation_count,

        avg(rate_percent) filter (where is_posted_rate)
            as posted_rate_percent,
        count(*) filter (where is_posted_rate)
            as posted_rate_observation_count

    from {{ ref('stg_bank_of_canada__interest_rates') }}
    where is_contracted_rate or is_posted_rate
    group by 1

),

priced as (

    select
        market.*,
        parameter.gds_max_ratio,
        parameter.amortization_years,
        parameter.compounding_per_year,
        parameter.max_insurable_price,
        quarterly_rate.contract_rate_percent,
        quarterly_rate.contract_rate_observation_count,
        quarterly_rate.posted_rate_percent,
        quarterly_rate.posted_rate_observation_count,

        /*
            The qualifying rate CMHC requires the debt service ratios to be
            computed at: the greater of the contract rate plus two points, or
            5.25 per cent. Quoted verbatim on the Home Start eligibility sheet.
        */
        greatest(
            quarterly_rate.contract_rate_percent + parameter.qualifying_rate_buffer,
            parameter.qualifying_rate_floor
        ) as qualifying_rate_percent

    from market
    cross join parameter
    left join quarterly_rate
           on quarterly_rate.quarter_start_date = market.quarter_start_date

),

down_payment as (

    /*
        The minimum down payment, summed over the tranches of the bracket the
        price falls into. Marginal for a price under 1.5 M$ -- 5 % of the first
        500 000 $ then 10 % above -- and a flat 20 % at or above 1.5 M$, which
        is a genuine cliff and not a rounding: one dollar more on the price adds
        175 000 $ to the down payment, because the property stops being
        insurable at all.
    */
    select
        priced.market_key,
        sum(
            bracket.down_payment_rate
            * (least(priced.median_price, coalesce(bracket.tranche_to_cad, priced.median_price))
               - bracket.tranche_from_cad)
        ) as minimum_down_payment
    from priced
    join {{ ref('mortgage_down_payment_bracket') }} as bracket
      on bracket.price_from_cad <= priced.median_price
     and (bracket.price_to_cad is null or priced.median_price < bracket.price_to_cad)
     and priced.median_price > bracket.tranche_from_cad
    where priced.median_price is not null
    group by 1

),

with_ltv as (

    select
        priced.*,
        down_payment.minimum_down_payment,
        priced.median_price - down_payment.minimum_down_payment as loan_before_premium,
        (priced.median_price - down_payment.minimum_down_payment)
            / nullif(priced.median_price, 0)::numeric           as loan_to_value
    from priced
    left join down_payment on down_payment.market_key = priced.market_key

),

with_premium as (

    select
        with_ltv.*,
        band.premium_rate,
        /*
            Insurance is required below a 20 % down payment. At the minimum
            down payment every row here is insured, but the condition is written
            out rather than assumed, so a future scenario at 20 % down produces
            a premium of zero instead of a wrong band lookup.
        */
        case
            when with_ltv.loan_to_value is null then null
            when with_ltv.loan_to_value <= 0.80 then 0::numeric
            else round(with_ltv.loan_before_premium * band.premium_rate, 2)
        end as insurance_premium
    from with_ltv
    left join {{ ref('mortgage_insurance_premium_band') }} as band
           on band.amortization_years = with_ltv.amortization_years
          and band.down_payment_kind = 'traditional'
          and with_ltv.loan_to_value >  band.ltv_from - 0.0001
          and with_ltv.loan_to_value <= band.ltv_to

),

with_payment as (

    select
        with_premium.*,
        with_premium.loan_before_premium + coalesce(with_premium.insurance_premium, 0)
            as loan_amount,

        /*
            The monthly rate implied by a half-yearly quoted annual rate, and
            the same conversion applied to the qualifying rate. Cast to double
            precision because power() with a fractional exponent is not exact in
            numeric anyway; the money is rounded back to cents below.
        */
        power(
            1 + (with_premium.contract_rate_percent / 100.0
                 / with_premium.compounding_per_year)::double precision,
            (with_premium.compounding_per_year / 12.0)::double precision
        ) - 1 as monthly_rate_contract,

        power(
            1 + (with_premium.qualifying_rate_percent / 100.0
                 / with_premium.compounding_per_year)::double precision,
            (with_premium.compounding_per_year / 12.0)::double precision
        ) - 1 as monthly_rate_qualifying

    from with_premium

),

computed as (

    select
        with_payment.*,
        (with_payment.amortization_years * 12)::int as payment_count,

        round((
            with_payment.loan_amount::double precision * with_payment.monthly_rate_contract
            / (1 - power(1 + with_payment.monthly_rate_contract,
                         -(with_payment.amortization_years * 12)::double precision))
        )::numeric, 2) as monthly_payment_contract_rate,

        round((
            with_payment.loan_amount::double precision * with_payment.monthly_rate_qualifying
            / (1 - power(1 + with_payment.monthly_rate_qualifying,
                         -(with_payment.amortization_years * 12)::double precision))
        )::numeric, 2) as monthly_payment_qualifying_rate

    from with_payment

)

select
    market_key                                              as mortgage_scenario_key,
    quarter_start_date,
    quarter_end_date,
    edition_year,
    edition_quarter,
    edition_label,
    geography_key,
    area_code,
    property_type_code,
    is_island_aggregate,

    -- The observed inputs, carried so a reader never has to join back.
    median_price,
    median_price_value_status,
    contract_rate_percent,
    contract_rate_observation_count,
    posted_rate_percent,
    posted_rate_observation_count,
    round(posted_rate_percent - contract_rate_percent, 4)
                                                            as posted_minus_contract_rate_points,
    'contracted_high_ratio_5y_fixed'                        as rate_basis,

    -- The scenario this row describes, stated rather than implied.
    'minimum_down_payment'                                  as down_payment_scenario,
    amortization_years,
    qualifying_rate_percent,

    -- The derived money.
    minimum_down_payment,
    loan_to_value,
    premium_rate                                            as insurance_premium_rate,
    insurance_premium,
    loan_amount,
    monthly_payment_contract_rate,
    monthly_payment_qualifying_rate,

    /*
        What the qualifying payment alone consumes of a 39 % gross debt service
        allowance. A LOWER BOUND: property tax, heating and half of any condo
        fees also count against that 39 % and this project holds none of them.
    */
    round(monthly_payment_qualifying_rate * 12 / gds_max_ratio, 2)
                                                            as income_required_lower_bound,
    'mortgage_payment_only_at_gds_39'                       as income_required_basis,

    case
        when median_price is null then 'no_price_published'
        when median_price >= max_insurable_price then 'not_insurable'
        when loan_to_value > 0.80 then 'insured'
        else 'uninsured'
    end                                                     as insurance_status

from computed
