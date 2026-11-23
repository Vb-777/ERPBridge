-- ERP A keeps two customer records for most stores (one bare store record, one store + contact
-- person that carries the orders). Collapse them: one canonical record per store, preferring the
-- record with orders. Individual (person) customers are already one record each.
with c as (
    select cast(CustomerID as integer) as customer_id, cast(StoreID as integer) as store_id
    from {{ source('erp_a', 'customer') }}
),
with_orders as (select distinct cast(CustomerID as integer) as customer_id from {{ source('erp_a', 'salesorderheader') }})
select
    c.customer_id,
    case when c.store_id is null then c.customer_id
         else first_value(c.customer_id) over (
                  partition by c.store_id
                  order by case when o.customer_id is not null then 0 else 1 end, c.customer_id)
    end as canonical_customer_id
from c
left join with_orders o on o.customer_id = c.customer_id
