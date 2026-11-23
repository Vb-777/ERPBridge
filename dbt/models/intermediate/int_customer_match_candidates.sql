-- Candidate pairs (ERP B customer, ERP A customer) from two blocking keys:
-- same country + postal code, or the same e-mail. Then similarity features per pair.
with a as (select * from {{ ref('int_customers_normalised') }} where source_system = 'A'),
     b as (select * from {{ ref('int_customers_normalised') }} where source_system = 'B'),
pairs as (
    select b.source_customer_id as b_id, a.source_customer_id as a_id
    from b inner join a on a.country_code = b.country_code and a.postal_norm = b.postal_norm
    union
    select b.source_customer_id as b_id, a.source_customer_id as a_id
    from b inner join a on a.email_norm = b.email_norm
    where b.email_norm is not null
)
select
    p.b_id, p.a_id, a.customer_kind,
    coalesce(a.email_norm = b.email_norm, false) as email_match,
    coalesce(a.phone_tail = b.phone_tail, false) as phone_match,
    {{ jaro_winkler('a.address_norm', 'b.address_norm') }} as address_sim,
    {{ jaro_winkler('a.company_norm', 'b.company_norm') }} as company_sim,
    {{ jaro_winkler('a.last_norm', 'b.last_norm') }} as last_name_sim,
    {{ jaro_winkler('a.name_compact', 'b.name_compact') }} as full_name_sim,
    {{ jaro_winkler('a.first_norm', 'b.first_norm') }} as first_name_sim,
    length(b.first_norm) = 1 and left(a.first_norm, 1) = b.first_norm as first_initial_match
from pairs p
inner join a on a.source_customer_id = p.a_id
inner join b on b.source_customer_id = p.b_id
