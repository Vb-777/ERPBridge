-- Both customer masters in one shape, with match keys. Only European ERP A customers can
-- appear in ERP B (it is a European business), so only they are candidates.
with a as (
    select 'A' as source_system, cast(c.customer_id as varchar) as source_customer_id, customer_kind,
           customer_name, first_name, last_name, email, phone, address_line1, city, postal_code, country_code
    from {{ ref('stg_a__customers') }} c
    join {{ ref('int_a_customer_canonical') }} k on k.customer_id = c.customer_id and k.canonical_customer_id = c.customer_id
    where country_code in ('DE', 'FR', 'GB')
),
b as (
    select 'B', cast(cust_num as varchar), null, customer_name, null, null, email, phone,
           address_line1, city, postal_code, country_code
    from {{ ref('stg_b__customers') }}
),
u as (select * from a union all select * from b),
named as (
    select *,
        -- person names: put "LAST, First" back in order; first/last token give first and last name
        {{ mdm_clean(mdm_person_order('customer_name')) }} as name_clean
    from u
)
select
    source_system, source_customer_id, customer_kind, customer_name, country_code,
    trim(name_clean) as name_norm,
    {{ mdm_company('customer_name') }} as company_norm,
    coalesce(lower(first_name), split_part(trim(name_clean), ' ', 1)) as first_norm,
    coalesce(lower(last_name), split_part(trim(name_clean), ' ', -1)) as last_norm,
    replace(trim(name_clean), ' ', '') as name_compact,
    {{ mdm_address('address_line1') }} as address_norm,
    {{ mdm_postal('postal_code') }} as postal_norm,
    lower(email) as email_norm,
    nullif({{ mdm_phone_tail('phone') }}, '') as phone_tail
from named
