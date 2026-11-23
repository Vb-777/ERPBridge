"""The next day's ERP B extract, to exercise incremental loading and history tracking:

* customer master (full extract, replaces yesterday's): 50 customers have moved address;
* orders (delta extract, appended): 300 new orders, landed in landing/erp_b/day2/.

Ground truth for the new lines is appended to landing/ground_truth/line_usd_truth.csv.

    python extract/make_erp_b_day2.py landing
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

SEED = 20272


def main(root: str):
    root = Path(root)
    b, gt = root / "erp_b", root / "ground_truth"
    r = random.Random(SEED)
    cust = list(csv.DictReader(open(b / "customer.csv", encoding="utf-8")))
    moved = r.sample(range(len(cust)), 50)
    for i in moved:
        cust[i]["Address1"] = f"{r.randint(1, 400)} {r.choice(['Kings Road', 'Lindenallee', 'Rue Victor Hugo', 'Station Road'])}"
    with open(b / "customer.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cust[0].keys()))
        w.writeheader()
        w.writerows(cust)

    heads = {h["OrderNum"]: h for h in csv.DictReader(open(b / "orderhed.csv", encoding="utf-8"))}
    lines = list(csv.DictReader(open(b / "orderdtl.csv", encoding="utf-8")))
    truth = {(t["OrderNum"], t["OrderLine"]): t["usd_amount"] for t in csv.DictReader(open(gt / "line_usd_truth.csv"))}
    defects = {d["OrderNum"] for d in csv.DictReader(open(gt / "defects.csv"))}
    xref = {x["PartNum"] for x in csv.DictReader(open(b / "part_xref.csv"))}
    templates = [l for l in lines if l["OrderNum"] not in defects and int(l["OrderQty"]) > 0 and l["PartNum"] in xref]
    valid_cust = [c["CustNum"] for c in cust]
    new_heads, new_lines, new_truth = [], [], []
    for n in range(300):
        t = r.choice(templates)
        h = heads[t["OrderNum"]]
        ordnum = str(600000 + n)
        new_heads.append(dict(h, OrderNum=ordnum, CustNum=r.choice(valid_cust)))
        new_lines.append(dict(t, OrderNum=ordnum, OrderLine="1"))
        new_truth.append(dict(OrderNum=ordnum, OrderLine="1", usd_amount=truth[(t["OrderNum"], t["OrderLine"])]))
    d2 = b / "day2"
    d2.mkdir(exist_ok=True)
    for name, rows in (("orderhed", new_heads), ("orderdtl", new_lines)):
        with open(d2 / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    with open(gt / "line_usd_truth.csv", "a", newline="") as f:
        csv.DictWriter(f, fieldnames=["OrderNum", "OrderLine", "usd_amount"]).writerows(new_truth)
    json.dump({"moved_customers": sorted(int(cust[i]["CustNum"]) for i in moved), "new_orders": 300, "new_lines": 300},
              open(gt / "day2.json", "w"), indent=1)
    print("day 2: 50 customers moved, 300 new order lines")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "landing")
