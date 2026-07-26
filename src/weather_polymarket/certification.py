"""Certify HKO outcomes against eleven-event contract books."""

from __future__ import annotations

from typing import Dict, Tuple

import pandas as pd

from .contract_source import intervals_for_date
from .settlement import classify_temperature


def certify_real_event_books(
    contracts: pd.DataFrame,
    hko: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    temperatures: Dict[object, float] = dict(
        zip(hko["event_date"], hko["hko_daily_max_c"])
    )

    common_dates = sorted(
        set(contracts["event_date"]) & set(hko["event_date"])
    )

    if not common_dates:
        raise ValueError("Contract and HKO inputs have no common dates.")

    certified_groups = []
    date_rows = []

    for event_date in common_dates:
        group = contracts.loc[
            contracts["event_date"] == event_date
        ].copy()

        intervals = intervals_for_date(group)
        temperature = float(temperatures[event_date])

        winner = classify_temperature(intervals, temperature)

        group["hko_daily_max_c"] = temperature
        group["realised_yes"] = (
            group["event_id"].astype(str)
            == str(winner.event_id)
        ).astype(int)

        if int(group["realised_yes"].sum()) != 1:
            raise ValueError(f"{event_date} does not have one winner.")

        group["certification_status"] = "PASSED"
        group["certification_reason"] = ""

        certified_groups.append(group)

        date_rows.append(
            {
                "event_date": str(event_date),
                "hko_daily_max_c": temperature,
                "event_count": len(group),
                "winning_event_id": str(winner.event_id),
                "winner_count": int(group["realised_yes"].sum()),
                "status": "PASSED",
            }
        )

    certified = pd.concat(certified_groups, ignore_index=True)
    by_date = pd.DataFrame(date_rows)

    if not by_date["event_count"].eq(11).all():
        raise ValueError("A retained date does not contain eleven events.")

    if not by_date["winner_count"].eq(1).all():
        raise ValueError("A retained date does not contain one winner.")

    return certified, by_date
