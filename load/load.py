"""Loads the landing CSVs into the warehouse's RAW layer: one table per file, every column as
text (typing happens in dbt staging, where a bad value becomes a test failure instead of a
failed load), plus _source_file and _loaded_at for lineage.

    python load/load.py duckdb    warehouse/erpbridge.duckdb   # local, used by tests and CI
    python load/load.py snowflake                              # reads SNOWFLAKE_* env vars

Snowflake: files are PUT to an internal stage and loaded with COPY INTO, the standard bulk path.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

LANDING = Path(__file__).resolve().parent.parent / "landing"
SYSTEMS = {"erp_a": "raw_erp_a", "erp_b": "raw_erp_b"}


def files():
    for system, schema in SYSTEMS.items():
        for f in sorted((LANDING / system).glob("*.csv")):
            with open(f, encoding="utf-8") as fh:
                header = next(csv.reader(fh))
            yield schema, f.stem, f, header


def load_duckdb(path: str, delta: str | None = None):
    """Full load replaces each table. With delta=<subdir>, files in landing/<system>/<subdir>/ are
    APPENDED to their tables instead (how daily delta extracts of transactional tables arrive),
    and master-data files at the top level are re-loaded in full."""
    import duckdb
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = duckdb.connect(path)
    if delta:
        for system, schema in SYSTEMS.items():
            ddir = LANDING / system / delta
            for f in sorted(ddir.glob("*.csv")) if ddir.is_dir() else []:
                header = next(csv.reader(open(f, encoding="utf-8")))
                cols = ", ".join(f"'{h}': 'VARCHAR'" for h in header)
                con.execute(f"""insert into {schema}.{f.stem} by name
                    select *, '{delta}/{f.name}' as _source_file, current_timestamp as _loaded_at
                    from read_csv('{f}', header = true, columns = {{{cols}}}, quote = '"', escape = '"')""")
                print(f"{schema}.{f.stem:28s} +{con.execute(f'select count(*) from read_csv({chr(39)}{f}{chr(39)}, header=true)').fetchone()[0]} appended")
        master = {("raw_erp_b", "customer")}
    for schema, table, f, header in files():
        if delta and (schema, table) not in master:
            continue
        con.execute(f"create schema if not exists {schema}")
        cols = ", ".join(f"'{h}': 'VARCHAR'" for h in header)
        con.execute(f"""create or replace table {schema}.{table} as
            select *, '{f.name}' as _source_file, current_timestamp as _loaded_at
            from read_csv('{f}', header = true, columns = {{{cols}}}, quote = '"', escape = '"')""")
        n = con.execute(f"select count(*) from {schema}.{table}").fetchone()[0]
        print(f"{schema}.{table:28s} {n:>8}")
    con.close()


def load_snowflake():
    import snowflake.connector
    con = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        password=os.environ.get("SNOWFLAKE_PASSWORD"), authenticator=os.environ.get("SNOWFLAKE_AUTHENTICATOR", "snowflake"),
        role=os.environ.get("SNOWFLAKE_ROLE", "TRANSFORMER"), warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "TRANSFORMING"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "ERPBRIDGE"))
    cur = con.cursor()
    cur.execute("create file format if not exists public.landing_csv type = csv skip_header = 1 "
                "field_optionally_enclosed_by = '\"' empty_field_as_null = true")
    for schema, table, f, header in files():
        cur.execute(f"create schema if not exists {schema}")
        cur.execute(f"create stage if not exists {schema}.landing file_format = public.landing_csv")
        cols = ", ".join(f'"{h.upper()}" varchar' for h in header)
        cur.execute(f"create or replace table {schema}.{table} ({cols}, _source_file varchar, "
                    f"_loaded_at timestamp_ltz default current_timestamp())")
        cur.execute(f"put 'file://{f.as_posix()}' @{schema}.landing/{table}/ overwrite = true auto_compress = true")
        sel = ", ".join(f"${i + 1}" for i in range(len(header)))
        cur.execute(f"""copy into {schema}.{table} ({", ".join(f'"{h.upper()}"' for h in header)}, _source_file)
                        from (select {sel}, metadata$filename from @{schema}.landing/{table}/)
                        on_error = abort_statement""")
        print(schema, table, cur.fetchall())
    con.close()


if __name__ == "__main__":
    if sys.argv[1] == "duckdb":
        load_duckdb(sys.argv[2] if len(sys.argv) > 2 else "warehouse/erpbridge.duckdb",
                    sys.argv[3] if len(sys.argv) > 3 else None)
    elif sys.argv[1] == "snowflake":
        load_snowflake()
    else:
        raise SystemExit("usage: load.py duckdb [path] | snowflake")
