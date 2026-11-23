{{ config(materialized='incremental', unique_key='b_id', incremental_strategy='delete+insert') }}
-- Persisted ERP B -> ERP A customer links. Once a link is made it stays, even if a later extract
-- changes the record (a customer who moves house is still the same customer); new links are added
-- for ERP B customers not linked yet. Unlinking is a data-steward decision, not a side effect of a run.
select m.b_id, m.a_id, m.match_rule, m.match_score, current_timestamp as linked_at
from {{ ref('int_customer_matches') }} m
{% if is_incremental() %}
where m.b_id not in (select t.b_id from {{ this }} as t)
  and m.a_id not in (select t.a_id from {{ this }} as t)
{% endif %}
