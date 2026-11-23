# ERPBridge: merging two ERPs into one governed warehouse with dbt

When a manufacturer buys another company, it also takes on that company's ERP. Then someone
has to answer simple questions across both systems: who are our customers, what did we sell,
and at what margin. Doing that safely is mostly a data-engineering and data-governance problem:

* the same customer is spelled differently in each system;
* the same product has a different part number;
* the two systems use different currencies;
* each extract has its own defects;
* personal data must not reach the dashboards.

ERPBridge builds that warehouse end to end:

* extracts from two ERPs;
* a RAW layer;
* a dbt project with staging, master-data matching, and Kimball marts;
* tests, data contracts, PII masking, an incremental fact table and a type-2 history snapshot;
* a dashboard;

Every claim the warehouse makes is scored against ground truth.

```
ERP A extract ─┐                                        ┌─ dim_customer  (golden record, PII-masked view for BI)
(AdventureWorks)│   RAW        staging        intermediate│  dim_product   (+ "unmapped" member)
               ├─► (text) ─► (typed) ─► MDM match/links ├─ dim_date
ERP B extract ─┘                         validation     ├─ fct_sales_order_line (incremental, USD, point-in-time cost)
(acquired, EUR/GBP)                      (quarantine)   ├─ fct_purchase_order_line
                                                        └─ quality.dq_quarantine / dq_summary
```

## Data

* **ERP A** is Microsoft's **AdventureWorks** OLTP sample: a bicycle manufacturer's ERP with sales,
  purchasing, production, product cost history and daily currency rates.
  * Size: 31,465 orders, 121,317 order lines, 19,820 customers.
  * `extract/aw_extract.py` turns its three different file layouts into headered CSVs, using
    column names taken from the sample's own install script. It checks every row's field count.
* **ERP B** is **synthetic**. `extract/make_erp_b.py` generates it from ERP A with a fixed seed, so that
  every hard case has a known right answer:
  * 1,500 of ERP A's European customers re-keyed the way another system would hold them: different
    name order and case, typos, "Str." vs "Straße", "Inc." vs "Incorporated", missing e-mails;
  * 1,000 customers that exist only in ERP B. 200 of them are deliberately hard: same surname and
    address as an ERP A customer, but a different person;
  * 150 parts under ERP B's own part numbers, with 6 missing from the cross-reference;
  * 9,000 orders in EUR and GBP, priced from ERP A's list price and the day's exchange rate;
  * 120 injected defects of 5 kinds (50 at order level, 70 at line level).
* The ground truth is written to `landing/ground_truth/`. It is **never loaded** into the
  warehouse; only `eval/evaluate.py` reads it.

## Results (all measured by `eval/evaluate.py`; full output in `results/metrics.json`)

| What | Result |
|---|---|
| Customer matching, held-out half (thresholds set on the other half) | precision **99.7%**, recall **98.9%** |
| Customer matching, all 2,500 ERP B customers | 1,488 of 1,500 true matches found, **2 false merges** |
| Household cases (same surname + address, different person) | **0 of 200** wrongly merged |
| Duplicate customer records found *inside* ERP A | **635** store records collapsed to one per store |
| EUR/GBP lines converted to USD | **27,130 of 27,130 exact to the cent** |
| Injected defects (orphan orders, bad dates, missing currency, bad quantities, duplicate lines) | **120 of 120 quarantined under the right reason, 0 false flags** |
| Lines whose part has no cross-reference | 1,039 lines kept on the "unmapped" product member, not dropped ($0.99m of revenue made visible) |
| Day-2 delta of 300 new lines | fact grew by exactly 300; earlier rows untouched (incremental) |
| 50 customers moving address on day 2 | exactly 50 closed history rows in the snapshot; **no customer link lost** |
| Personal data through the BI view | 0 unmasked names, e-mails, phones or addresses |
| Every source order line accounted for | in the fact or in quarantine, checked by a dbt test |

dbt: 24 models, 1 snapshot, 48 data tests (generic and singular), 2 unit tests (14 cases), and
enforced contracts on the two main marts. pytest: 8 end-to-end and extraction tests. SQL is linted with sqlfluff.
The whole pipeline (both days) runs in about 20 seconds on DuckDB.

## How it works

**Master data (customers).**
1. `int_a_customer_canonical` first fixes ERP A's own problem: most stores exist twice there.
2. Matching blocks candidate pairs on country + postal code, or on e-mail.
3. Each pair is scored with Jaro-Winkler on names and addresses after normalisation (macros in
   `macros/matching.sql`).
4. Explicit rules decide which pairs match, so a data steward can read them.
5. Each record is linked at most once.
6. Links are **persisted** (`int_customer_links`, incremental). A customer who moves house keeps
   their link; unlinking is a steward's decision.

**Money.**
* ERP B amounts are converted using the USD rate on the order date, rounded half-up to the cent.
* Standard cost is taken **point-in-time**, from the cost interval in force on the order date.
* A gap in ERP A's cost history falls back to the latest earlier cost, and the line is flagged in
  `cost_basis`. It is never silently guessed.
* A test proves cost intervals never overlap, so the join cannot fan out.

**Quality.** ERP B lines are validated in one model; each invalid line carries the first rule it
breaks and goes to `quality.dq_quarantine`. A singular test proves no line disappears.

**Governance.**
* Columns tagged `meta: {pii: true}` are masked by a post-hook. On **Snowflake** it attaches a
  column masking policy: only the `PII_READER` role sees values. On **DuckDB** it creates a
  `_masked` view for BI.
* `company_name` exists so reports can name business customers without exposing individuals.
* `dbt docs generate` gives the catalog and lineage graph.


## Running it

```bash
pip install -r requirements.txt
scripts/fetch_data.sh                        # AdventureWorks into data/adventureworks
./run_pipeline.sh data/adventureworks        # day 1 + day 2 on DuckDB, all dbt tests, evaluation
ERPBRIDGE_SKIP_RUN=1 python -m pytest -q tests
python dashboard/build.py                    # dashboard/erpbridge_dashboard.html
sqlfluff lint dbt/models
```

**On Snowflake.**
1. Run `snowflake_setup.sql` once as an admin in a trial account.
2. Set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER` and `SNOWFLAKE_PASSWORD`.
3. Run:

```bash
python load/load.py snowflake                # PUT + COPY INTO the raw schemas
cd dbt && dbt build --profiles-dir . --target snowflake
```

Warehouse-specific SQL goes through `adapter.dispatch` macros: Jaro-Winkler, regex replace, the
date spine, and PII masking.

## Honest limits

* **The Snowflake path has not been run yet.** This was built where Snowflake is unreachable; every
  number above comes from DuckDB. The loader, profile, dispatch macros, masking policy and CI job
  for Snowflake are written but unexecuted.
* The CI workflow has not run on GitHub yet.
* ERP B is synthetic. Its variations were designed by the same person who wrote the matching
  rules, so real data will be messier. That is why thresholds were set on one half and reported on
  the other.
* The dashboard is a static HTML page, not Power BI or Tableau. The marts are shaped for either
  (star schema, masked view).
* Matching uses deterministic rules, not a trained model. Production MDM would add a steward
  review queue for borderline scores.
