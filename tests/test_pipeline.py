"""End-to-end checks against ground truth. The thresholds are floors, not the measured values."""
import duckdb


def test_customer_matching_quality(pipeline):
    m = pipeline["metrics"]["mdm"]
    assert m["test_odd_ids"]["precision"] >= 0.99 and m["test_odd_ids"]["recall"] >= 0.97  # held-out half
    assert m["household_false_merges"] == 0  # same surname + address, different person: never merged
    assert m["a_duplicate_store_records_collapsed"] == 635


def test_matches_survive_master_data_changes(pipeline):
    # 50 customers move house on day 2; their links must not be lost
    assert pipeline["metrics"]["mdm"]["all"] == pipeline["day1"]["mdm"]["all"]


def test_currency_conversion_exact_to_the_cent(pipeline):
    fx = pipeline["metrics"]["fx"]
    assert fx["exact_to_the_cent"] == fx["b_lines_in_fact"] and fx["max_abs_diff_usd"] == 0


def test_every_injected_defect_quarantined_and_nothing_else(pipeline):
    d = pipeline["metrics"]["defects"]
    for kind in ("orphan_customer", "invalid_order_date", "missing_currency", "bad_quantity", "duplicate_line"):
        assert d[kind]["caught"] == d[kind]["injected"] > 0, kind
        assert d[kind]["wrongly_flagged"] == 0, kind
    assert d["other_reasons"] == {}


def test_unmapped_parts_land_on_unknown_member(pipeline):
    u = pipeline["metrics"]["unmapped"]
    assert u["lines_on_unmapped_member"] == u["expected"] > 0


def test_incremental_and_history(pipeline):
    d2 = pipeline["metrics"]["day2"]
    assert d2["incremental_ok"] and d2["scd2_matches_moved_customers"] and d2["scd2_closed_versions"] == 50


def test_bi_view_masks_personal_data(pipeline):
    con = duckdb.connect(pipeline["db"], read_only=True)
    leaked = con.execute("""select count(*) from core.dim_customer_masked
        where coalesce(email, '***MASKED***') <> '***MASKED***' or coalesce(customer_name, '***MASKED***') <> '***MASKED***'""").fetchone()[0]
    assert leaked == 0
    assert con.execute("select count(*) from core.dim_customer where email is not null").fetchone()[0] > 0
