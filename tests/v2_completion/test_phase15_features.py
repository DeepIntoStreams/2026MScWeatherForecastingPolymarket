from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


class Phase15FeatureTest(unittest.TestCase):
    def test_feature_reconciliation(self) -> None:
        root = Path(__file__).resolve().parents[2]
        spec = json.loads(
            (root / "config/v2_completion/phase15_gp_implementation_spec.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(spec["status"], "PASSED")
        self.assertEqual(len(spec["features"]["ordered_raw_features"]), 4)
        self.assertEqual(spec["features"]["calendar_time"]["status"], "PASSED")
        self.assertEqual(spec["features"]["seasonality"]["status"], "PASSED")

        path = root / "outputs/v2_completion/phase15_feature_transformations.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 16)
        self.assertEqual({row["decision_rule"] for row in rows}, {
            "24h_prior", "12h_prior", "6h_prior", "event_day_open"
        })
        for row in rows:
            self.assertEqual(row["status"], "PASSED")
            self.assertLess(float(row["max_reconstruction_error"]), 1e-8)


if __name__ == "__main__":
    unittest.main()
