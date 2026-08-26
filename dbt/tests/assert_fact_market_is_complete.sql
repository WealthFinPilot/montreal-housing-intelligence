/*
    Every quarter x geography x property type exists, once.

    The Baromètre prints a full grid: 19 areas x 3 categories x 5 metrics on
    every edition, with no blank row -- a cell APCIQ cannot publish is printed
    as '**' or '-', never omitted. So the fact table must be a full grid too,
    and a hole in it can only come from the pivot or from an edition that
    failed to load.

    WHERE THE EXPECTED GRID COMES FROM, AND WHY NOT FROM THE FACT ITSELF

    The quarters come from the source, because the archive grows by one every
    three months and hard-coding 29 would turn a normal ingestion into a failed
    build. The geographies come from dim_geography instead -- the island and
    its 18 sectors, as the geography model declares them -- so that a whole
    area missing from an edition is caught. Taking them from the same staging
    view would make the test agree with whatever was loaded.

    A returned row is a failure: either a combination the source has and the
    fact does not, or one the fact invented.
*/

with quarters as (

    select distinct period_start_date as quarter_start_date
    from {{ ref('stg_apciq__barometer_statistics') }}
    where period_code = 'quarter'

),

geographies as (

    select geography_key
    from {{ ref('dim_geography') }}
    where geography_type in ('island', 'apciq_sector')

),

expected as (

    select
        quarters.quarter_start_date,
        geographies.geography_key,
        property_types.property_type_code
    from quarters
    cross join geographies
    cross join {{ ref('dim_property_type') }} as property_types

),

actual as (

    select quarter_start_date, geography_key, property_type_code
    from {{ ref('fact_market') }}

),

missing as (

    select
        'expected combination absent from fact_market' as direction,
        expected.quarter_start_date,
        expected.geography_key,
        expected.property_type_code
    from expected
    left join actual using (quarter_start_date, geography_key, property_type_code)
    where actual.geography_key is null

),

unexpected as (

    select
        'fact_market row matching no expected combination' as direction,
        actual.quarter_start_date,
        actual.geography_key,
        actual.property_type_code
    from actual
    left join expected using (quarter_start_date, geography_key, property_type_code)
    where expected.geography_key is null

)

select * from missing
union all
select * from unexpected
