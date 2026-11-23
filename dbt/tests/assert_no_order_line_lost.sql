-- Every source line is either in the fact or in quarantine: nothing silently disappears.
with src as (
    select 'A' as s, count(*) as n from {{ ref('stg_a__sales_order_lines') }}
    union all select 'B', count(*) from {{ ref('stg_b__order_lines') }}
),
out as (
    select source_system as s, count(*) as n from {{ ref('fct_sales_order_line') }} group by 1
    union all select 'B', count(*) from {{ ref('dq_quarantine') }}
)
select src.s, src.n as source_lines, sum(out.n) as accounted
from src join out on out.s = src.s group by src.s, src.n having src.n <> sum(out.n)
