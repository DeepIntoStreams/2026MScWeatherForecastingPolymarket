from __future__ import annotations

import csv
import json
import unittest

from datetime import (
    date,
    datetime,
    timedelta,
)

from pathlib import Path


PANEL = Path(
    "data/processed/final_pipeline/"
    "ecmwf_deterministic_forecasts.csv"
)

SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "ecmwf_summary.json"
)

RECON = Path(
    "outputs/final_pipeline/audit/"
    "ecmwf_historical_reconciliation.csv"
)


def parse_dt(value: str):
    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


class TestFinalECMWF(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with PANEL.open(
            encoding="utf-8",
            newline="",
        ) as f:
            cls.rows = list(
                csv.DictReader(f)
            )

        cls.summary = json.loads(
            SUMMARY.read_text()
        )

    def test_target_dates(self):
        self.assertEqual(
            len(
                {
                    r["target_date"]
                    for r in self.rows
                }
            ),
            899,
        )

    def test_four_rules_every_date(self):
        self.assertEqual(
            len(self.rows),
            899 * 4,
        )

        keys = [
            (
                r["target_date"],
                r["decision_rule"],
            )
            for r in self.rows
        ]

        self.assertEqual(
            len(keys),
            len(set(keys)),
        )

    def test_issue_time_no_lookahead(self):
        for r in self.rows:
            if (
                r["support_available"]
                != "True"
            ):
                continue

            issue = parse_dt(
                r["selected_run_init_utc"]
            )

            decision = parse_dt(
                r["decision_time_utc"]
            )

            self.assertLessEqual(
                issue,
                decision,
            )

    def test_six_hour_allowance(self):
        for r in self.rows:
            if (
                r["support_available"]
                != "True"
            ):
                continue

            issue = parse_dt(
                r["selected_run_init_utc"]
            )

            decision = parse_dt(
                r["decision_time_utc"]
            )

            self.assertLessEqual(
                issue
                + timedelta(hours=6),
                decision,
                msg=(
                    r["target_date"]
                    + " "
                    + r["decision_rule"]
                ),
            )

    def test_selected_run_age_is_operational(self):
        for r in self.rows:
            if (
                r["support_available"]
                != "True"
            ):
                continue

            age = float(
                r[
                    "run_age_hours_at_decision"
                ]
            )

            # Under the frozen four-cycle geometry plus the six-hour
            # availability allowance, the latest primary or repair
            # candidate must be operationally recent. A five-day-old
            # fallback is not admissible.
            self.assertGreaterEqual(
                age,
                6.0,
            )

            self.assertLessEqual(
                age,
                16.0,
                msg=(
                    r["target_date"]
                    + " "
                    + r["decision_rule"]
                ),
            )

    def test_candidate_rank_is_core_or_single_repair(self):
        for r in self.rows:
            if (
                r["support_available"]
                != "True"
            ):
                continue

            rank = int(
                r[
                    "selected_candidate_rank"
                ]
            )

            self.assertIn(
                rank,
                {1, 2},
            )

    def test_complete_hkt_local_day(self):
        for r in self.rows:
            if (
                r["support_available"]
                != "True"
            ):
                continue

            self.assertEqual(
                int(r["hourly_rows"]),
                24,
            )

            self.assertEqual(
                int(
                    r[
                        "unique_local_hours"
                    ]
                ),
                24,
            )

            self.assertEqual(
                int(
                    r[
                        "nonmissing_temperature_rows"
                    ]
                ),
                24,
            )

            self.assertEqual(
                r["hours_00_to_23"],
                "True",
            )

    def test_weather_history_accounting(self):
        rows = [
            r
            for r in self.rows
            if date.fromisoformat(
                r["target_date"]
            )
            <= date(
                2026, 3, 15
            )
        ]

        self.assertEqual(
            len(rows),
            2920,
        )

        keys = [
            (
                r["target_date"],
                r["decision_rule"],
            )
            for r in rows
        ]

        self.assertEqual(
            len(keys),
            len(set(keys)),
        )

        for r in rows:
            if r["support_available"] != "True":
                self.assertTrue(
                    bool(
                        r["unsupported_reason"]
                    )
                )

    def test_v2_reconciliation_is_complete_but_diagnostic(self):
        with RECON.open(
            encoding="utf-8",
            newline="",
        ) as f:
            rows = list(
                csv.DictReader(f)
            )

        self.assertEqual(
            len(rows),
            2920,
        )

        # Exact equality is intentionally NOT required.
        # V2 used an earlier issue-time implementation;
        # the final methodology freezes the six-hour allowance.

    def test_summary(self):
        self.assertEqual(
            self.summary["status"],
            "PASS",
        )

        self.assertEqual(
            self.summary[
                "availability_delay_hours"
            ],
            6,
        )

        self.assertEqual(
            self.summary[
                "no_lookahead_violations"
            ],
            0,
        )

        self.assertEqual(
            self.summary[
                "availability_allowance_violations"
            ],
            0,
        )

        self.assertEqual(
            self.summary[
                "local_day_integrity_violations"
            ],
            0,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
