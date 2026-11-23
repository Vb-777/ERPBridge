-- Rejected source rows with the rule they broke, for the data steward's work queue.
select 'B' as source_system, order_id, order_line_id, cust_num, order_date, currency_code, part_num, quantity, reject_reason
from {{ ref('int_b_order_lines_validated') }}
where reject_reason is not null
