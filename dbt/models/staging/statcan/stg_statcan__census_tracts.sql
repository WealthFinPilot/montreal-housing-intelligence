{{
    config(
        materialized = 'view'
    )
}}

/*
    The 541 census tracts of the Island of Montréal, one row each, with the
    municipality they belong to and a real PostGIS geometry.

    Built by rolling 13 844 dissemination blocks up to their tract. The raw
    layer holds the blocks because of what they carry -- population, dwellings
    and a representative point -- and because a tract will one day have to be
    split between two APCIQ sectors, which needs a weight this grain provides
    and the tract grain does not.

    WHY THE MUNICIPALITY IS READ, NOT COMPUTED

    Every attribute below that describes a whole tract is aggregated with
    max(), which is only legitimate because those attributes are constant
    across the blocks of a tract. That is not an assumption: it was measured on
    2026-08-24, and it is enforced permanently by the singular test
    tests/assert_census_tract_nests_in_one_municipality.sql. If Statistics
    Canada ever redraws a tract across a municipal boundary, the build fails
    instead of silently picking whichever municipality sorted highest.

    The same measurement is what removed the spatial join this model was
    originally expected to need. Membership comes from a published code; the
    geometry below is for drawing and measuring, never for deciding where a
    tract belongs. Two files do not agree on where the shoreline is -- see
    docs/geography.md section 6.

    WHY THERE IS NO BOROUGH COLUMN

    Because nothing published carries one. A census tract nests inside a
    municipality, and Ville de Montréal holds 485 of the 541, but boroughs are
    a municipal creation and APCIQ sectors an association's: neither is a
    Statistics Canada geography, so no attribute file will ever state them. A
    NULL would be honest and a guess would not, so the column simply does not
    exist yet. Attaching tracts to boroughs and to APCIQ sectors is a genuine
    spatial problem, and it belongs to J3.4.
*/

with blocks as (

    select *
    from {{ source('statcan', 'statcan_geographic_attribute') }}
    where ct_uid <> ''

),

boundaries as (

    select *
    from {{ source('statcan', 'statcan_census_tract_boundary') }}

),

aggregated as (

    select
        ct_uid,

        max(ct_dguid)   as ct_dguid,
        max(ct_name)    as ct_name,
        max(cma_uid)    as cma_uid,
        max(cma_name)   as cma_name,

        /*
            The municipality, as a published census subdivision code, and the
            same code in the nomenclature the rest of this project keys on.

            csd_uid is province (24) + census division (66) + subdivision, so
            dropping the province prefix yields the MAMH municipal code that
            dim_geography, the assessment roll and the city's boundary file all
            use. Verified for all 16 Island municipalities on 2026-08-24, name
            by name -- not inferred from the shape of the number.
        */
        max(csd_uid)                as csd_uid,
        max(substr(csd_uid, 3))     as municipality_code,
        max(csd_name)               as csd_name,
        max(cd_uid)                 as cd_uid,

        -- Counts, from text, where a bad character now fails loudly.
        sum(nullif(trim(population_2021), '')::int)              as population_2021,
        sum(nullif(trim(total_dwellings_2021), '')::int)         as dwellings_2021,
        sum(nullif(trim(usual_resident_dwellings_2021), '')::int)
                                                                 as occupied_dwellings_2021,

        -- Land area as Statistics Canada states it, summed from the blocks.
        -- Kept beside the measured area below so one can check the other.
        round(sum(nullif(trim(land_area_km2), '')::numeric), 4)  as published_land_area_km2,

        count(*)                        as block_count,
        count(distinct da_uid)          as dissemination_area_count,

        -- Guarded by a singular test. Selected rather than asserted here so
        -- the test can point at the offending tract.
        count(distinct csd_uid)         as municipality_count,

        min(first_seen_at)              as first_seen_at,
        max(updated_at)                 as updated_at

    from blocks
    group by ct_uid

),

with_geometry as (

    select
        aggregated.*,

        /*
            The source ships EPSG:3347, NAD83 / Statistics Canada Lambert, in
            metres. It is reprojected here to 4326 so that every geometry in
            this project lives in one system -- mixing them is the trap that
            already cost this repository a day.

            The SRID is stated by the raw row rather than assumed, and 3347 was
            proven rather than recognised by name: the attribute file publishes
            the same representative point in both Lambert and latitude and
            longitude, and reprojecting one lands on the other within 5 cm.
        */
        st_transform(
            st_geomfromtext(boundaries.geometry_wkt, boundaries.source_srid),
            4326
        ) as geometry,

        boundaries.source_srid as source_srid

    from aggregated
    left join boundaries using (ct_uid)

),

measured as (

    select
        *,

        /*
            Measured on the ellipsoid, in square kilometres.

            NOT with ST_Area on the source projection. EPSG:3347 is a Lambert
            CONFORMAL conic: it preserves angles, not areas, and this far south
            of its standard parallels it overstates every area by 3.3 % while
            returning a perfectly plausible number in metres. Measured against
            the published land areas on 2026-08-24 -- docs/geography.md
            section 6.

            The residual quarter of a percent against published_land_area_km2
            is not error: a polygon holds a little water that a LAND area
            excludes.
        */
        round((st_area(geometry::geography) / 1000000.0)::numeric, 4) as area_km2

    from with_geometry

)

select * from measured
