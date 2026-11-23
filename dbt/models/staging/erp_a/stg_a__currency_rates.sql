-- Daily USD -> currency average rates.
select
    cast(cast(CurrencyRateDate as timestamp) as date) as rate_date,
    ToCurrencyCode as currency_code,
    cast(AverageRate as numeric(18, 6)) as usd_to_currency
from {{ source('erp_a', 'currencyrate') }}
where FromCurrencyCode = 'USD'
