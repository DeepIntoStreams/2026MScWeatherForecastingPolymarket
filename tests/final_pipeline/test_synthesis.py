from __future__ import annotations

import json
import math
import unittest

from pathlib import Path

import numpy as np
import pandas as pd


SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "synthesis_stage_summary.json"
)

CHECKS = Path(
    "outputs/final_pipeline/audit/"
    "synthesis_stage_integrity_checks.csv"
)

CROSS = Path(
    "outputs/final_pipeline/synthesis/"
    "cross_stage_attribution.csv"
)

RULE = Path(
    "outputs/final_pipeline/synthesis/"
    "rule_support_robustness.csv"
)

THRESHOLD = Path(
    "data/processed/final_pipeline/synthesis/"
    "external_threshold_neighbourhood.csv"
)

MONTHLY = Path(
    "data/processed/final_pipeline/synthesis/"
    "external_monthly_method_performance.csv"
)

TOP = Path(
    "outputs/final_pipeline/synthesis/"
    "external_gp_top_winner_removal.csv"
)

BOOT = Path(
    "outputs/final_pipeline/synthesis/"
    "bootstrap_interpretation.csv"
)

PENDING = Path(
    "outputs/final_pipeline/synthesis/"
    "pending_target_status.json"
)

EVIDENCE = Path(
    "outputs/final_pipeline/synthesis/"
    "thesis_evidence_register.csv"
)

REPRO = Path(
    "outputs/final_pipeline/synthesis/"
    "reproducibility_manifest.csv"
)


class TestSynthesisStage(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls
    ):
        cls.summary = json.loads(
            SUMMARY.read_text()
        )

        cls.checks = pd.read_csv(
            CHECKS
        )

        cls.cross = pd.read_csv(
            CROSS
        )

        cls.rule = pd.read_csv(
            RULE
        )

        cls.threshold = pd.read_csv(
            THRESHOLD
        )

        cls.monthly = pd.read_csv(
            MONTHLY
        )

        cls.top = pd.read_csv(
            TOP
        )

        cls.boot = pd.read_csv(
            BOOT
        )

        cls.pending = json.loads(
            PENDING.read_text()
        )

        cls.evidence = pd.read_csv(
            EVIDENCE
        )

        cls.repro = pd.read_csv(
            REPRO
        )

    def test_stage_pass(
        self
    ):
        self.assertEqual(
            self.summary[
                "status"
            ],
            "PASS",
        )

    def test_upstream_frozen(
        self
    ):
        self.assertTrue(
            self.summary[
                "upstream_steps_1_55_frozen"
            ]
        )

        self.assertEqual(
            self.summary[
                "weather_kernel"
            ],
            "matern32",
        )

        self.assertTrue(
            math.isclose(
                self.summary[
                    "pool_weight_gp"
                ],
                0.188,
                abs_tol=1e-12,
            )
        )

        self.assertEqual(
            self.summary[
                "trading_rule"
            ],
            "24h_prior",
        )

        self.assertTrue(
            math.isclose(
                self.summary[
                    "trading_threshold"
                ],
                0.15,
                abs_tol=1e-12,
            )
        )

    def test_cross_stage_static_share(
        self
    ):
        self.assertEqual(
            len(
                self.cross
            ),
            3,
        )

        self.assertTrue(
            (
                self.cross[
                    "static_share_of_raw_to_gp_improvement"
                ]
                >= 0.90
            ).all()
        )

    def test_support_diagnostic_does_not_replace_policy(
        self
    ):
        primary = self.rule[
            self.rule[
                "selection_basis"
            ]
            == "prespecified_rule_specific_support"
        ]

        common = self.rule[
            self.rule[
                "selection_basis"
            ]
            == "common_all_rule_dates_diagnostic"
        ]

        self.assertEqual(
            len(
                primary
            ),
            1,
        )

        self.assertEqual(
            len(
                common
            ),
            1,
        )

        self.assertEqual(
            primary.iloc[
                0
            ][
                "selected_rule"
            ],
            "24h_prior",
        )

        self.assertTrue(
            (
                self.rule[
                    "changes_frozen_policy"
                ]
                .astype(str)
                .str.lower()
                == "false"
            ).all()
        )

    def test_threshold_baseline(
        self
    ):
        row = self.threshold[
            np.isclose(
                self.threshold[
                    "threshold"
                ],
                0.15,
                atol=1e-12,
            )
        ]

        self.assertEqual(
            len(
                row
            ),
            1,
        )

        self.assertTrue(
            math.isclose(
                float(
                    row.iloc[
                        0
                    ][
                        "total_net_pnl"
                    ]
                ),
                2.451,
                abs_tol=1e-10,
            )
        )

        self.assertFalse(
            bool(
                row.iloc[
                    0
                ][
                    "used_for_selection"
                ]
            )
        )

    def test_monthly_gp_sums(
        self
    ):
        x = self.monthly[
            self.monthly[
                "probability_source"
            ]
            == "selected_gp"
        ]

        self.assertTrue(
            math.isclose(
                float(
                    x[
                        "total_net_pnl"
                    ].sum()
                ),
                2.451,
                abs_tol=1e-10,
            )
        )

    def test_concentration_baseline(
        self
    ):
        row = self.top[
            self.top[
                "largest_positive_trades_removed"
            ]
            == 0
        ]

        self.assertEqual(
            len(
                row
            ),
            1,
        )

        self.assertTrue(
            math.isclose(
                float(
                    row.iloc[
                        0
                    ][
                        "remaining_total_net_pnl"
                    ]
                ),
                2.451,
                abs_tol=1e-10,
            )
        )

    def test_bootstrap_reconciliation(self):
        # Classification must follow the reported interval evidence rather
        # than a hard-coded pre-31-Aug outcome label.
        x = pd.read_csv(
            "outputs/final_pipeline/synthesis/"
            "bootstrap_interpretation.csv"
        )

        gp = x.loc[
            (x["estimand"] == "method_level")
            & (x["source_a"] == "selected_gp")
        ].copy()

        self.assertEqual(
            len(gp),
            1,
        )

        row = gp.iloc[0]

        ordinary_contains_zero = (
            float(row["ordinary_lower_95"])
            <= 0.0
            <= float(row["ordinary_upper_95"])
        )

        block_contains_zero = (
            float(row["block7_lower_95"])
            <= 0.0
            <= float(row["block7_upper_95"])
        )

        classification = str(
            row["classification"]
        )

        if ordinary_contains_zero != block_contains_zero:
            self.assertEqual(
                classification,
                "dependence_sensitive",
            )

        elif ordinary_contains_zero and block_contains_zero:
            self.assertEqual(
                classification,
                "unresolved",
            )

        else:
            self.assertNotIn(
                classification,
                {
                    "dependence_sensitive",
                    "unresolved",
                },
            )

    def test_pending_status(
        self
    ):
        self.assertIn(
            self.pending[
                "pending_dates"
            ],
            [
                [],
                [
                    "2026-08-31"
                ],
            ],
        )

        self.assertFalse(
            self.pending[
                "development_reselection_allowed_after_refresh"
            ]
        )

    def test_evidence_register_has_do_not_use_guards(
        self
    ):
        guarded = self.evidence[
            self.evidence[
                "recommended_location"
            ]
            == "do_not_use_as_primary_claim"
        ]

        self.assertGreaterEqual(
            len(
                guarded
            ),
            2,
        )

    def test_manifest_complete(
        self
    ):
        self.assertTrue(
            (
                self.repro[
                    "exists"
                ]
                .astype(str)
                .str.lower()
                == "true"
            ).all()
        )

        self.assertTrue(
            self.repro[
                "sha256"
            ]
            .astype(str)
            .str.len()
            .eq(
                64
            )
            .all()
        )

    def test_all_integrity_checks(
        self
    ):
        self.assertTrue(
            (
                self.checks[
                    "passed"
                ]
                .astype(str)
                .str.lower()
                == "true"
            ).all()
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
