import json
from pathlib import Path
import unittest

import pandas as pd


ROOT = Path(".")
OUT = ROOT / "outputs/trading_contrast_extension/stage6"
THESIS = ROOT / "outputs/trading_contrast_extension/thesis"


class TestTradingContrastStage6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (OUT / "stage6_summary.json").read_text()
        )
        cls.claims = pd.read_csv(
            OUT / "thesis_value_pruning_register.csv"
        )

    def test_stage_pass(self):
        self.assertEqual(
            self.summary["status"],
            "PASS",
        )

    def test_no_new_empirical_modelling(self):
        self.assertFalse(
            self.summary[
                "new_empirical_modelling_after_stage5"
            ]
        )

    def test_no_external_reselection(self):
        self.assertFalse(
            self.summary[
                "external_data_used_for_reselection"
            ]
        )

    def test_fixed_policy_unchanged(self):
        self.assertTrue(
            self.summary[
                "primary_fixed_policy_unchanged"
            ]
        )

    def test_taec_is_exploratory(self):
        self.assertIn(
            "exploratory",
            self.summary[
                "taec_policy_status"
            ].lower(),
        )

    def test_claim_destinations(self):
        self.assertTrue(
            set(
                self.claims["destination"]
            ).issubset(
                {
                    "MAIN_RESULTS",
                    "DISCUSSION",
                    "APPENDIX",
                    "DO_NOT_USE_AS_PRIMARY",
                }
            )
        )

    def test_main_discussion_claims_safe(self):
        x = self.claims.loc[
            self.claims["destination"].isin(
                [
                    "MAIN_RESULTS",
                    "DISCUSSION",
                ]
            )
        ]
        self.assertTrue(
            x["safe_use"].all()
        )

    def test_do_not_use_guards(self):
        self.assertGreaterEqual(
            int(
                (
                    self.claims["destination"]
                    == "DO_NOT_USE_AS_PRIMARY"
                ).sum()
            ),
            3,
        )

    def test_numbers_tex_exists(self):
        self.assertTrue(
            (
                THESIS
                / "generated"
                / "numbers.tex"
            ).exists()
        )

    def test_thesis_tables_exist(self):
        self.assertGreaterEqual(
            len(
                list(
                    (
                        THESIS
                        / "tables"
                    ).glob("*.tex")
                )
            ),
            3,
        )

    def test_thesis_figures_exist(self):
        self.assertGreaterEqual(
            len(
                list(
                    (
                        THESIS
                        / "figures"
                    ).glob("*.png")
                )
            ),
            5,
        )

    def test_docs_exist(self):
        for path in [
            "docs/trading_contrast_extension/EXAMINER_README.md",
            "docs/trading_contrast_extension/FINAL_THESIS_HANDOFF.md",
            "docs/trading_contrast_extension/REPRODUCIBILITY_RUNBOOK.md",
            "TRADING_CONTRAST_EXTENSION_STATUS.md",
        ]:
            self.assertTrue(
                Path(path).exists()
            )


    def test_replay_recreates_pre_stage2_generated_state(self):
        script = Path(
            "scripts/trading_contrast_extension/reproduce_extension.sh"
        ).read_text()

        self.assertIn(
            '"$EXT_OUT/stage2"',
            script,
        )
        self.assertIn(
            '"$EXT_OUT/stage6"',
            script,
        )
        self.assertIn(
            '"$EXT_OUT/release"',
            script,
        )
        self.assertIn(
            "PASS: replay starts from Stage-1-only generated extension state.",
            script,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
