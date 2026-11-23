"""Builds the second source system: the ERP of an acquired European business ("ERP B").

ERP B is SYNTHETIC, generated from ERP A (AdventureWorks) with a fixed seed, so that every
hard problem of merging two ERPs has a known right answer to score against:

* Customer master: 1,500 of ERP A's European customers also buy from ERP B, recorded the way a
  different system and different clerks would record them (name order and case, typos,
  abbreviated streets, company-suffix variants, missing or re-cased e-mails, other phone
  formats). 1,200 customers exist only in ERP B, 200 of them deliberately hard: same household
  address and surname as an ERP A customer, but a different person.
* Product master: ERP B sells 150 of ERP A's finished goods under its own part numbers; the
  cross-reference maintained by the MDM team is missing 6 of them.
* Orders: in EUR (DE, FR) and GBP (GB), priced from ERP A's list price at the order date and
  the day's USD rate, so the warehouse's currency conversion can be checked to the cent.
* Defects a real extract contains, at known counts: orphan orders, zero/negative quantities,
  duplicated lines, future-dated orders, missing currency.

Ground truth goes to landing/ground_truth/ and is never loaded into the warehouse; only the
evaluation script reads it.

    python extract/make_erp_b.py landing
"""
from __future__ import annotations

import csv
import json
import random
import sys
from decimal import ROUND_HALF_UP, Decimal
from datetime import date, timedelta
from pathlib import Path

import duckdb

SEED = 20271
N_OVERLAP, N_ONLY, N_HOUSEHOLD, N_PARTS, N_UNMAPPED, N_ORDERS = 1500, 1000, 200, 150, 6, 9000
DEFECTS = {"orphan_customer": 25, "bad_quantity": 40, "duplicate_line": 30, "future_date": 10, "missing_currency": 15}
STREET = {"Street": "St", "Avenue": "Ave", "Drive": "Dr", "Road": "Rd", "Lane": "Ln", "Court": "Ct",
          "Boulevard": "Blvd", "Place": "Pl", "Way": "Wy", "Circle": "Cir"}
SUFFIX = [(" Inc.", " Incorporated"), (" Company", " Co."), (" & ", " and "), ("Corporation", "Corp."), (" Ltd.", " Limited")]


def typo(s: str, r: random.Random) -> str:
    if len(s) < 4:
        return s
    i = r.randrange(1, len(s) - 1)
    op = r.choice("swap drop double".split())
    if op == "swap":
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if op == "drop":
        return s[:i] + s[i + 1:]
    return s[:i] + s[i] + s[i:]


def vary_person(first, last, r):
    style = r.random()
    if style < 0.3:
        name = f"{last.upper()}, {first}"
    elif style < 0.5:
        name = f"{first} {last}".upper()
    elif style < 0.6:
        name = f"{first[0]}. {last}"
    else:
        name = f"{first} {last}"
    if r.random() < 0.25:
        name = typo(name, r)
    if r.random() < 0.15:
        name = "  " + name.replace(" ", "  ", 1)
    return name


def vary_company(name, r):
    for a, b in SUFFIX:
        if a in name and r.random() < 0.7:
            name = name.replace(a, b)
            break
    if name.startswith("The ") and r.random() < 0.5:
        name = name[4:]
    if r.random() < 0.3:
        name = name.upper()
    if r.random() < 0.2:
        name = typo(name, r)
    return name


def vary_address(line, r):
    if r.random() < 0.6:
        for full, ab in STREET.items():
            if line.endswith(" " + full):
                line = line[: -len(full)] + (ab + "." if r.random() < 0.5 else ab)
                break
    if "Straße" in line and r.random() < 0.6:
        line = line.replace("Straße", r.choice(["Str.", "Strasse"]))
    if line.startswith(tuple("0123456789")) is False and " rue " in line and r.random() < 0.4:
        line = line.replace(" rue ", " r. ")
    if r.random() < 0.15:
        line = typo(line, r)
    if r.random() < 0.2:
        line = line.upper()
    return line


def vary_postal(p, r):
    if r.random() < 0.2:
        return p.replace(" ", "") if " " in p else p.lower()
    return p


def vary_phone(p, r):
    digits = "".join(ch for ch in p if ch.isdigit())
    return r.choice([p, digits, f"+1 {digits}", f"({digits[:3]}) {digits[3:6]}-{digits[6:]}" if len(digits) >= 10 else p])


def main(out: str):
    out = Path(out)
    a = out / "erp_a"
    b, gt = out / "erp_b", out / "ground_truth"
    b.mkdir(parents=True, exist_ok=True)
    gt.mkdir(parents=True, exist_ok=True)
    r = random.Random(SEED)
    c = duckdb.connect()
    for t in ("customer", "person", "store", "address", "businessentityaddress", "stateprovince", "emailaddress",
              "personphone", "product", "productlistpricehistory", "currencyrate"):
        c.sql(f"create view {t} as select * from read_csv('{a}/{t}.csv', header=true)")

    # Every European ERP A customer with its name, primary address, e-mail and phone.
    pool = c.sql("""
        with addr as (
            select bea.BusinessEntityID, ad.AddressLine1, ad.City, ad.PostalCode, sp.CountryRegionCode as country,
                   row_number() over (partition by bea.BusinessEntityID order by bea.AddressTypeID) rn
            from businessentityaddress bea join address ad using (AddressID) join stateprovince sp using (StateProvinceID))
        select cu.CustomerID, cu.AccountNumber,
               case when cu.StoreID is null then 'person' else 'company' end as kind,
               p.FirstName, p.LastName, s.Name as company,
               ad.AddressLine1, ad.City, ad.PostalCode, ad.country, e.EmailAddress, ph.PhoneNumber
        from customer cu
        left join person p on p.BusinessEntityID = cu.PersonID
        left join store s on s.BusinessEntityID = cu.StoreID
        join addr ad on ad.BusinessEntityID = coalesce(cu.StoreID, cu.PersonID) and ad.rn = 1
        left join emailaddress e on e.BusinessEntityID = cu.PersonID
        left join personphone ph on ph.BusinessEntityID = cu.PersonID
        where ad.country in ('DE', 'FR', 'GB')
        order by cu.CustomerID""").fetchall()
    cols = ["CustomerID", "AccountNumber", "kind", "FirstName", "LastName", "company", "AddressLine1", "City",
            "PostalCode", "country", "EmailAddress", "PhoneNumber"]
    pool = [dict(zip(cols, row)) for row in pool]
    r.shuffle(pool)
    overlap, rest = pool[:N_OVERLAP], pool[N_OVERLAP:]

    customers, truth = [], []
    cust_no = 100000
    for src in overlap:
        cust_no += r.randint(1, 3)
        if src["kind"] == "company":
            name = vary_company(src["company"], r)
        else:
            name = vary_person(src["FirstName"], src["LastName"], r)
        email = src["EmailAddress"]
        email = None if (email is None or r.random() < 0.4) else (email.upper() if r.random() < 0.3 else email)
        customers.append(dict(CustNum=cust_no, Name=name, Address1=vary_address(src["AddressLine1"], r),
                              City=src["City"] if r.random() > 0.1 else src["City"].upper(),
                              Zip=vary_postal(src["PostalCode"], r), Country=src["country"], EMailAddress=email,
                              PhoneNum=vary_phone(src["PhoneNumber"], r) if src["PhoneNumber"] else None))
        truth.append(dict(CustNum=cust_no, a_customer_id=src["CustomerID"], case="same_customer"))

    # Household hard negatives: same address and surname as an ERP A customer, different first name.
    firsts = sorted({p["FirstName"] for p in pool if p["FirstName"]})
    persons = [p for p in rest if p["kind"] == "person"]
    for src in r.sample(persons, N_HOUSEHOLD):
        cust_no += r.randint(1, 3)
        first = r.choice([f for f in firsts if f[0] != src["FirstName"][0]])
        customers.append(dict(CustNum=cust_no, Name=vary_person(first, src["LastName"], r),
                              Address1=vary_address(src["AddressLine1"], r), City=src["City"],
                              Zip=vary_postal(src["PostalCode"], r), Country=src["country"], EMailAddress=None,
                              PhoneNum=None))
        truth.append(dict(CustNum=cust_no, a_customer_id=None, case="household_not_same_person"))
    # Other B-only customers: name and address drawn from different ERP A records.
    for _ in range(N_ONLY - N_HOUSEHOLD):
        cust_no += r.randint(1, 3)
        x, y = r.sample(rest, 2)
        if x["kind"] == "company":
            name = f"{r.choice(['Alpen', 'Rhein', 'Seine', 'Thames', 'Nord', 'Loire'])} {x['company']}"
        else:
            name = f"{x['FirstName']} {y['LastName'] or 'Meyer'}"
        customers.append(dict(CustNum=cust_no, Name=name, Address1=f"{r.randint(1, 999)} {y['AddressLine1'].split(' ', 1)[-1]}",
                              City=y["City"], Zip=y["PostalCode"], Country=y["country"], EMailAddress=None, PhoneNum=None))
        truth.append(dict(CustNum=cust_no, a_customer_id=None, case="b_only"))
    r.shuffle(customers)

    # Product master and cross-reference.
    prods = c.sql("select ProductID, ProductNumber, Name from product where FinishedGoodsFlag = 1 and ListPrice > 0 "
                  "and SellEndDate is null order by ProductID").fetchall()
    parts = r.sample(prods, N_PARTS)
    part_rows, xref = [], []
    unmapped = set(r.sample(range(N_PARTS), N_UNMAPPED))
    for i, (pid, pnum, pname) in enumerate(parts):
        part = f"EP-{40000 + 7 * i:05d}"
        part_rows.append(dict(PartNum=part, PartDescription=pname.upper() if r.random() < 0.3 else pname, ClassID="FG"))
        if i not in unmapped:
            xref.append(dict(PartNum=part, aw_product_number=pnum))
    part_to_pid = {f"EP-{40000 + 7 * i:05d}": pid for i, (pid, _, _) in enumerate(parts)}

    # Prices and rates at order date.
    lp = {}
    for pid, start, end, price in c.sql("select ProductID, StartDate, EndDate, ListPrice from productlistpricehistory").fetchall():
        lp.setdefault(pid, []).append((start.date(), end.date() if end else date(2099, 1, 1), float(price)))
    cur_price = dict(c.sql("select ProductID, ListPrice from product").fetchall())
    rates = {(d.date(), cc): float(rt) for d, cc, rt in c.sql(
        "select CurrencyRateDate, ToCurrencyCode, AverageRate from currencyrate where ToCurrencyCode in ('EUR','GBP')").fetchall()}

    def list_price(pid, d):
        for s, e, p in lp.get(pid, []):
            if s <= d <= e:
                return p
        return float(cur_price[pid])

    valid_cust = [x["CustNum"] for x in customers]
    country = {x["CustNum"]: x["Country"] for x in customers}
    heads, lines, line_truth = [], [], []
    start = date(2024, 1, 1)
    days = (date(2025, 5, 30) - start).days
    for n in range(N_ORDERS):
        ordnum = 500000 + n
        cust = r.choice(valid_cust)
        d = start + timedelta(days=r.randrange(days + 1))
        ccy = "GBP" if country[cust] == "GB" else "EUR"
        heads.append(dict(OrderNum=ordnum, CustNum=cust, OrderDate=d.isoformat(), CurrencyCode=ccy,
                          PONum=f"PO-{r.randint(10000, 99999)}"))
        for ln in range(1, r.randint(1, 5) + 1):
            part = r.choice(part_rows)["PartNum"]
            qty = r.randint(1, 4)
            disc = r.choice([0, 0, 0, 0.05, 0.10])
            usd = round(list_price(part_to_pid[part], d) * (1 - disc), 4)
            unit = round(usd * rates[(d, ccy)], 2)
            lines.append(dict(OrderNum=ordnum, OrderLine=ln, PartNum=part, OrderQty=qty, UnitPrice=unit, DiscountPct=disc))
            # accounting rounding (half-up on exact decimals), as the warehouse does it
            usd_amt = (Decimal(qty) * Decimal(str(unit)) / Decimal(str(rates[(d, ccy)]))).quantize(Decimal("0.01"), ROUND_HALF_UP)
            line_truth.append(dict(OrderNum=ordnum, OrderLine=ln, usd_amount=str(usd_amt)))

    # Inject defects at known counts.
    defect_rows = []
    for h in r.sample(heads, DEFECTS["orphan_customer"]):
        h["CustNum"] = 999000 + r.randint(0, 999)
        defect_rows.append(dict(kind="orphan_customer", OrderNum=h["OrderNum"]))
    healthy = [h for h in heads if h["CustNum"] < 999000]
    for h in r.sample(healthy, DEFECTS["future_date"]):
        h["OrderDate"] = "2031-" + h["OrderDate"][5:]
        defect_rows.append(dict(kind="future_date", OrderNum=h["OrderNum"]))
    healthy = [h for h in healthy if not h["OrderDate"].startswith("2031")]
    for h in r.sample(healthy, DEFECTS["missing_currency"]):
        h["CurrencyCode"] = ""
        defect_rows.append(dict(kind="missing_currency", OrderNum=h["OrderNum"]))
    bad_heads = {d["OrderNum"] for d in defect_rows}
    clean_lines = [l for l in lines if l["OrderNum"] not in bad_heads]
    for l in r.sample(clean_lines, DEFECTS["bad_quantity"]):
        l["OrderQty"] = r.choice([0, -1, -2, -5])
        defect_rows.append(dict(kind="bad_quantity", OrderNum=l["OrderNum"], OrderLine=l["OrderLine"]))
    bad_qty = {(d["OrderNum"], d.get("OrderLine")) for d in defect_rows if d["kind"] == "bad_quantity"}
    for l in r.sample([l for l in clean_lines if (l["OrderNum"], l["OrderLine"]) not in bad_qty], DEFECTS["duplicate_line"]):
        lines.append(dict(l))
        defect_rows.append(dict(kind="duplicate_line", OrderNum=l["OrderNum"], OrderLine=l["OrderLine"]))
    r.shuffle(lines)

    def write(path, rows, fields=None):
        fields = fields or list(rows[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    write(b / "customer.csv", customers)
    write(b / "part.csv", part_rows)
    write(b / "part_xref.csv", xref)
    write(b / "orderhed.csv", heads)
    write(b / "orderdtl.csv", lines)
    write(gt / "customer_truth.csv", truth)
    write(gt / "line_usd_truth.csv", line_truth)
    write(gt / "defects.csv", defect_rows, ["kind", "OrderNum", "OrderLine"])
    unmapped_parts = [part_rows[i]["PartNum"] for i in sorted(unmapped)]
    json.dump(dict(seed=SEED, defects=DEFECTS, unmapped_parts=unmapped_parts,
                   unmapped_part_lines=sum(1 for l in lines if l["PartNum"] in unmapped_parts)),
              open(gt / "summary.json", "w"), indent=1)
    print(f"customers {len(customers)} (overlap {N_OVERLAP}), parts {len(part_rows)} (xref {len(xref)}), "
          f"orders {len(heads)}, lines {len(lines)}, defects {DEFECTS}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "landing")
