from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from weather_polymarket.certification import certify_real_event_books
from weather_polymarket.contract_source import load_contract_definitions
from weather_polymarket.hko_source import load_hko_daily_max
from weather_polymarket.settlement import build_standard_11_event_book


class RealSourceAdapterTests(unittest.TestCase):
    def test_adapters_and_certification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contracts_path = root / "contracts.csv"
            hko_path = root / "hko.csv"

            events = build_standard_11_event_book(25, 34)

            rows = []

            for index, event in enumerate(events):
                rows.append(
                    {
                        "event_date": "2026-06-01",
                        "event_id": event.event_id,
                        "event_index": index,
                        "contract_id": f"c-{index}",
                        "token_id": f"t-{index}",
                        "event_label": event.event_id,
                        "lower_bound_c": event.lower_c,
                        "upper_bound_c": event.upper_c,
                        "lower_closed": event.lower_closed,
                        "upper_closed": event.upper_closed,
                        "settlement_source": "HKO Daily Extract",
                        "metadata_retrieved_utc": (
                            "2026-07-26T00:00:00+00:00"
                        ),
                    }
                )

            pd.DataFrame(rows).to_csv(
                contracts_path,
                index=False,
            )

            pd.DataFrame(
                [
                    {
                        "event_date": "2026-06-01",
                        "hko_daily_max_c": 30.9,
                        "source_reference": "test",
                        "source_retrieved_utc": (
                            "2026-07-26T00:00:00+00:00"
                        ),
                        "outcome_admissible_utc": "",
                        "availability_basis": "test",
                    }
                ]
            ).to_csv(hko_path, index=False)

            contracts = load_contract_definitions(contracts_path)
            hko = load_hko_daily_max(hko_path)

            certified, by_date = certify_real_event_books(
                contracts,
                hko,
            )

        self.assertEqual(len(certified), 11)
        self.assertEqual(int(certified["realised_yes"].sum()), 1)
        self.assertEqual(
            certified.loc[
                certified["realised_yes"] == 1,
                "event_id",
            ].iloc[0],
            "30_to_31",
        )
        self.assertEqual(by_date["status"].iloc[0], "PASSED")


if __name__ == "__main__":
    unittest.main()
