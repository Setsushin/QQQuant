{#
  Use custom schema names verbatim (raw, marts, ...) instead of dbt's default
  "<target>_<custom>" concatenation, so source/seed schemas match ingestion.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
