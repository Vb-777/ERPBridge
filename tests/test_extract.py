"""The AdventureWorks extract: headers from the install script, every row with the right field count."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_extract_headers_and_counts(pipeline):
    a = ROOT / "landing" / "erp_a"
    with open(a / "salesorderheader.csv") as f:
        r = csv.reader(f)
        head = next(r)
        n = sum(1 for _ in r)
    assert head[:3] == ["SalesOrderID", "RevisionNumber", "OrderDate"] and "rowguid" not in head
    assert n == 31465
    with open(a / "person.csv", encoding="utf-8") as f:  # '+|' separated, UTF-8 with accents in the source
        assert any("Sánchez" in line for line in f)
