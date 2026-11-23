#!/usr/bin/env bash
# End-to-end run on DuckDB: extract -> load -> dbt build -> evaluate; then day 2 (delta + history).
#   ./run_pipeline.sh /path/to/unzipped/AdventureWorks
set -euo pipefail
cd "$(dirname "$0")"
AW=${1:-data/adventureworks}
export DBT_PROFILES_DIR=$PWD/dbt DO_NOT_TRACK=1
rm -rf landing warehouse/erpbridge.duckdb
python extract/aw_extract.py "$AW" landing/erp_a
python extract/make_erp_b.py landing
python load/load.py duckdb warehouse/erpbridge.duckdb
(cd dbt && dbt build --quiet)
python eval/evaluate.py warehouse/erpbridge.duckdb > /dev/null
cp results/metrics.json results/metrics_day1.json
# day 2: master data changes + delta orders
python extract/make_erp_b_day2.py landing
python load/load.py duckdb warehouse/erpbridge.duckdb day2
(cd dbt && dbt snapshot --quiet && dbt build --quiet --exclude resource_type:snapshot)
python eval/evaluate.py warehouse/erpbridge.duckdb > /dev/null
python eval/day2_check.py warehouse/erpbridge.duckdb
