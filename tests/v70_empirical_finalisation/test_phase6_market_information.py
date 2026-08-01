from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "v70_empirical_finalisation"
    / "build_phase6_market_information.py"
)
SPEC = (
    ROOT
    / "config"
    / "v70"
    / "phase6_market_information_spec.json"
)

def test_script_compiles():
    py_compile.compile(str(SCRIPT), doraise=True)

def test_frozen_specification():
    data = json.loads(SPEC.read_text())
    assert data["frozen_ref"] == "v2-empirical-complete"
    assert data["expected"]["exact_support_dates"] == 97
    assert data["expected"]["exact_support_books"] == 350
    assert data["expected"]["event_rows_per_model"] == 3850
    assert data["expected"]["events_per_book"] == 11
    assert data["expected"]["development_dates"] == 67
    assert data["expected"]["june_external_dates"] == 30
    assert data["input_paths"]["frozen_exact_support_panel"] == (
        "outputs/v2_completion/"
        "phase20_exact_common_support_event_panel.csv"
    )
    assert data["input_paths"]["phase1_existing_event_books"].endswith(
        "phase1_canonical_existing_event_books.csv.gz"
    )
    assert abs(
        data["june_reference_model_minus_market"]["binary_brier"]
        - 0.009323867184877032
    ) < 1e-12
    assert abs(
        data["june_reference_model_minus_market"]["binary_log"]
        - 0.03862806151631949
    ) < 1e-12
    assert abs(
        data["legacy_june_reference_model_minus_market"]["binary_brier"]
        - 0.009246327
    ) < 1e-12
    assert data["bootstrap"]["replications"] == 10000
    assert data["bootstrap"]["moving_block_lengths"] == [3, 5, 7]
    assert len(data["transitions"]) == 4
