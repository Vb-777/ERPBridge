import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
AW = os.environ.get("ERPBRIDGE_AW", str(ROOT / "data" / "adventureworks"))
DB = ROOT / "warehouse" / "erpbridge.duckdb"


@pytest.fixture(scope="session")
def pipeline():
    """Runs the whole pipeline once (day 1 and day 2) unless ERPBRIDGE_SKIP_RUN=1 and a warehouse exists."""
    if not (os.environ.get("ERPBRIDGE_SKIP_RUN") == "1" and DB.exists()):
        if not (Path(AW) / "instawdb.sql").exists():
            pytest.skip("AdventureWorks not downloaded: run scripts/fetch_data.sh")
        subprocess.run(["bash", str(ROOT / "run_pipeline.sh"), AW], check=True, capture_output=True)
    import json
    return {"db": str(DB), "metrics": json.load(open(ROOT / "results" / "metrics.json")),
            "day1": json.load(open(ROOT / "results" / "metrics_day1.json"))}
