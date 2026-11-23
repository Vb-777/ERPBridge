select
    cast(CustNum as integer) as cust_num,
    Name as customer_name,
    Address1 as address_line1,
    City as city,
    Zip as postal_code,
    Country as country_code,
    nullif(lower(trim(EMailAddress)), '') as email,
    nullif(PhoneNum, '') as phone
from {{ source('erp_b', 'customer') }}
