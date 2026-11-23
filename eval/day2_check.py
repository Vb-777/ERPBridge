"""After the day-2 run: the fact grew by exactly the delta (incremental, earlier rows untouched),
and the snapshot holds exactly one closed history row per moved customer."""
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
con = duckdb.connect(sys.argv[1], read_only=True)
d1 = json.load(open(ROOT / "results" / "metrics_day1.json"))
d2 = json.load(open(ROOT / "landing" / "ground_truth" / "day2.json"))
b_before = d1["totals"]["fact_lines_by_source"]["B"]
b_now, loads = con.execute("select count(*), count(distinct loaded_at) from core.fct_sales_order_line where source_system = 'B'").fetchone()
closed = sorted(r[0] for r in con.execute(
    "select cast(CustNum as integer) from snapshots.snap_b_customer where dbt_valid_to is not null").fetchall())
out = {
    "b_fact_lines_day1": b_before, "b_fact_lines_day2": b_now, "new_lines_expected": d2["new_lines"],
    "incremental_ok": b_now - b_before == d2["new_lines"] and loads == 2,
    "scd2_closed_versions": len(closed), "scd2_matches_moved_customers": closed == d2["moved_customers"],
}
m = json.load(open(ROOT / "results" / "metrics.json"))
m["day2"] = out
json.dump(m, open(ROOT / "results" / "metrics.json", "w"), indent=1)
print(json.dumps(out, indent=1))
assert out["incremental_ok"] and out["scd2_matches_moved_customers"], out
