from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "v70_empirical_finalisation" / "build_phase2_settlement_error.py"
SPEC = ROOT / "config" / "v70" / "phase2_settlement_error_spec.json"

def test_script_compiles():
    py_compile.compile(str(SCRIPT), doraise=True)

def test_frozen_specification():
    data = json.loads(SPEC.read_text())
    assert data["frozen_ref"] == "v2-empirical-complete"
    assert data["expected"]["rows"] == 2920
    assert data["expected"]["dates"] == 730
    assert data["bootstrap"]["replications"] == 10000
    assert data["bootstrap"]["moving_block_lengths"] == [3, 5, 7]
    assert data["bootstrap"]["seed"] == 20260731
