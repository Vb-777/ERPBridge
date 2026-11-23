"""Scores the warehouse against the ground truth that make_erp_b.py wrote (never loaded into
the warehouse). Writes results/metrics.json.

    python eval/evaluate.py warehouse/erpbridge.duckdb
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
GT = ROOT / "landing" / "ground_truth"


def _score(truth, pred):
    tp = sum(1 for b, a in pred.items() if truth[b][0] == a)
    pos = sum(1 for t in truth.values() if t[0])
    return {"true_matches": pos, "predicted_matches": len(pred), "correct": tp, "false_merges": len(pred) - tp,
            "missed": pos - tp, "precision": round(tp / len(pred), 4) if pred else None,
            "recall": round(tp / pos, 4), "f1": round(2 * tp / (len(pred) + pos), 4)}


def mdm(con):
    """Customer matching. ERP A's own duplicate store records are collapsed first, so a match is
    correct when it points at the canonical record of the right ERP A customer. Rule thresholds were
    set looking only at even-numbered ERP B customers (dev); odd-numbered ones (test) were held out."""
    canon = dict(con.execute("select customer_id, canonical_customer_id from intermediate.int_a_customer_canonical").fetchall())
    truth = {int(r["CustNum"]): (canon[int(r["a_customer_id"])] if r["a_customer_id"] else None, r["case"])
             for r in csv.DictReader(open(GT / "customer_truth.csv"))}
    pred = {int(b): int(a) for b, a in con.execute("select b_id, a_id from intermediate.int_customer_links").fetchall()}
    house = [b for b, t in truth.items() if t[1] == "household_not_same_person"]
    split = lambda d, h: {k: v for k, v in d.items() if k % 2 == h}
    return {
        "b_customers": len(truth),
        "all": _score(truth, pred),
        "dev_even_ids": _score(split(truth, 0), split(pred, 0)),
        "test_odd_ids": _score(split(truth, 1), split(pred, 1)),
        "household_false_merges": sum(1 for b in house if b in pred), "household_cases": len(house),
        "a_duplicate_store_records_collapsed": con.execute(
            "select count(*) from intermediate.int_a_customer_canonical where customer_id <> canonical_customer_id").fetchone()[0],
        "by_rule": dict(con.execute("select match_rule, count(*) from intermediate.int_customer_links group by 1 order by 2 desc").fetchall()),
    }


def main(db):
    con = duckdb.connect(db, read_only=True)
    out = {"mdm": mdm(con)}
    for name, fn in EXTRA:
        try:
            out[name] = fn(con)
        except duckdb.CatalogException as e:  # mart not built yet
            out[name] = {"skipped": str(e).splitlines()[0]}
    (ROOT / "results").mkdir(exist_ok=True)
    json.dump(out, open(ROOT / "results" / "metrics.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


def fx(con):
    """ERP B lines converted to USD by the warehouse vs the USD amount the generator priced them at."""
    truth = {(int(r["OrderNum"]), int(r["OrderLine"])): float(r["usd_amount"]) for r in csv.DictReader(open(GT / "line_usd_truth.csv"))}
    rows = con.execute("select order_id, order_line_id, net_amount_usd from core.fct_sales_order_line where source_system = 'B'").fetchall()
    diffs = [abs(float(v) - truth[(o, l)]) for o, l, v in rows]
    return {"b_lines_in_fact": len(rows), "exact_to_the_cent": sum(d < 0.005 for d in diffs), "max_abs_diff_usd": round(max(diffs), 4)}


def defects(con):
    """Each injected defect must be quarantined under the right reason, and nothing else may be."""
    want = {"orphan_customer": set(), "invalid_order_date": set(), "missing_currency": set(), "bad_quantity": set(), "duplicate_line": set()}
    name = {"future_date": "invalid_order_date"}
    for d in csv.DictReader(open(GT / "defects.csv")):
        k = name.get(d["kind"], d["kind"])
        want[k].add((int(d["OrderNum"]), int(d["OrderLine"])) if d["OrderLine"] else int(d["OrderNum"]))
    got = {}
    for o, l, reason in con.execute("select order_id, order_line_id, reject_reason from quality.dq_quarantine").fetchall():
        got.setdefault(reason, set()).add((o, l) if reason in ("bad_quantity", "duplicate_line") else o)
    out = {k: {"injected": len(v), "caught": len(v & got.get(k, set())), "wrongly_flagged": len(got.get(k, set()) - v)}
           for k, v in want.items()}
    out["other_reasons"] = {k: len(v) for k, v in got.items() if k not in want}
    return out


def unmapped(con):
    s = json.load(open(GT / "summary.json"))
    parts = s["unmapped_parts"]
    in_fact = con.execute("select count(*) from core.fct_sales_order_line where product_key = -1").fetchone()[0]
    expected = con.execute(f"""select count(*) from intermediate.int_b_order_lines_validated
                               where reject_reason is null and part_num in ({", ".join(f"'{p}'" for p in parts)})""").fetchone()[0]
    usd = con.execute("select round(sum(net_amount_usd), 2) from core.fct_sales_order_line where product_key = -1").fetchone()[0]
    return {"unmapped_parts": len(parts), "lines_on_unmapped_member": in_fact, "expected": expected, "unmapped_revenue_usd": float(usd)}


def totals(con):
    q = lambda sql: con.execute(sql).fetchall()
    return {
        "fact_lines_by_source": dict(q("select source_system, count(*) from core.fct_sales_order_line group by 1 order by 1")),
        "revenue_usd_by_source": {k: float(v) for k, v in q("select source_system, round(sum(net_amount_usd), 2) from core.fct_sales_order_line group by 1 order by 1")},
        "golden_customers": dict(q("select source_systems, count(*) from core.dim_customer group by 1 order by 1")),
        "cost_basis": dict(q("select cost_basis, count(*) from core.fct_sales_order_line group by 1 order by 1")),
        "revenue_in_shared_customers_usd": float(q("select round(sum(f.net_amount_usd), 2) from core.fct_sales_order_line f join core.dim_customer c using (customer_key) where c.source_systems = 'A+B'")[0][0]),
    }


EXTRA = [("fx", fx), ("defects", defects), ("unmapped", unmapped), ("totals", totals)]

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "warehouse" / "erpbridge.duckdb"))
