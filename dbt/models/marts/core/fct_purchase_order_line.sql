select
    purchase_order_id, purchase_order_line_id, vendor_id, vendor_name, product_id as product_key,
    order_date, due_date, ship_date, quantity_ordered, quantity_received, quantity_rejected,
    unit_price_usd, cast(line_total_usd as numeric(18, 2)) as line_total_usd,
    ship_date <= due_date as shipped_by_due_date,
    case when quantity_received > 0 then cast(quantity_rejected as double) / quantity_received end as reject_rate
from {{ ref('stg_a__purchase_order_lines') }}
