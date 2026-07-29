from __future__ import annotations

import unittest
from pathlib import Path


class Phase18FigureTest(unittest.TestCase):
    def test_figures_exist(self) -> None:
        root = Path(__file__).resolve().parents[2]
        paths = [
            root
            / "outputs/v2_completion/phase18_figures/"
            / "phase18_matern_crps_rule_block_heatmap.png",
            root
            / "outputs/v2_completion/phase18_figures/"
            / "phase18_matern_crps_rule_block_heatmap.pdf",
            root
            / "outputs/v2_completion/phase18_figures/"
            / "phase18_matern_minus_static_heatmap.png",
            root
            / "outputs/v2_completion/phase18_figures/"
            / "phase18_matern_minus_static_heatmap.pdf",
            root
            / "outputs/v2_completion/phase18_figures/"
            / "phase18_matern_length_scale_stability.png",
            root
            / "outputs/v2_completion/phase18_figures/"
            / "phase18_matern_length_scale_stability.pdf",
        ]
        for path in paths:
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
