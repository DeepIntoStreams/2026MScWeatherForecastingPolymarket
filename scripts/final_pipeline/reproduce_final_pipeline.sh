#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-audit}"

run_tests() {
    for TEST in tests/final_pipeline/test_*.py; do
        python3 "$TEST"
    done
}

case "$MODE" in

    audit)
        echo "=== FINAL PIPELINE AUDIT REPLAY ==="

        python3 -m json.tool \
            config/final_empirical_config.json \
            >/dev/null

        python3 -m src.final_pipeline.release

        run_tests

        if [ -n "$(git status --porcelain)" ]; then
            echo "ERROR: deterministic audit replay changed repository files."
            git status --short
            exit 1
        fi

        echo "PASS: deterministic audit replay."
        ;;

    full)
        echo "=== FULL FINAL PIPELINE REBUILD ==="
        echo "This mode may require live external data endpoints."

        python3 -m src.final_pipeline.hko --refresh
        python3 -m src.final_pipeline.ecmwf
        python3 -m src.final_pipeline.residuals
        python3 -m src.final_pipeline.weather_models
        python3 -m src.final_pipeline.market_books
        python3 -m src.final_pipeline.trading
        python3 -m src.final_pipeline.synthesis
        python3 -m src.final_pipeline.reporting
        python3 -m src.final_pipeline.release

        run_tests

        echo "PASS: full final-pipeline rebuild."
        ;;

    *)
        echo "Usage:"
        echo "  $0 audit"
        echo "  $0 full"
        exit 2
        ;;
esac
