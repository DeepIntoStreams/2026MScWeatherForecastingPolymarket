"""Load and validate the declared empirical configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def find_repo_root(start: Optional[Path] = None) -> Path:
    current = (start or Path.cwd()).resolve()

    for candidate in (current, *current.parents):
        if (
            (candidate / "config" / "analysis.yaml").exists()
            and (candidate / "src" / "weather_polymarket").exists()
        ):
            return candidate

    raise FileNotFoundError(
        "Could not locate the repository root containing "
        "config/analysis.yaml."
    )


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to load the empirical configuration."
        ) from exc

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict):
        raise ValueError(
            f"{path} must contain a top-level YAML mapping."
        )

    return payload


def validate_analysis_config(config: Dict[str, Any]) -> None:
    required = {
        "project",
        "dates",
        "decision_rules",
        "availability",
        "training",
        "evaluation",
        "particles",
        "trading",
        "reproducibility",
    }

    missing = sorted(required.difference(config))

    if missing:
        raise ValueError(
            "analysis.yaml is missing sections: "
            + ", ".join(missing)
        )

    expected_rules = {
        "24h_prior",
        "12h_prior",
        "6h_prior",
        "event_day_open",
    }

    actual_rules = set(config["decision_rules"])

    if actual_rules != expected_rules:
        raise ValueError(
            "decision_rules must contain exactly: "
            + ", ".join(sorted(expected_rules))
        )

    if config["project"].get("uncertainty_unit") != "settlement_date":
        raise ValueError(
            "The uncertainty unit must be settlement_date."
        )

    if config["availability"].get(
        "required_unique_local_hours"
    ) != 24:
        raise ValueError(
            "The final weather construction requires 24 unique HKT hours."
        )

    if not config["evaluation"].get("exact_common_support"):
        raise ValueError(
            "The final design requires exact common support."
        )


def load_project_config(
    repo_root: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    root = repo_root or find_repo_root()

    analysis = _load_yaml(root / "config" / "analysis.yaml")
    models = _load_yaml(root / "config" / "models.yaml")
    data_sources = _load_yaml(
        root / "config" / "data_sources.yaml"
    )

    validate_analysis_config(analysis)

    return {
        "analysis": analysis,
        "models": models,
        "data_sources": data_sources,
    }
