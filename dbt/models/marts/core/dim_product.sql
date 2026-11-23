-- ERP A product master is the product system of record; -1 is the "unmapped" member that ERP B
-- lines point to when the MDM cross-reference has no entry for their part number.
select product_id as product_key, product_number, product_name, category, subcategory,
       is_finished_good, is_active, current_list_price, current_standard_cost
from {{ ref('stg_a__products') }}
union all
select -1, 'UNMAPPED', 'Unmapped ERP B part', 'Unmapped', 'Unmapped', true, true, null, null
