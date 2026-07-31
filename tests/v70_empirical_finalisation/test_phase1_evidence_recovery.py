from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "v70_empirical_finalisation" / "build_phase1_evidence_recovery.py"
SPEC = ROOT / "config" / "v70" / "phase1_evidence_recovery_spec.json"

def test_script_compiles():
    py_compile.compile(str(SCRIPT), doraise=True)

def test_spec_has_frozen_boundary():
    data = json.loads(SPEC.read_text())
    assert data["frozen_ref"] == "v2-empirical-complete"
    assert data["expected"]["weather_rows"] == 2920
    assert data["expected"]["phase10_event_rows"] == 3850
    assert data["expected"]["events_per_book"] == 11
