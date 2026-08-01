from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "v70_empirical_finalisation"
    / "build_phase7_trading_sensitivity.py"
)
SPEC = (
    ROOT
    / "config"
    / "v70"
    / "phase7_trading_sensitivity_spec.json"
)

def test_script_compiles():
    py_compile.compile(str(SCRIPT), doraise=True)

def test_frozen_specification():
    data = json.loads(SPEC.read_text())
    assert data["input_paths"]["phase8_market_period_predictions"] == (
        "data/processed/v2/phase8_clean_gp/"
        "phase8_gp_market_period_predictions.csv"
    )
    assert data["expected"]["selected_model"] == "matern"
    assert data["expected"]["selected_rule"] == "event_day_open"
    assert data["expected"]["selected_threshold"] == 0.12
    assert data["expected"]["selected_cost"] == 0.01
    assert data["expected"]["june_selected_trades"] == 16
    assert data["expected"]["june_selected_winning_trades"] == 1
    assert abs(data["expected"]["june_selected_net_pnl"] - 0.0235) < 1e-12
    assert abs(data["expected"]["june_break_even_cost"] - 0.01146875) < 1e-12
    assert data["bootstrap"]["replications"] == 10000
    assert data["bootstrap"]["moving_block_lengths"] == [3, 5, 7]
    assert data["mean_shift_grid_c"] == [
        -1.0, -0.5, -0.25, -0.1, 0.0, 0.1, 0.25, 0.5, 1.0
    ]
