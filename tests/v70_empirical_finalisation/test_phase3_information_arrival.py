from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "v70_empirical_finalisation" / "build_phase3_information_arrival.py"
SPEC = ROOT / "config" / "v70" / "phase3_information_arrival_spec.json"

def test_script_compiles():
    py_compile.compile(str(SCRIPT), doraise=True)

def test_frozen_specification():
    data = json.loads(SPEC.read_text())
    assert data["frozen_ref"] == "v2-empirical-complete"
    assert data["expected"]["weather_rows"] == 2920
    assert data["expected"]["weather_dates"] == 730
    assert data["expected"]["gp_rows"] == 2920
    assert data["expected"]["gp_validation_dates"] == 365
    assert data["bootstrap"]["replications"] == 10000
    assert data["bootstrap"]["moving_block_lengths"] == [3, 5, 7]
    assert len(data["transitions"]) == 6
