"""Formal Notebook 02 sample-design declarations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass(frozen=True)
class Notebook02Design:
    target: str
    local_timezone: str
    decision_rules: tuple[str, ...]
    required_local_hours: int
    training_requires_market: bool
    evaluation_requires_market: bool
    random_split_permitted: bool
    group_by_date: bool


def load_notebook02_design(
    repo_root: Optional[Path] = None,
) -> Notebook02Design:
    root = repo_root or Path.cwd()
    path = root / "config" / "notebook02.yaml"

    with path.open("r", encoding="utf-8") as handle:
        payload: Dict[str, Any] = yaml.safe_load(handle)

    return Notebook02Design(
        target=payload["objective"]["target"],
        local_timezone=payload["timezone"]["local"],
        decision_rules=tuple(payload["decision_rules"]),
        required_local_hours=int(
            payload["forecast_admission"][
                "required_unique_local_hours"
            ]
        ),
        training_requires_market=bool(
            payload["weather_training_panel"][
                "requires_polymarket_market"
            ]
        ),
        evaluation_requires_market=bool(
            payload["market_evaluation_panel"][
                "requires_polymarket_market"
            ]
        ),
        random_split_permitted=bool(
            payload["chronology"]["random_split_permitted"]
        ),
        group_by_date=bool(
            payload["chronology"]["group_observations_by_date"]
        ),
    )


def validate_notebook02_design(
    design: Notebook02Design,
) -> None:
    required_rules = {
        "24h_prior",
        "12h_prior",
        "6h_prior",
        "event_day_open",
    }

    if set(design.decision_rules) != required_rules:
        raise ValueError("The four declared decision rules are required.")

    if design.target != "hko_daily_max_c":
        raise ValueError("The target must be HKO daily maximum temperature.")

    if design.local_timezone != "Asia/Hong_Kong":
        raise ValueError("Forecast paths must use Hong Kong local time.")

    if design.required_local_hours != 24:
        raise ValueError("A complete local day must contain 24 unique hours.")

    if design.training_requires_market:
        raise ValueError(
            "Weather model training must not require a Polymarket market."
        )

    if not design.evaluation_requires_market:
        raise ValueError(
            "Market evaluation must require an audited Polymarket market."
        )

    if design.random_split_permitted:
        raise ValueError("Random train-test splitting is prohibited.")

    if not design.group_by_date:
        raise ValueError("Observations must be grouped by settlement date.")
