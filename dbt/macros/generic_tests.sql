{% test dbt_utils_free_unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n from {{ model }}
group by {{ columns | join(', ') }} having count(*) > 1
{% endtest %}

{# Validity intervals for one key must not overlap; otherwise a point-in-time join fans out. #}
{% test no_overlapping_intervals(model, key, start_col, end_col) %}
select a.{{ key }}, a.{{ start_col }}, b.{{ start_col }} as other_start
from {{ model }} a join {{ model }} b
  on a.{{ key }} = b.{{ key }} and a.{{ start_col }} < b.{{ start_col }}
 and b.{{ start_col }} <= coalesce(a.{{ end_col }}, cast('9999-12-31' as date))
{% endtest %}
