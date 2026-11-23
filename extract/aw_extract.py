"""Turns Microsoft's AdventureWorks OLTP sample (a bicycle manufacturer's ERP database: sales,
purchasing, production, inventory) into the kind of extract an ERP export job lands: one
UTF-8 CSV per table, with a header row.

The sample ships as headerless files in three different layouts (tab-separated, '+|' / '&|'
separated, UTF-16); the column names and layouts are taken from the CREATE TABLE and BULK INSERT
statements in its own install script, and every row is checked to have the right field count.

    python extract/aw_extract.py <unzipped AdventureWorks dir> landing/erp_a
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

TABLES = [
    "Sales.SalesOrderHeader", "Sales.SalesOrderDetail", "Sales.Customer", "Sales.Store",
    "Sales.SalesTerritory", "Sales.CurrencyRate", "Sales.SpecialOffer",
    "Person.Person", "Person.EmailAddress", "Person.PersonPhone", "Person.Address",
    "Person.BusinessEntityAddress", "Person.AddressType", "Person.StateProvince", "Person.CountryRegion",
    "Production.Product", "Production.ProductSubcategory", "Production.ProductCategory",
    "Production.ProductCostHistory", "Production.ProductListPriceHistory", "Production.ProductInventory",
    "Production.Location", "Production.WorkOrder", "Production.ScrapReason",
    "Purchasing.PurchaseOrderHeader", "Purchasing.PurchaseOrderDetail", "Purchasing.Vendor", "Purchasing.ShipMethod",
]
DROP = {"rowguid", "Demographics", "AdditionalContactInfo", "SpatialLocation", "Demographics"}


def parse_script(sql: str):
    cols, fmt = {}, {}
    for m in re.finditer(r"CREATE TABLE \[(\w+)\]\.\[(\w+)\]\((.*?)\n\) ON", sql, re.S):
        names = []
        for line in m.group(3).splitlines():
            c = re.match(r"\s*\[(\w+)\]", line)
            if c:
                names.append(c.group(1))
        cols[f"{m.group(1)}.{m.group(2)}"] = names
    for m in re.finditer(r"BULK INSERT \[(\w+)\]\.\[(\w+)\] FROM '\$\(SqlSamplesSourceDataPath\)(\w+)\.csv'(.*?)\);", sql, re.S):
        opts = m.group(4)
        ft = re.search(r"FIELDTERMINATOR\s*=\s*'([^']*)'", opts).group(1)
        rt = re.search(r"ROWTERMINATOR\s*=\s*'([^']*)'", opts).group(1)
        wide = "widechar" in opts
        fmt[f"{m.group(1)}.{m.group(2)}"] = (m.group(3), ft, rt, wide)
    return cols, fmt


def read_rows(path: Path, ft: str, rt: str, wide: bool):
    raw = path.read_bytes()
    text = raw.decode("utf-16") if wide or raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    ft = "\t" if ft == "\\t" else ft
    rt = {"0x0a": "\n", "\\n": "\n"}.get(rt, rt.replace("\\n", "\n"))
    rows = text.split(rt)
    if rows and rows[-1].strip() == "":
        rows = rows[:-1]
    return [r.rstrip("\r").split(ft) for r in rows]


def main(src: str, out: str):
    src, out = Path(src), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cols, fmt = parse_script((src / "instawdb.sql").read_text(encoding="utf-8-sig"))
    for t in TABLES:
        fname, ft, rt, wide = fmt[t]
        names = cols[t]
        rows = read_rows(src / f"{fname}.csv", ft, rt, wide)
        bad = [i for i, r in enumerate(rows) if len(r) != len(names)]
        if bad:
            raise SystemExit(f"{t}: {len(bad)} rows have != {len(names)} fields (first: row {bad[0]}, {len(rows[bad[0]])})")
        keep = [i for i, n in enumerate(names) if n not in DROP]
        with open(out / f"{t.split('.')[1].lower()}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([names[i] for i in keep])
            for r in rows:
                w.writerow([r[i] for i in keep])
        print(f"{t:40s} {len(rows):>7} rows", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
