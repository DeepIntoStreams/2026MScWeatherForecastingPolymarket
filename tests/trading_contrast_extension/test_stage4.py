import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


OUT = Path(
    "outputs/trading_contrast_extension/stage4"
)


class TestTradingContrastStage4(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (
                OUT
                / "stage4_summary.json"
            ).read_text()
        )

        cls.panel = pd.read_csv(
            OUT
            / "external_common_support_daily_panel.csv"
        )

        cls.profit = pd.read_csv(
            OUT
            / "portfolio_profitability_inference.csv"
        )

        cls.pairwise = pd.read_csv(
            OUT
            / "within_strategy_model_pairwise_inference.csv"
        )

        cls.strategy = pd.read_csv(
            OUT
            / "taec_vs_fixed_inference.csv"
        )

        cls.sharpe = pd.read_csv(
            OUT
            / "sharpe_strategy_difference_inference.csv"
        )

        cls.conv = pd.read_csv(
            OUT
            / "market_convergence_inference.csv"
        )

        cls.risk = pd.read_csv(
            OUT
            / "risk_metric_bootstrap_intervals.csv"
        )

        cls.recon = pd.read_csv(
            OUT
            / "stage3_stage4_risk_reconciliation.csv"
        )

    def test_stage_pass(self):
        self.assertEqual(
            self.summary["status"],
            "PASS",
        )

    def test_common_support(self):
        self.assertEqual(
            self.panel[
                "event_date"
            ].nunique(),
            61,
        )

        self.assertEqual(
            len(
                self.panel
            ),
            488,
        )

    def test_profitability_family_size(self):
        self.assertEqual(
            len(
                self.profit
            ),
            8,
        )

    def test_pairwise_family_size(self):
        g = (
            self.pairwise.groupby(
                "holm_subfamily"
            )
            .size()
            .to_dict()
        )

        self.assertEqual(
            g,
            {
                "fixed_settlement":
                    6,
                "taec11":
                    6,
            },
        )

    def test_strategy_family_size(self):
        self.assertEqual(
            len(
                self.strategy
            ),
            4,
        )

    def test_sharpe_family_size(self):
        self.assertEqual(
            len(
                self.sharpe
            ),
            4,
        )

    def test_convergence_family_size(self):
        self.assertEqual(
            len(
                self.conv
            ),
            4,
        )

    def test_holm_values_valid(self):
        for x in [
            self.profit,
            self.pairwise,
            self.strategy,
            self.sharpe,
            self.conv,
        ]:
            self.assertTrue(
                x[
                    "holm_p_two_sided"
                ].between(
                    0,
                    1,
                ).all()
            )

    def test_holm_not_below_raw_p(self):
        for x in [
            self.profit,
            self.pairwise,
            self.strategy,
            self.sharpe,
            self.conv,
        ]:
            self.assertTrue(
                (
                    x[
                        "holm_p_two_sided"
                    ]
                    + 1e-15
                    >= x[
                        "mbb_p_two_sided"
                    ]
                ).all()
            )

    def test_risk_interval_count(self):
        # 8 portfolios x 9 metrics x 2 bootstrap methods
        self.assertEqual(
            len(
                self.risk
            ),
            8
            * 9
            * 2,
        )

    def test_stage3_reconciliation(self):
        self.assertTrue(
            self.recon[
                "passed"
            ].all()
        )

        self.assertLessEqual(
            float(
                self.recon[
                    "absolute_difference"
                ].max()
            ),
            1e-10,
        )

    def test_primary_bootstrap_metadata(self):
        self.assertEqual(
            self.summary[
                "bootstrap_repetitions"
            ],
            10000,
        )

        self.assertEqual(
            self.summary[
                "sampling_unit"
            ],
            "settlement_date",
        )

    def test_external_only(self):
        self.assertEqual(
            set(
                self.panel[
                    "empirical_period"
                ]
            ),
            {
                "external_validation",
            },
        )

    def test_figures_exist(self):
        for filename in [
            "external_profitability_mbb_intervals.png",
            "external_taec_minus_fixed_mbb_intervals.png",
            "external_taec_precost_convergence_mbb_intervals.png",
        ]:
            self.assertTrue(
                (
                    OUT
                    / filename
                ).exists()
            )


    def test_mean_test_ci_pvalue_coherence(self):
        frames = [
            self.profit,
            self.pairwise,
            self.strategy,
            self.conv,
        ]

        for x in frames:
            for _, row in x.iterrows():
                p = float(
                    row[
                        "mbb_p_two_sided"
                    ]
                )

                lo = float(
                    row[
                        "mbb_ci95_total_lower"
                    ]
                )

                hi = float(
                    row[
                        "mbb_ci95_total_upper"
                    ]
                )

                excludes_zero = (
                    lo > 0
                    or hi < 0
                )

                if p < 0.05:
                    self.assertTrue(
                        excludes_zero
                    )
                else:
                    self.assertFalse(
                        excludes_zero
                    )

    def test_dependence_sensitive_claim_wording(self):
        claims = pd.read_csv(
            OUT
            / "stage4_inference_claims_register.csv"
        )

        sensitive = claims.loc[
            claims[
                "dependence_sensitive_5pct"
            ]
        ]

        for _, row in sensitive.iterrows():
            self.assertIn(
                "dependence-sensitive",
                str(
                    row[
                        "interpretation"
                    ]
                ).lower(),
            )

    def test_pairwise_claims_have_strategy_context(self):
        claims = pd.read_csv(
            OUT
            / "stage4_inference_claims_register.csv"
        )

        pairwise = claims.loc[
            claims[
                "family"
            ]
            == "within_strategy_model_pairwise"
        ]

        self.assertTrue(
            pairwise[
                "comparison"
            ].str.startswith(
                (
                    "fixed_settlement:",
                    "taec11:",
                )
            ).all()
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
