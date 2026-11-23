-- Match decision per candidate pair, then at most one ERP A customer per ERP B customer and
-- vice versa (best score wins). Rules are deliberately explicit so a data steward can read them.
with scored as (
    select *,
        case
            when email_match and (last_name_sim >= 0.80 or company_sim >= 0.80) then 'email + name'
            when customer_kind = 'company' and company_sim >= 0.90 and address_sim >= 0.85 then 'company name + address'
            when customer_kind = 'person' and last_name_sim >= 0.92 and address_sim >= 0.85
                 and (first_name_sim >= 0.90 or first_initial_match) then 'person name + address'
            -- typos that move a letter across the space ("Shawn Xu" -> "SHAW NXU") break per-token
            -- similarity; compare the names with spaces removed instead (threshold set on the dev half)
            when customer_kind = 'person' and full_name_sim >= 0.93 and address_sim >= 0.90 then 'person full name + address'
        end as match_rule,
        (case when email_match then 0.4 else 0 end) + 0.3 * address_sim
          + 0.3 * case when customer_kind = 'company' then company_sim else (last_name_sim + first_name_sim) / 2 end as match_score
    from {{ ref('int_customer_match_candidates') }}
),
matched as (select * from scored where match_rule is not null),
best_for_b as (
    select * from matched
    qualify row_number() over (partition by b_id order by match_score desc, a_id asc) = 1
)
select b_id, a_id, match_rule, match_score, address_sim, company_sim, last_name_sim, first_name_sim, email_match
from best_for_b
qualify row_number() over (partition by a_id order by match_score desc, b_id asc) = 1
