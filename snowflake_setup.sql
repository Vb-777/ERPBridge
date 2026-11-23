-- One-time Snowflake setup (run as ACCOUNTADMIN in a trial account). Not executed by this repo's tests.
create role if not exists transformer;
create role if not exists pii_reader;          -- sees unmasked personal data
create role if not exists reporting;           -- BI tools: masked
grant role transformer to role sysadmin;
grant role pii_reader to role sysadmin;
create warehouse if not exists transforming warehouse_size = xsmall auto_suspend = 60 initially_suspended = true;
create database if not exists erpbridge;
grant usage on warehouse transforming to role transformer;
grant all on database erpbridge to role transformer;
grant create masking policy on schema erpbridge.public to role transformer;
grant usage on warehouse transforming to role reporting;
grant usage on database erpbridge to role reporting;
-- after the first dbt build:
-- grant usage on schema erpbridge.core to role reporting;
-- grant select on all tables in schema erpbridge.core to role reporting;
