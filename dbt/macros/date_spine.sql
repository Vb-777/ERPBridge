{% macro day_spine(start_date, end_date) -%}{%- if adapter is defined -%}{{ return(adapter.dispatch('day_spine')(start_date, end_date)) }}{%- else -%}{{ default__day_spine(start_date, end_date) }}{%- endif -%}{%- endmacro %}
{% macro default__day_spine(start_date, end_date) -%}
    select cast(d as date) as date_day
    from unnest(generate_series(cast('{{ start_date }}' as date), cast('{{ end_date }}' as date), interval 1 day)) as t(d)
{%- endmacro %}
{% macro snowflake__day_spine(start_date, end_date) -%}
    select dateadd(day, row_number() over (order by seq4()) - 1, cast('{{ start_date }}' as date)) as date_day
    from table(generator(rowcount => {{ (modules.datetime.date.fromisoformat(end_date) - modules.datetime.date.fromisoformat(start_date)).days + 1 }}))
{%- endmacro %}
