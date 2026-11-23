-- One row per data-quality measure; the dashboard's quality panel reads this.
select 'quarantined_lines:' || reject_reason as measure, count(*) as value
from {{ ref('dq_quarantine') }} group by reject_reason
union all
select 'lines_unmapped_product', count(*) from {{ ref('fct_sales_order_line') }} where product_key = -1
union all
select 'lines_cost_basis:' || cost_basis, count(*) from {{ ref('fct_sales_order_line') }} group by cost_basis
union all
select 'customers_in_both_erps', count(*) from {{ ref('dim_customer') }} where source_systems = 'A+B'
union all
select 'a_duplicate_customer_records_collapsed', count(*) from {{ ref('int_a_customer_canonical') }} where customer_id <> canonical_customer_id
