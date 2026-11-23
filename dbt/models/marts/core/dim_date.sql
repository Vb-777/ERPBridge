with d as (
    {{ day_spine('2022-01-01', '2026-12-31') }}
)
select date_day, extract(year from date_day) as year, extract(quarter from date_day) as quarter,
       extract(month from date_day) as month, date_trunc('month', date_day) as month_start,
       extract(dayofweek from date_day) in (0, 6) as is_weekend
from d
