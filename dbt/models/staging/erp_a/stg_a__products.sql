select
    cast(p.ProductID as integer) as product_id,
    p.ProductNumber as product_number,
    p.Name as product_name,
    coalesce(cat.Name, 'Components & Other') as category,
    coalesce(sub.Name, 'Unclassified') as subcategory,
    cast(p.FinishedGoodsFlag as integer) = 1 as is_finished_good,
    cast(p.StandardCost as numeric(18, 4)) as current_standard_cost,
    cast(p.ListPrice as numeric(18, 4)) as current_list_price,
    p.SellEndDate is null as is_active
from {{ source('erp_a', 'product') }} p
left join {{ source('erp_a', 'productsubcategory') }} sub on sub.ProductSubcategoryID = p.ProductSubcategoryID
left join {{ source('erp_a', 'productcategory') }} cat on cat.ProductCategoryID = sub.ProductCategoryID
