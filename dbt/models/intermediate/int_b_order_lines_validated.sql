-- Every ERP B order line with the first rule it breaks (null = valid). Invalid lines are kept
-- here and in quality.dq_quarantine, never silently dropped.
with l as (
    select *, row_number() over (partition by order_id, order_line_id order by part_num, quantity) as copy_no
    from {{ ref('stg_b__order_lines') }}
),
c as (select cust_num from {{ ref('stg_b__customers') }}),
fx as (select * from {{ ref('stg_a__currency_rates') }})
select
    l.*,
    fx.usd_to_currency,
    case
        when l.copy_no > 1 then 'duplicate_line'
        when c.cust_num is null then 'orphan_customer'
        when l.order_date is null or l.order_date > cast('{{ var("max_valid_order_date") }}' as date) then 'invalid_order_date'
        when l.currency_code is null then 'missing_currency'
        when l.quantity <= 0 then 'bad_quantity'
        when fx.usd_to_currency is null then 'missing_fx_rate'
    end as reject_reason
from l
left join c on c.cust_num = l.cust_num
left join fx on fx.rate_date = l.order_date and fx.currency_code = l.currency_code
