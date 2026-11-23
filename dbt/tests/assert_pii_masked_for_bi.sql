-- BI tools read the masked view (DuckDB) / policy-masked table (Snowflake): no raw PII may show.
{% if target.type == 'duckdb' %}
{%- set d = ref('dim_customer') %}
select customer_key from {{ d.schema }}.{{ d.identifier }}_masked
where coalesce(customer_name, '***MASKED***') <> '***MASKED***'
   or coalesce(email, '***MASKED***') <> '***MASKED***'
   or coalesce(phone, '***MASKED***') <> '***MASKED***'
   or coalesce(address_line1, '***MASKED***') <> '***MASKED***'
{% else %}
select 1 where false
{% endif %}
