from __future__ import annotations

import json
import unittest

from pathlib import Path

import numpy as np
import pandas as pd


UNIVERSE = Path(
    "data/processed/final_pipeline/market/"
    "polymarket_contract_universe.csv"
)

TARGETS = Path(
    "data/processed/final_pipeline/market/"
    "polymarket_contract_targets.csv"
)

SNAPSHOTS = Path(
    "data/processed/final_pipeline/market/"
    "polymarket_decision_snapshots.csv.gz"
)

WEATHER = Path(
    "data/processed/final_pipeline/market/"
    "weather_event_probabilities.csv.gz"
)

COMMON = Path(
    "data/processed/final_pipeline/market/"
    "exact_common_event_panel.csv.gz"
)

BOOKS = Path(
    "data/processed/final_pipeline/market/"
    "exact_common_book_metrics.csv"
)

SCORES = Path(
    "outputs/final_pipeline/market/"
    "exact_support_score_summary.csv"
)

TV = Path(
    "outputs/final_pipeline/market/"
    "total_variation_summary.csv"
)

POOL = Path(
    "outputs/final_pipeline/market/"
    "convex_pool_selection.json"
)

SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "market_stage_summary.json"
)

CHECKS = Path(
    "outputs/final_pipeline/audit/"
    "market_stage_integrity_checks.csv"
)


class TestFinalMarketStage(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):
        cls.universe = (
            pd.read_csv(
                UNIVERSE
            )
        )

        cls.targets = pd.read_csv(
            TARGETS
        )

        cls.snapshots = (
            pd.read_csv(
                SNAPSHOTS
            )
        )

        cls.weather = pd.read_csv(
            WEATHER
        )

        cls.common = pd.read_csv(
            COMMON
        )

        cls.books = pd.read_csv(
            BOOKS
        )

        cls.scores = pd.read_csv(
            SCORES
        )

        cls.tv = pd.read_csv(
            TV
        )

        cls.pool = json.loads(
            POOL.read_text()
        )

        cls.summary = json.loads(
            SUMMARY.read_text()
        )

        cls.checks = pd.read_csv(
            CHECKS
        )

    def test_summary_pass(self):
        self.assertEqual(
            self.summary[
                "status"
            ],
            "PASS",
        )

    def test_every_certified_date_has_11_contracts(self):
        counts = (
            self.universe.groupby(
                "event_date"
            )
            .size()
        )

        self.assertTrue(
            counts.eq(
                11
            ).all()
        )

    def test_event_type_structure(self):
        for _, g in (
            self.universe.groupby(
                "event_date"
            )
        ):
            counts = (
                g[
                    "contract_event_type"
                ]
                .value_counts()
                .to_dict()
            )

            self.assertEqual(
                counts.get(
                    "lower_tail_endpoint"
                ),
                1,
            )

            self.assertEqual(
                counts.get(
                    "interior_bin"
                ),
                9,
            )

            self.assertEqual(
                counts.get(
                    "upper_tail"
                ),
                1,
            )

    def test_known_targets_have_one_winner(self):
        x = self.targets[
            self.targets[
                "target_available"
            ].astype(str)
            .str.lower()
            .eq(
                "true"
            )
        ]

        counts = (
            x.groupby(
                "event_date"
            )[
                "Y"
            ]
            .sum()
        )

        self.assertTrue(
            counts.eq(
                1
            ).all()
        )

    def test_no_lookahead(self):
        x = self.snapshots[
            self.snapshots[
                "market_price_available"
            ].astype(str)
            .str.lower()
            .eq(
                "true"
            )
        ]

        selected = pd.to_datetime(
            x[
                "selected_price_timestamp_utc"
            ],
            utc=True,
        )

        cutoff = pd.to_datetime(
            x[
                "decision_cutoff_utc"
            ],
            utc=True,
        )

        self.assertTrue(
            (
                selected
                <= cutoff
            ).all()
        )

        self.assertTrue(
            (
                x[
                    "record_age_hours"
                ]
                >= -1e-10
            ).all()
        )

    def test_market_prices_valid(self):
        x = self.snapshots[
            self.snapshots[
                "market_price_available"
            ].astype(str)
            .str.lower()
            .eq(
                "true"
            )
        ]

        self.assertTrue(
            x[
                "market_raw_yes"
            ].between(
                0,
                1,
            ).all()
        )

    def test_weather_probability_mass(self):
        sums = (
            self.weather.groupby(
                [
                    "event_date",
                    "decision_rule",
                ]
            )[
                [
                    "p_raw",
                    "p_static",
                    "p_selected_gp",
                ]
            ]
            .sum()
        )

        error = np.max(
            np.abs(
                sums.to_numpy()
                - 1.0
            )
        )

        self.assertLess(
            float(
                error
            ),
            1e-9,
        )

    def test_exact_books_are_complete(self):
        counts = (
            self.common.groupby(
                [
                    "event_date",
                    "decision_rule",
                ]
            )
            .size()
        )

        self.assertTrue(
            counts.eq(
                11
            ).all()
        )

    def test_external_support_exists(self):
        self.assertTrue(
            (
                self.common[
                    "empirical_period"
                ]
                == "external_validation"
            ).any()
        )

    def test_pool_selected_on_development_only(self):
        self.assertFalse(
            self.pool[
                "external_validation_used"
            ]
        )

        self.assertFalse(
            self.pool[
                "trading_pnl_used"
            ]
        )

        self.assertGreaterEqual(
            self.pool[
                "weight_gp"
            ],
            0.0,
        )

        self.assertLessEqual(
            self.pool[
                "weight_gp"
            ],
            1.0,
        )

    def test_external_score_rows_exist(self):
        self.assertTrue(
            (
                self.scores[
                    "analysis_period"
                ]
                == "external_validation"
            ).any()
        )

    def test_total_variation_sources_exist(self):
        sources = set(
            self.tv[
                "source"
            ]
        )

        self.assertTrue(
            {
                "raw",
                "static",
                "selected_gp",
            }.issubset(
                sources
            )
        )

    def test_integrity_checks_pass(self):
        passed = (
            self.checks[
                "passed"
            ]
            .astype(str)
            .str.lower()
            .eq(
                "true"
            )
        )

        self.assertTrue(
            passed.all()
        )




class TestChronologyResolution(unittest.TestCase):

    def test_may19_chronology_resolution(self):
        import pandas as pd
        from pathlib import Path

        universe = pd.read_csv(
            Path(
                "data/processed/final_pipeline/market/"
                "polymarket_contract_universe.csv"
            ),
            dtype={
                "parent_event_id":
                    "string",

                "market_id":
                    "string",
            },
        )

        audit = pd.read_csv(
            Path(
                "outputs/final_pipeline/market/"
                "contract_book_chronology_audit.csv"
            ),
            dtype={
                "parent_event_id":
                    "string",
            },
        )

        dates = set(
            universe[
                "event_date"
            ].astype(str)
        )

        expected = set(
            pd.date_range(
                "2026-03-16",
                "2026-08-31",
            ).strftime(
                "%Y-%m-%d"
            )
        )

        self.assertEqual(
            expected - dates,
            {
                "2026-03-20",
                "2026-03-31",
            },
        )

        self.assertEqual(
            len(
                dates
            ),
            167,
        )

        may = universe[
            universe[
                "event_date"
            ]
            .astype(str)
            .eq(
                "2026-05-19"
            )
        ]

        self.assertEqual(
            len(
                may
            ),
            11,
        )

        self.assertEqual(
            set(
                may[
                    "parent_event_id"
                ].astype(str)
            ),
            {
                "493669"
            },
        )

        self.assertEqual(
            set(
                may[
                    "market_id"
                ].astype(int)
            ),
            set(
                range(
                    2281866,
                    2281877,
                )
            ),
        )

        may_audit = audit[
            audit[
                "event_date"
            ]
            .astype(str)
            .eq(
                "2026-05-19"
            )
        ]

        selected = may_audit[
            may_audit[
                "selected"
            ]
            .astype(str)
            .str.lower()
            .eq(
                "true"
            )
        ]

        self.assertEqual(
            len(
                selected
            ),
            1,
        )

        self.assertEqual(
            str(
                selected.iloc[0][
                    "parent_event_id"
                ]
            ),
            "493669",
        )

        late = may_audit[
            may_audit[
                "parent_event_id"
            ]
            .astype(str)
            .eq(
                "503637"
            )
        ]

        self.assertEqual(
            len(
                late
            ),
            1,
        )

        self.assertEqual(
            str(
                late.iloc[0][
                    "created_by_event_day_open"
                ]
            ).lower(),
            "false",
        )



if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
