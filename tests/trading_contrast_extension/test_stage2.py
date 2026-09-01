import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


OUT = Path(
    "outputs/trading_contrast_extension/stage2"
)


class TestTradingContrastStage2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (OUT / "stage2_summary.json").read_text()
        )
        cls.panel = pd.read_csv(
            OUT / "canonical_four_model_event_panel.csv.gz"
        )
        cls.fixed = pd.read_csv(
            OUT / "fixed_strategy_daily_ledger.csv"
        )
        cls.taec_pos = pd.read_csv(
            OUT / "taec11_position_ledger.csv.gz"
        )
        cls.taec_daily = pd.read_csv(
            OUT / "taec11_daily_ledger.csv"
        )
        cls.repro = pd.read_csv(
            OUT / "fixed_baseline_reproduction.csv"
        )

    def test_stage_pass(self):
        self.assertEqual(
            self.summary["status"],
            "PASS",
        )

    def test_panel_shape(self):
        self.assertEqual(len(self.panel), 6996)
        self.assertEqual(
            self.panel["event_date"].nunique(),
            163,
        )

    def test_four_models(self):
        for model in [
            "raw",
            "static",
            "rbf",
            "matern32",
        ]:
            self.assertIn(
                f"p_{model}",
                self.panel.columns,
            )

    def test_probabilities_valid(self):
        for model in [
            "raw",
            "static",
            "rbf",
            "matern32",
        ]:
            p = self.panel[f"p_{model}"]
            self.assertTrue(
                ((p >= 0) & (p <= 1)).all()
            )

    def test_probability_mass(self):
        for model in [
            "raw",
            "static",
            "rbf",
            "matern32",
        ]:
            g = (
                self.panel.groupby(
                    ["event_date", "decision_rule"]
                )[f"p_{model}"]
                .sum()
            )

            self.assertTrue(
                np.isclose(
                    g,
                    1.0,
                    atol=5e-6,
                ).all()
            )

    def test_fixed_support(self):
        g = (
            self.fixed.groupby(
                ["empirical_period", "model"]
            )["event_date"]
            .nunique()
        )

        for model in [
            "raw",
            "static",
            "rbf",
            "matern32",
        ]:
            self.assertEqual(
                int(g[("market_development", model)]),
                90,
            )
            self.assertEqual(
                int(g[("external_validation", model)]),
                61,
            )

    def test_baseline_reproduction(self):
        self.assertTrue(
            self.repro["passed"].all()
        )

    def test_taec_support(self):
        g = (
            self.taec_daily.groupby(
                ["empirical_period", "model"]
            )["event_date"]
            .nunique()
        )

        for model in [
            "raw",
            "static",
            "rbf",
            "matern32",
        ]:
            self.assertEqual(
                int(g[("market_development", model)]),
                90,
            )
            self.assertEqual(
                int(g[("external_validation", model)]),
                61,
            )

    def test_taec_max_positions(self):
        self.assertLessEqual(
            int(self.taec_daily["positions"].max()),
            11,
        )

    def test_one_side_per_contract(self):
        self.assertFalse(
            self.taec_pos.duplicated(
                ["event_date", "model", "contract_key"]
            ).any()
        )

    def test_pre_event_exit_only(self):
        self.assertTrue(
            self.taec_pos["exit_rule"].isin(
                ["12h_prior", "6h_prior", "event_day_open"]
            ).all()
        )

    def test_taec_pnl_identity(self):
        direction = np.where(
            self.taec_pos["side"] == "YES",
            1.0,
            -1.0,
        )

        expected = (
            direction
            * (
                self.taec_pos["market_yes_exit"]
                - self.taec_pos["market_entry_yes_24h"]
            )
            - 0.02
        )

        self.assertTrue(
            np.allclose(
                expected,
                self.taec_pos["net_pnl"],
                atol=1e-12,
            )
        )

    def test_no_settlement_term(self):
        self.assertNotIn(
            "realised_event",
            self.taec_pos.columns,
        )

    def test_round_trip_cost(self):
        self.assertTrue(
            np.allclose(
                self.taec_pos["round_trip_cost"],
                0.02,
            )
        )


    def test_rbf_distinct_from_static(self):
        diff = (
            self.panel["p_rbf"].astype(float)
            - self.panel["p_static"].astype(float)
        ).abs()

        self.assertGreater(
            int((diff > 1e-12).sum()),
            0,
        )

        self.assertGreater(
            float(diff.max()),
            1e-12,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
