{#
  Post-hook for core marts. Columns whose YAML has meta: {pii: true} are masked for everyone
  without the PII_READER role.
  Snowflake: a column masking policy (governance.pii_string) is attached to each such column.
  DuckDB (local/CI, no roles): a <model>_masked view is created for BI tools to read instead.
#}
{% macro apply_pii_masking() %}
    {%- if not execute -%}{{ return('') }}{%- endif -%}
    {%- set pii = [] -%}
    {%- for name, col in model.columns.items() -%}
        {%- if col.meta.get('pii') -%}{%- do pii.append(name) -%}{%- endif -%}
    {%- endfor -%}
    {%- if pii | length == 0 -%}{{ return('select 1') }}{%- endif -%}
    {{ return(adapter.dispatch('apply_pii_masking')(pii)) }}
{% endmacro %}

{% macro default__apply_pii_masking(pii) -%}
    create or replace view {{ this.schema }}.{{ this.identifier }}_masked as
    select * replace ({% for c in pii %}case when {{ c }} is null then null else '***MASKED***' end as {{ c }}{% if not loop.last %}, {% endif %}{% endfor %})
    from {{ this }}
{%- endmacro %}

{% macro snowflake__apply_pii_masking(pii) -%}
    begin
        create schema if not exists {{ this.database }}.governance;
        create masking policy if not exists {{ this.database }}.governance.pii_string as (val string) returns string ->
            case when is_role_in_session('PII_READER') then val when val is null then null else '***MASKED***' end;
        {% for c in pii -%}
        alter table {{ this }} modify column {{ c }} set masking policy {{ this.database }}.governance.pii_string force;
        {% endfor -%}
    end
{%- endmacro %}
