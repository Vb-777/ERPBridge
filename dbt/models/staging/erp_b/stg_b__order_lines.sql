-- ERP B order lines with header fields, typed. Validity is judged downstream, not here,
-- so that invalid rows can be counted and quarantined instead of silently disappearing.
select
    cast(d.OrderNum as integer) as order_id,
    cast(d.OrderLine as integer) as order_line_id,
    try_cast(h.OrderDate as date) as order_date,
    cast(h.CustNum as integer) as cust_num,
    nullif(h.CurrencyCode, '') as currency_code,
    d.PartNum as part_num,
    cast(d.OrderQty as integer) as quantity,
    cast(d.UnitPrice as numeric(18, 4)) as unit_price_local,
    cast(d.DiscountPct as numeric(18, 4)) as discount_pct,
    d._loaded_at
from {{ source('erp_b', 'orderdtl') }} d
left join {{ source('erp_b', 'orderhed') }} h on h.OrderNum = d.OrderNum
