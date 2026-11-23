"""Static HTML dashboard over the marts, built the way a BI tool would read them: customers only
through the PII-masked view. Writes dashboard/erpbridge_dashboard.html.

    python dashboard/build.py warehouse/erpbridge.duckdb
"""
from __future__ import annotations

import base64
import html
import io
import json
import sys
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
BLUE, ORANGE, GREY = "#2563eb", "#d97706", "#6b7280"


def png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main(db: str):
    con = duckdb.connect(db, read_only=True)
    q = lambda s: con.execute(s).fetchall()
    rev = q("""select date_trunc('month', order_date) m, source_system, sum(net_amount_usd)
               from core.fct_sales_order_line
               where order_date < (select date_trunc('month', max(order_date)) from core.fct_sales_order_line)  -- complete months only
               group by 1, 2 order by 1""")
    fig, ax = plt.subplots(figsize=(7.5, 3))
    for s, col, lab in (("A", BLUE, "ERP A"), ("B", ORANGE, "ERP B (acquired)")):
        pts = [(m, float(v)) for m, src, v in rev if src == s]
        ax.plot([p[0] for p in pts], [p[1] / 1e6 for p in pts], color=col, label=lab, lw=1.8)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y")); fig.autofmt_xdate()
    ax.set_ylabel("revenue (USD m)"); ax.legend(frameon=False); ax.grid(alpha=.3); ax.spines[["top", "right"]].set_visible(False)
    rev_png = png(fig)

    cat = q("""select p.category, sum(f.net_amount_usd), sum(f.gross_margin_usd)
               from core.fct_sales_order_line f join core.dim_product p using (product_key)
               where f.cost_basis <> 'unmapped_product' group by 1 order by 2 desc""")
    fig, ax = plt.subplots(figsize=(7.5, 2.6))
    ax.barh([c for c, _, _ in cat][::-1], [100 * float(m) / float(r) for _, r, m in cat][::-1], color=BLUE)
    ax.set_xlabel("gross margin %"); ax.grid(axis="x", alpha=.3); ax.spines[["top", "right"]].set_visible(False)
    cat_png = png(fig)

    kpi = q("""select sum(net_amount_usd), sum(gross_margin_usd) filter (where cost_basis <> 'unmapped_product'),
                      sum(net_amount_usd) filter (where cost_basis <> 'unmapped_product'), count(*)
               from core.fct_sales_order_line""")[0]
    shared = q("select count(*) from core.dim_customer_masked where source_systems = 'A+B'")[0][0]
    top = q("""select c.company_name, c.country_code, sum(f.net_amount_usd) filter (where f.source_system = 'A'),
                      sum(f.net_amount_usd) filter (where f.source_system = 'B')
               from core.fct_sales_order_line f join core.dim_customer_masked c using (customer_key)
               where c.source_systems = 'A+B' and c.company_name is not null
               group by 1, 2 order by sum(f.net_amount_usd) desc limit 8""")
    dq = q("select measure, value from quality.dq_summary order by measure")
    sample = q("select customer_key, customer_name, email, city from core.dim_customer_masked where source_systems = 'A+B' limit 3")
    m = json.load(open(ROOT / "results" / "metrics.json"))

    e = html.escape
    rows = lambda rs: "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in rs)
    money = lambda v: f"${float(v) / 1e6:,.1f}m"
    kusd = lambda v: f"${float(v) / 1e3:,.1f}k"
    out = f"""<!doctype html><html><head><meta charset="utf-8"><title>ERPBridge - sales across both ERPs</title>
<style>body{{font-family:system-ui,sans-serif;max-width:980px;margin:24px auto;color:#111;padding:0 16px}}
.k{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.k div{{border:1px solid #e5e7eb;border-radius:8px;padding:10px}}
.k b{{font-size:22px;display:block}}h2{{font-size:16px;margin-top:28px}}table{{border-collapse:collapse;font-size:13px;width:100%}}
td,th{{border-bottom:1px solid #eee;padding:4px 6px;text-align:left}}small{{color:#555}}</style></head><body>
<h1>ERPBridge: sales across ERP A and the acquired ERP B</h1>
<small>Built from the dbt marts; customer fields read through the PII-masked view, as a BI tool would.</small>
<div class="k"><div><b>{money(kpi[0])}</b>revenue, both ERPs</div><div><b>{100 * float(kpi[1]) / float(kpi[2]):.1f}%</b>gross margin (mapped products)</div>
<div><b>{shared:,}</b>customers found in both ERPs</div><div><b>{m['mdm']['all']['precision']:.1%} / {m['mdm']['all']['recall']:.1%}</b>match precision / recall</div></div>
<h2>Monthly revenue by source ERP (USD, complete months)</h2><img src="{rev_png}" width="100%">
<h2>Gross margin by product category</h2><img src="{cat_png}" width="100%">
<h2>Largest customers shared by both ERPs</h2>
<table><tr><th>company</th><th>country</th><th>ERP A revenue</th><th>ERP B revenue</th></tr>
{"".join(f"<tr><td>{e(n)}</td><td>{c}</td><td>{kusd(a or 0)}</td><td>{kusd(b or 0)}</td></tr>" for n, c, a, b in top)}</table>
<h2>Data quality</h2><table><tr><th>measure</th><th>value</th></tr>{rows(dq)}</table>
<h2>What a BI user sees for personal data</h2><table><tr><th>customer_key</th><th>customer_name</th><th>email</th><th>city</th></tr>{rows(sample)}</table>
</body></html>"""
    (ROOT / "dashboard" / "erpbridge_dashboard.html").write_text(out, encoding="utf-8")
    print("wrote dashboard/erpbridge_dashboard.html")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "warehouse" / "erpbridge.duckdb"))
