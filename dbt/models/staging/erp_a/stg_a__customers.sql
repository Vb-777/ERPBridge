-- One row per ERP A customer: a person (individual buyer) or a store (reseller), with its primary address.
with cust as (
    select cast(CustomerID as integer) as customer_id, AccountNumber as account_number,
           cast(PersonID as integer) as person_id, cast(StoreID as integer) as store_id,
           cast(TerritoryID as integer) as territory_id
    from {{ source('erp_a', 'customer') }}
),
addr as (
    select cast(bea.BusinessEntityID as integer) as entity_id, ad.AddressLine1 as address_line1, ad.City as city,
           ad.PostalCode as postal_code, sp.CountryRegionCode as country_code,
           row_number() over (partition by bea.BusinessEntityID order by cast(bea.AddressTypeID as integer)) as rn
    from {{ source('erp_a', 'businessentityaddress') }} bea
    inner join {{ source('erp_a', 'address') }} ad on ad.AddressID = bea.AddressID
    inner join {{ source('erp_a', 'stateprovince') }} sp on sp.StateProvinceID = ad.StateProvinceID
)
select
    c.customer_id,
    c.account_number,
    case when c.store_id is null then 'person' else 'company' end as customer_kind,
    coalesce(s.Name, p.FirstName || ' ' || p.LastName) as customer_name,
    p.FirstName as first_name,
    p.LastName as last_name,
    e.EmailAddress as email,
    ph.PhoneNumber as phone,
    a.address_line1, a.city, a.postal_code, a.country_code,
    c.territory_id
from cust c
left join {{ source('erp_a', 'person') }} p on cast(p.BusinessEntityID as integer) = c.person_id
left join {{ source('erp_a', 'store') }} s on cast(s.BusinessEntityID as integer) = c.store_id
left join {{ source('erp_a', 'emailaddress') }} e on cast(e.BusinessEntityID as integer) = c.person_id
left join {{ source('erp_a', 'personphone') }} ph on cast(ph.BusinessEntityID as integer) = c.person_id
left join addr a on a.entity_id = coalesce(c.store_id, c.person_id) and a.rn = 1
