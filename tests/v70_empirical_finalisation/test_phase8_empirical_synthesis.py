from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "v70_empirical_finalisation"
    / "build_phase8_empirical_synthesis.py"
)
SPEC = (
    ROOT
    / "config"
    / "v70"
    / "phase8_empirical_synthesis_spec.json"
)


def test_script_compiles():
    py_compile.compile(str(SCRIPT), doraise=True)


def test_specification_is_frozen():
    data = json.loads(SPEC.read_text())
    assert data["phase"] == "phase8_final_empirical_synthesis"
    assert data["expected"]["weather_dates"] == 730
    assert data["expected"]["exact_support_dates"] == 97
    assert data["expected"]["exact_support_books"] == 350
    assert data["expected"]["selected_rule"] == "event_day_open"
    assert data["expected"]["selected_threshold"] == 0.12
    assert data["expected"]["selected_cost"] == 0.01
    assert data["expected"]["june_trade_count"] == 16
    assert data["expected"]["june_winning_trades"] == 1
    assert abs(data["expected"]["june_net_pnl"] - 0.0235) < 1e-12
    assert len(data["figure_shortlist"]) == 7
    assert len(data["no_refit_boundary"]) >= 6
