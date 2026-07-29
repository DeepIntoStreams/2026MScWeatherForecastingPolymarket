from __future__ import annotations

import unittest
from pathlib import Path


class Phase17FigureTest(unittest.TestCase):
    def test_figures_exist(self) -> None:
        root = Path(__file__).resolve().parents[2]
        paths = [
            root
            / "outputs/v2_completion/phase17_figures/"
            / "phase17_rule_error_boxplot.png",
            root
            / "outputs/v2_completion/phase17_figures/"
            / "phase17_rule_error_boxplot.pdf",
            root
            / "outputs/v2_completion/phase17_figures/"
            / "phase17_missing_support_matrix.png",
            root
            / "outputs/v2_completion/phase17_figures/"
            / "phase17_missing_support_matrix.pdf",
        ]
        for path in paths:
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
