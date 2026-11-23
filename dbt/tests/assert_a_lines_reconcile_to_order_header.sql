-- Fact amounts for ERP A must add up to each order's header subtotal (per-line rounding to the cent allowed).
select f.order_id, sum(f.net_amount_usd) as fact_total, max(s.header_subtotal_usd) as header_total
from {{ ref('fct_sales_order_line') }} f
join {{ ref('stg_a__sales_order_lines') }} s on f.source_system = 'A' and s.order_line_id = f.order_line_id
group by f.order_id
having abs(sum(f.net_amount_usd) - max(s.header_subtotal_usd)) > 0.005 * count(*) + 0.0001
