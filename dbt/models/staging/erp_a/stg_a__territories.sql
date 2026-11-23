select cast(TerritoryID as integer) as territory_id, Name as territory_name,
       CountryRegionCode as country_code, "GROUP" as territory_group
from {{ source('erp_a', 'salesterritory') }}
