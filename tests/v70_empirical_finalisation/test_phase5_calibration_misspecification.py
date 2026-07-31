from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "v70_empirical_finalisation"
    / "build_phase5_calibration_misspecification.py"
)
SPEC = (
    ROOT
    / "config"
    / "v70"
    / "phase5_calibration_misspecification_spec.json"
)

def test_script_compiles():
    py_compile.compile(str(SCRIPT), doraise=True)

def test_frozen_specification():
    data = json.loads(SPEC.read_text())
    assert data["frozen_ref"] == "v2-empirical-complete"
    assert data["expected"]["validation_dates"] == 365
    assert data["expected"]["gp_rows"] == 2920
    assert data["expected"]["rows_per_model"] == 1460
    assert data["coverage_levels"] == [0.50, 0.80, 0.90]
    assert data["bootstrap"]["replications"] == 10000
    assert data["bootstrap"]["moving_block_lengths"] == [3, 5, 7, 14]
    assert data["acf_max_lag"] == 14
    assert len(data["phase19_files"]) == 14
