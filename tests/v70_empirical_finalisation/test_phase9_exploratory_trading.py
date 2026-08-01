from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "tools" / "v70_empirical_finalisation" / "phase9_core.py"
SEARCH = ROOT / "tools" / "v70_empirical_finalisation" / "phase9_search.py"
SCRIPT = ROOT / "tools" / "v70_empirical_finalisation" / "build_phase9_exploratory_trading.py"
SPEC = ROOT / "config" / "v70" / "phase9_exploratory_trading_spec.json"


def test_scripts_compile():
    for path in [CORE, SEARCH, SCRIPT]:
        py_compile.compile(str(path), doraise=True)


def test_specification():
    data = json.loads(SPEC.read_text())
    assert data["working_branch"] == "edward-v70-empirical-finalisation"
    assert data["frozen_tag"] == "v70-empirical-synthesis-complete"
    assert data["primary_cost"] == 0.01
    assert data["validation"]["outer_initial_dates"] == 37
    assert data["validation"]["outer_blocks"] == 5
    assert data["validation"]["outer_block_dates"] == 12
    assert data["primary_selection_objective"] == "robust_sharpe"
    assert "long_short" in data["side_modes"]
    assert 11 in data["selection_counts"]
    assert "quarter_kelly" in data["sizing_rules"]
    assert "robust_0.25c" in data["stability_filters"]
