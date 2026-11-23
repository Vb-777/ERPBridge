select p.PartNum as part_num, p.PartDescription as part_description, x.aw_product_number as product_number
from {{ source('erp_b', 'part') }} p
left join {{ source('erp_b', 'part_xref') }} x on x.PartNum = p.PartNum
