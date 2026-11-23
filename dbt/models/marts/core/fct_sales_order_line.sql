{{ config(materialized='incremental', unique_key='order_line_key', incremental_strategy='delete+insert',
          on_schema_change='fail') }}
-- One row per valid order line from both ERPs, in USD, with the standard cost in force on the
-- order date (point-in-time). Grain is enforced by a uniqueness test on order_line_key.
with a as (
    select 'A-' || cast(l.order_id as varchar) || '-' || cast(l.order_line_id as varchar) as order_line_key,
           'A' as source_system, l.order_id, l.order_line_id, l.order_date, k.customer_key, l.product_id as product_key,
           l.quantity, 'USD' as currency_code, l.unit_price as unit_price_local, cast(1 as numeric(18, 6)) as usd_to_currency,
           cast(round(l.line_total_usd, 2) as numeric(18, 2)) as net_amount_usd, l._loaded_at
    from {{ ref('stg_a__sales_order_lines') }} l
    inner join {{ ref('int_customer_xref') }} k on k.source_system = 'A' and k.source_customer_id = cast(l.customer_id as varchar)
),
b as (
    select 'B-' || cast(l.order_id as varchar) || '-' || cast(l.order_line_id as varchar),
           'B', l.order_id, l.order_line_id, l.order_date, k.customer_key, coalesce(p.product_id, -1),
           l.quantity, l.currency_code, l.unit_price_local, l.usd_to_currency,
           cast(round(l.quantity * l.unit_price_local / l.usd_to_currency, 2) as numeric(18, 2)), l._loaded_at
    from {{ ref('int_b_order_lines_validated') }} l
    inner join {{ ref('int_customer_xref') }} k on k.source_system = 'B' and k.source_customer_id = cast(l.cust_num as varchar)
    left join {{ ref('stg_b__part_xref') }} x on x.part_num = l.part_num
    left join {{ ref('stg_a__products') }} p on p.product_number = x.product_number
    where l.reject_reason is null
),
lines as (
    select * from a
    union all
    select * from b
),
cost as (
    -- in-force interval first; if the ERP's history has a gap, the latest earlier cost, flagged
    select l.order_line_key, h.standard_cost,
           case when l.order_date <= coalesce(h.valid_to, cast('9999-12-31' as date)) then 'in_force' else 'latest_prior' end as cost_basis,
           row_number() over (partition by l.order_line_key
                              order by case when l.order_date <= coalesce(h.valid_to, cast('9999-12-31' as date)) then 0 else 1 end,
                                       h.valid_from desc) as rn
    from lines l
    inner join {{ ref('stg_a__product_cost_history') }} h on h.product_id = l.product_key and h.valid_from <= l.order_date
)
select
    l.order_line_key, l.source_system, l.order_id, l.order_line_id, l.order_date, l.customer_key, l.product_key,
    l.quantity, l.currency_code, cast(l.unit_price_local as numeric(18, 4)) as unit_price_local,
    cast(l.usd_to_currency as numeric(18, 6)) as usd_to_currency, l.net_amount_usd,
    cast(coalesce(c.standard_cost, p.current_standard_cost) as numeric(18, 4)) as unit_standard_cost_usd,
    coalesce(c.cost_basis, case when l.product_key = -1 then 'unmapped_product' else 'product_master' end) as cost_basis,
    cast(l.net_amount_usd - l.quantity * coalesce(c.standard_cost, p.current_standard_cost) as numeric(18, 2)) as gross_margin_usd,
    cast(l._loaded_at as timestamp) as loaded_at
from lines l
left join cost c on c.order_line_key = l.order_line_key and c.rn = 1
left join {{ ref('stg_a__products') }} p on p.product_id = l.product_key
{% if is_incremental() %}
where cast(l._loaded_at as timestamp) > (select max(t.loaded_at) from {{ this }} as t)
{% endif %}
