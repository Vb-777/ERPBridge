-- Standard cost validity intervals; EndDate is inclusive in this ERP (next interval starts the day after).
select
    cast(ProductID as integer) as product_id,
    cast(cast(StartDate as timestamp) as date) as valid_from,
    cast(cast(EndDate as timestamp) as date) as valid_to,
    cast(StandardCost as numeric(18, 4)) as standard_cost
from {{ source('erp_a', 'productcosthistory') }}
