-- Golden customer record across both ERPs. Survivorship: ERP A (system of record) wins for
-- name and address; e-mail and phone fall back to ERP B when ERP A has none.
with x as (select * from {{ ref('int_customer_xref') }}),
keys as (
    select customer_key,
           max(case when source_system = 'A' then 1 else 0 end) as in_a,
           max(case when source_system = 'B' then 1 else 0 end) as in_b,
           min(case when source_system = 'B' then cast(source_customer_id as integer) end) as b_cust_num
    from x group by customer_key
),
a as (
    select c.* from {{ ref('stg_a__customers') }} c
    inner join {{ ref('int_a_customer_canonical') }} k on k.customer_id = c.customer_id and k.canonical_customer_id = c.customer_id
),
b as (select * from {{ ref('stg_b__customers') }})
select
    k.customer_key,
    case when k.in_a = 1 and k.in_b = 1 then 'A+B' when k.in_a = 1 then 'A' else 'B' end as source_systems,
    a.customer_id as a_customer_id,
    k.b_cust_num,
    coalesce(a.customer_kind, case when b.customer_name like '%,%' then 'person' else 'unknown' end) as customer_kind,
    coalesce(a.customer_name, trim(b.customer_name)) as customer_name,
    -- business name for reporting; null for individual buyers, whose names are personal data
    case when a.customer_kind = 'company' then a.customer_name end as company_name,
    coalesce(a.address_line1, b.address_line1) as address_line1,
    coalesce(a.city, b.city) as city,
    coalesce(a.postal_code, b.postal_code) as postal_code,
    coalesce(a.country_code, b.country_code) as country_code,
    coalesce(lower(a.email), b.email) as email,
    coalesce(a.phone, b.phone) as phone,
    m.match_rule
from keys k
left join a on 'A-' || cast(a.customer_id as varchar) = k.customer_key
left join b on b.cust_num = k.b_cust_num
left join {{ ref('int_customer_links') }} m on m.b_id = cast(k.b_cust_num as varchar) and k.in_a = 1
