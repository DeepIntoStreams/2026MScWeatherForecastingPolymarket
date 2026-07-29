from __future__ import annotations

import csv
import unittest
from pathlib import Path


class Phase15VarianceTest(unittest.TestCase):
    def test_variance_reconciliation(self) -> None:
        root = Path(__file__).resolve().parents[2]
        path = root / "outputs/v2_completion/phase15_variance_reconciliation.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertEqual(row["status"], "PASSED")
            self.assertLess(float(row["mean_abs_difference"]), 1e-10)
            self.assertLess(float(row["variance_abs_difference"]), 1e-10)
            self.assertLess(float(row["noise_identity_abs_difference"]), 1e-10)


if __name__ == "__main__":
    unittest.main()
