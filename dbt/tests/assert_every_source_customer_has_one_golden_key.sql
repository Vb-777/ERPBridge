select source_system, source_customer_id, count(*) from {{ ref('int_customer_xref') }}
group by 1, 2 having count(*) <> 1
