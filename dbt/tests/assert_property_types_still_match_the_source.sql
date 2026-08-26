/*
    dim_property_type says the same three things the Baromètre says.

    The dimension declares its three rows rather than deriving them from the
    fact, so that the relationship test between them proves something. This is
    the other half of that arrangement: the declaration is checked against the
    source, in both directions.

        a category in the source with no row here     APCIQ added one, or the
                                                      parser renamed one
        a row here matching no category in the source the declaration has gone
                                                      stale

    The labels are compared too, not only the codes. The days-on-market row was
    called « Délai de vente moyen (jours) » in 2019 and « Moyenne de jours sur
    le marché » in 2026: the source rewords itself, and a label kept for
    traceability that no longer matches the page traces nothing.

    Same arrangement as the Bank of Canada series labels, deliberately
    duplicated between series.py and the staging model so that adding a series
    on one side only fails the build.
*/

with declared as (

    select property_type_code, source_label_fr
    from {{ ref('dim_property_type') }}

),

printed as (

    select distinct
        property_category                          as property_type_code,
        source_category_label                      as source_label_fr
    from {{ ref('stg_apciq__barometer_statistics') }}

),

undeclared as (

    select
        'category printed by the source, not declared' as direction,
        printed.property_type_code,
        printed.source_label_fr
    from printed
    left join declared using (property_type_code, source_label_fr)
    where declared.property_type_code is null

),

stale as (

    select
        'declared category no longer printed as declared' as direction,
        declared.property_type_code,
        declared.source_label_fr
    from declared
    left join printed using (property_type_code, source_label_fr)
    where printed.property_type_code is null

)

select * from undeclared
union all
select * from stale
