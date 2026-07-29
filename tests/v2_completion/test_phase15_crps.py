from __future__ import annotations

import csv
import math
import unittest
from pathlib import Path


class Phase15CRPSTest(unittest.TestCase):
    def test_crps_registry(self) -> None:
        root = Path(__file__).resolve().parents[2]
        path = root / "outputs/v2_completion/phase15_crps_reconciliation.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        labels = {row["model"] for row in rows}
        self.assertEqual(labels, {"rbf", "matern32"})
        for row in rows:
            self.assertEqual(row["status"], "PASSED")
            self.assertEqual(int(row["rows"]), 1460)
            self.assertEqual(int(row["dates"]), 365)
            self.assertTrue(math.isfinite(float(row["analytic_mean_crps_c"])))
            self.assertTrue(math.isfinite(float(row["stored_mean_crps_c"])))


if __name__ == "__main__":
    unittest.main()
