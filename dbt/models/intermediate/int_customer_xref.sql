-- Every source customer -> one golden customer key. ERP A is the system of record, so a
-- matched ERP B customer takes its ERP A partner's key; unmatched ERP B customers get their own.
select 'A' as source_system, cast(customer_id as varchar) as source_customer_id,
       'A-' || cast(canonical_customer_id as varchar) as customer_key
from {{ ref('int_a_customer_canonical') }}
union all
select 'B', cast(b.cust_num as varchar),
       case when m.a_id is not null then 'A-' || m.a_id else 'B-' || cast(b.cust_num as varchar) end
from {{ ref('stg_b__customers') }} b
left join {{ ref('int_customer_links') }} m on m.b_id = cast(b.cust_num as varchar)
