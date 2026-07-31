from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "v70_empirical_finalisation" / "build_phase4_forecast_attribution.py"
SPEC = ROOT / "config" / "v70" / "phase4_forecast_attribution_spec.json"

def test_script_compiles():
    py_compile.compile(str(SCRIPT), doraise=True)

def test_frozen_specification():
    data = json.loads(SPEC.read_text())
    assert data["frozen_ref"] == "v2-empirical-complete"
    assert data["expected"]["validation_dates"] == 365
    assert data["expected"]["loss_panel_rows"] == 5840
    assert data["expected"]["date_loss_rows"] == 1460
    assert data["bootstrap"]["replications"] == 10000
    assert data["bootstrap"]["moving_block_lengths"] == [3, 5, 7]
    assert data["bootstrap"]["stationary_mean_block_lengths"] == [3, 5, 7]
    assert len(data["contrasts"]) == 6
    assert data["expected"]["chronological_block_sizes"] == [91, 91, 91, 92]
