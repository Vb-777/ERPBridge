select
    cast(h.PurchaseOrderID as integer) as purchase_order_id,
    cast(d.PurchaseOrderDetailID as integer) as purchase_order_line_id,
    cast(h.VendorID as integer) as vendor_id,
    v.Name as vendor_name,
    cast(cast(h.OrderDate as timestamp) as date) as order_date,
    cast(cast(d.DueDate as timestamp) as date) as due_date,
    cast(cast(h.ShipDate as timestamp) as date) as ship_date,
    cast(h.Status as integer) as status,
    cast(d.ProductID as integer) as product_id,
    cast(d.OrderQty as integer) as quantity_ordered,
    cast(cast(d.ReceivedQty as numeric(18, 2)) as integer) as quantity_received,
    cast(cast(d.RejectedQty as numeric(18, 2)) as integer) as quantity_rejected,
    cast(d.UnitPrice as numeric(18, 4)) as unit_price_usd,
    cast(d.LineTotal as numeric(18, 4)) as line_total_usd
from {{ source('erp_a', 'purchaseorderdetail') }} d
inner join {{ source('erp_a', 'purchaseorderheader') }} h on h.PurchaseOrderID = d.PurchaseOrderID
inner join {{ source('erp_a', 'vendor') }} v on v.BusinessEntityID = h.VendorID
