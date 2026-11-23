-- ERP A order lines joined to their header. Amounts are in USD in this ERP.
select
    cast(h.SalesOrderID as integer) as order_id,
    cast(d.SalesOrderDetailID as integer) as order_line_id,
    cast(cast(h.OrderDate as timestamp) as date) as order_date,
    cast(cast(h.ShipDate as timestamp) as date) as ship_date,
    cast(cast(h.DueDate as timestamp) as date) as due_date,
    cast(h.CustomerID as integer) as customer_id,
    cast(h.TerritoryID as integer) as territory_id,
    cast(h.OnlineOrderFlag as integer) = 1 as is_online,
    cast(d.ProductID as integer) as product_id,
    cast(d.OrderQty as integer) as quantity,
    cast(d.UnitPrice as numeric(18, 4)) as unit_price,
    cast(d.UnitPriceDiscount as numeric(18, 4)) as discount_pct,
    cast(d.LineTotal as numeric(18, 6)) as line_total_usd,
    cast(h.SubTotal as numeric(18, 4)) as header_subtotal_usd,
    d._loaded_at
from {{ source('erp_a', 'salesorderdetail') }} d
inner join {{ source('erp_a', 'salesorderheader') }} h on h.SalesOrderID = d.SalesOrderID
