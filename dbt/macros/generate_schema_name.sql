{#
    Put a model in the schema it names, and nowhere else.

    dbt ships a deliberately cautious default: when a model asks for schema
    "staging" while the connection targets schema "staging", it builds
    "staging_staging". That default exists so several developers can share one
    database without overwriting each other.

    This project has one developer and three schemas that already mean
    something -- raw, staging, marts -- created by sql/bootstrap. A model that
    says "staging" must land in "staging". Hence this override.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
