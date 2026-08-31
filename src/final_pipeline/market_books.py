from __future__ import annotations

import concurrent.futures
import gzip
import hashlib
import json
import math
import re
import sys
import time
import warnings

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

from scipy.stats import norm


# =============================================================================
# FROZEN FINAL DESIGN
# =============================================================================

START_DATE = pd.Timestamp("2026-03-16")
DEVELOPMENT_END = pd.Timestamp("2026-06-30")
EXTERNAL_START = pd.Timestamp("2026-07-01")
END_DATE = pd.Timestamp("2026-08-31")

HKT = ZoneInfo("Asia/Hong_Kong")
UTC = timezone.utc

RULE_ORDER = [
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
]

RULE_OFFSETS_HOURS = {
    "24h_prior": -24,
    "12h_prior": -12,
    "6h_prior": -6,
    "event_day_open": 0,
}

# Exact historical market-data convention retained from the certified
# earlier market reconstruction.
PRICE_HISTORY_WINDOW_DAYS = 7
PRICE_HISTORY_FIDELITY_MINUTES = 60

GAMMA_ENDPOINT = (
    "https://gamma-api.polymarket.com/events/keyset"
)

CLOB_HISTORY_ENDPOINT = (
    "https://clob.polymarket.com/prices-history"
)

GAMMA_LIMIT = 500
MAX_GAMMA_PAGES = 100

MAX_WORKERS = 6
REQUEST_TIMEOUT = 60
MAX_ATTEMPTS = 7

LOG_EPS = 1e-12

POOL_GRID = np.round(
    np.linspace(
        0.0,
        1.0,
        1001,
    ),
    3,
)

BOOTSTRAP_REPS = 10000
BOOTSTRAP_SEED = 20260831
BLOCK_LENGTH = 7


# =============================================================================
# INPUTS
# =============================================================================

HKO_PANEL = Path(
    "data/processed/final_pipeline/"
    "hko_daily_max_temperature.csv"
)

WEATHER_PREDICTIONS = Path(
    "data/processed/final_pipeline/weather_models/"
    "frozen_weather_model_predictions_mar_aug.csv"
)

WEATHER_SELECTION = Path(
    "outputs/final_pipeline/weather/models/"
    "weather_kernel_selection.json"
)


# =============================================================================
# RAW / CACHE PATHS
# =============================================================================

RAW_GAMMA = Path(
    "data/raw/polymarket/final_gamma/"
    "gamma_market_snapshot.json.gz"
)

RAW_PRICE_DIR = Path(
    "data/raw/polymarket/final_price_history"
)


# =============================================================================
# PROCESSED OUTPUTS
# =============================================================================

PROCESSED_DIR = Path(
    "data/processed/final_pipeline/market"
)

CONTRACT_CANDIDATES = (
    PROCESSED_DIR
    / "polymarket_contract_candidates.csv"
)

CONTRACT_UNIVERSE = (
    PROCESSED_DIR
    / "polymarket_contract_universe.csv"
)

CONTRACT_TARGETS = (
    PROCESSED_DIR
    / "polymarket_contract_targets.csv"
)

PRICE_HISTORY_PANEL = (
    PROCESSED_DIR
    / "polymarket_price_history.csv.gz"
)

DECISION_SNAPSHOTS = (
    PROCESSED_DIR
    / "polymarket_decision_snapshots.csv.gz"
)

WEATHER_EVENT_PROBS = (
    PROCESSED_DIR
    / "weather_event_probabilities.csv.gz"
)

EXACT_COMMON_EVENTS = (
    PROCESSED_DIR
    / "exact_common_event_panel.csv.gz"
)

BOOK_METRICS = (
    PROCESSED_DIR
    / "exact_common_book_metrics.csv"
)

DATE_LOSSES = (
    PROCESSED_DIR
    / "exact_common_date_losses.csv"
)

POOL_GRID_OUTPUT = (
    PROCESSED_DIR
    / "convex_pool_development_grid.csv"
)


# =============================================================================
# REPORT OUTPUTS
# =============================================================================

OUTPUT_DIR = Path(
    "outputs/final_pipeline/market"
)

GAMMA_FETCH_DIAGNOSTICS = (
    OUTPUT_DIR
    / "gamma_fetch_diagnostics.csv"
)

UNIVERSE_ISSUES = (
    OUTPUT_DIR
    / "contract_universe_issues.csv"
)

CONTRACT_DATE_SUMMARY = (
    OUTPUT_DIR
    / "contract_date_summary.csv"
)

CLOB_FETCH_DIAGNOSTICS = (
    OUTPUT_DIR
    / "clob_fetch_diagnostics.csv"
)

MISSING_SNAPSHOTS = (
    OUTPUT_DIR
    / "missing_decision_snapshots.csv"
)

MARKET_SCORE_SUMMARY = (
    OUTPUT_DIR
    / "market_only_score_summary.csv"
)

MARKET_BOOK_SUMMARY = (
    OUTPUT_DIR
    / "market_book_summary.csv"
)

WEATHER_MASS_AUDIT = (
    OUTPUT_DIR
    / "weather_probability_mass_audit.csv"
)

SCORE_SUMMARY = (
    OUTPUT_DIR
    / "exact_support_score_summary.csv"
)

TV_SUMMARY = (
    OUTPUT_DIR
    / "total_variation_summary.csv"
)

DISAGREEMENT_SUMMARY = (
    OUTPUT_DIR
    / "weather_market_disagreement_summary.csv"
)

POOL_SELECTION_JSON = (
    OUTPUT_DIR
    / "convex_pool_selection.json"
)

BOOTSTRAP_SUMMARY = (
    OUTPUT_DIR
    / "paired_score_bootstrap.csv"
)

EXACT_SUPPORT_SUMMARY = (
    OUTPUT_DIR
    / "exact_support_summary.csv"
)

TV_FIGURE = (
    OUTPUT_DIR
    / "total_variation_by_period.png"
)

EXTERNAL_SCORE_FIGURE = (
    OUTPUT_DIR
    / "external_proper_scores.png"
)

BOOK_SUM_FIGURE = (
    OUTPUT_DIR
    / "market_book_probability_sum.png"
)


# =============================================================================
# AUDIT OUTPUTS
# =============================================================================

AUDIT_DIR = Path(
    "outputs/final_pipeline/audit"
)

SUMMARY_JSON = (
    AUDIT_DIR
    / "market_stage_summary.json"
)

CHECKS_CSV = (
    AUDIT_DIR
    / "market_stage_integrity_checks.csv"
)

PROVENANCE_JSON = (
    AUDIT_DIR
    / "polymarket_provenance.json"
)


# =============================================================================
# GENERAL UTILITIES
# =============================================================================


def sha256_file(
    path: Path,
) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            block = f.read(
                1024 * 1024
            )

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def parse_jsonish(
    value,
):
    if isinstance(
        value,
        (list, dict),
    ):
        return value

    if value is None:
        return None

    if isinstance(
        value,
        float,
    ) and np.isnan(value):
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    try:
        return json.loads(
            text
        )

    except Exception:
        return None


def bool_series(
    s: pd.Series,
) -> pd.Series:
    if s.dtype == bool:
        return s

    out = (
        s.astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
            }
        )
    )

    if out.isna().any():
        raise RuntimeError(
            "Boolean parse failure."
        )

    return out.astype(bool)


def clip_probability(
    p,
):
    return np.clip(
        np.asarray(
            p,
            dtype=float,
        ),
        LOG_EPS,
        1.0 - LOG_EPS,
    )


def binary_brier(
    p,
    y,
):
    return (
        np.asarray(
            p,
            dtype=float,
        )
        - np.asarray(
            y,
            dtype=float,
        )
    ) ** 2


def binary_log(
    p,
    y,
):
    p = clip_probability(
        p
    )

    y = np.asarray(
        y,
        dtype=float,
    )

    return -(
        y * np.log(p)
        + (
            1.0 - y
        )
        * np.log(
            1.0 - p
        )
    )


def http_json(
    url,
    params=None,
):
    last_error = ""

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=
                    REQUEST_TIMEOUT,
                headers={
                    "User-Agent":
                        "UCL-MSc-weather-polymarket-research/1.0"
                },
            )

            if response.status_code == 200:
                return (
                    response.json(),
                    response.status_code,
                    "",
                    response.url,
                    attempt,
                )

            last_error = (
                f"HTTP {response.status_code}: "
                + response.text[:500]
            )

            if response.status_code == 429:
                retry = (
                    response.headers.get(
                        "Retry-After"
                    )
                )

                try:
                    wait = float(
                        retry
                    )
                except Exception:
                    wait = min(
                        60.0,
                        2.0 ** attempt,
                    )

                time.sleep(
                    wait
                )

            elif (
                500
                <= response.status_code
                < 600
            ):
                time.sleep(
                    min(
                        30.0,
                        2.0 ** attempt,
                    )
                )

            else:
                break

        except Exception as exc:
            last_error = repr(
                exc
            )

            time.sleep(
                min(
                    30.0,
                    2.0 ** attempt,
                )
            )

    return (
        None,
        None,
        last_error,
        "",
        MAX_ATTEMPTS,
    )


# =============================================================================
# GAMMA DISCOVERY
# =============================================================================


def discover_gamma_markets():
    """
    Discover the final Hong Kong market universe through Gamma events.

    We intentionally do NOT traverse the complete global binary-market
    universe.  Polymarket temperature questions are grouped as events
    containing their eleven binary contracts, so event-level retrieval is
    both the natural data model and the substantially more efficient one.

    Server-side discovery is deliberately broad:

        title_search = "Hong Kong"

    Exact inclusion remains downstream and still requires:
      * Hong Kong temperature wording,
      * study-period date,
      * HKO Daily Extract settlement family,
      * exactly eleven mutually exclusive contracts,
      * one lower tail, nine interiors and one upper tail,
      * valid YES-token identifiers.

    Hence title_search is a discovery accelerator, not an empirical
    admissibility rule.
    """

    all_events = []
    diagnostics = []

    for closed in [
        True,
        False,
    ]:
        after_cursor = None
        seen_cursors = set()

        for page in range(
            1,
            MAX_GAMMA_PAGES + 1,
        ):
            params = {
                "limit":
                    GAMMA_LIMIT,

                "closed":
                    str(
                        closed
                    ).lower(),

                "title_search":
                    "Hong Kong",

                "end_date_min":
                    "2026-03-14T00:00:00Z",

                "end_date_max":
                    "2026-09-03T23:59:59Z",
            }

            if after_cursor:
                params[
                    "after_cursor"
                ] = after_cursor

            (
                payload,
                status,
                error,
                resolved_url,
                attempts,
            ) = http_json(
                GAMMA_ENDPOINT,
                params=params,
            )

            if not isinstance(
                payload,
                dict,
            ):
                raise RuntimeError(
                    "Gamma event-keyset request failed: "
                    + (
                        error
                        or repr(payload)[:1000]
                    )
                )

            events = payload.get(
                "events"
            )

            next_cursor = payload.get(
                "next_cursor"
            )

            if not isinstance(
                events,
                list,
            ):
                raise RuntimeError(
                    "Gamma event-keyset response contains no events list."
                )

            nested_market_count = 0

            for event in events:
                if not isinstance(
                    event,
                    dict,
                ):
                    continue

                markets = event.get(
                    "markets"
                )

                if isinstance(
                    markets,
                    list,
                ):
                    nested_market_count += len(
                        markets
                    )

            diagnostics.append(
                {
                    "closed":
                        closed,

                    "page":
                        page,

                    "after_cursor_prefix":
                        (
                            str(
                                after_cursor
                            )[:40]
                            if after_cursor
                            else ""
                        ),

                    "next_cursor_prefix":
                        (
                            str(
                                next_cursor
                            )[:40]
                            if next_cursor
                            else ""
                        ),

                    "status":
                        status,

                    "events":
                        len(
                            events
                        ),

                    "nested_markets":
                        nested_market_count,

                    "attempts":
                        attempts,

                    "error":
                        error,

                    "resolved_url":
                        resolved_url,
                }
            )

            all_events.extend(
                events
            )

            if not events:
                break

            if not next_cursor:
                break

            next_cursor = str(
                next_cursor
            )

            if next_cursor in seen_cursors:
                raise RuntimeError(
                    "Gamma event-keyset cursor repeated."
                )

            if (
                after_cursor is not None
                and next_cursor
                == str(
                    after_cursor
                )
            ):
                raise RuntimeError(
                    "Gamma event-keyset cursor did not advance."
                )

            seen_cursors.add(
                next_cursor
            )

            after_cursor = (
                next_cursor
            )

        else:
            raise RuntimeError(
                "Gamma event-keyset pagination exceeded "
                "MAX_GAMMA_PAGES."
            )

    # ------------------------------------------------------------------
    # Deduplicate events queried under closed/active states.
    # ------------------------------------------------------------------

    event_dedup = {}

    for event in all_events:
        key = str(
            event.get(
                "id"
            )
            or event.get(
                "slug"
            )
            or json.dumps(
                event,
                sort_keys=True,
            )
        )

        event_dedup[key] = event

    events = list(
        event_dedup.values()
    )

    if not events:
        raise RuntimeError(
            "Gamma event discovery returned zero Hong Kong events."
        )

    # ------------------------------------------------------------------
    # Flatten nested binary markets.
    #
    # Inject a lightweight parent-event representation into each market
    # so the existing parsing/certification functions continue to see
    # event title/slug/resolution metadata.
    # ------------------------------------------------------------------

    flattened = []

    for event in events:
        nested = event.get(
            "markets"
        )

        if not isinstance(
            nested,
            list,
        ):
            continue

        parent = {
            "id":
                event.get(
                    "id"
                ),

            "title":
                event.get(
                    "title"
                ),

            "slug":
                event.get(
                    "slug"
                ),

            "description":
                event.get(
                    "description"
                ),

            "resolutionSource":
                event.get(
                    "resolutionSource"
                ),

            "startDate":
                event.get(
                    "startDate"
                ),

            "endDate":
                event.get(
                    "endDate"
                ),
        }

        for market in nested:
            if not isinstance(
                market,
                dict,
            ):
                continue

            market_copy = dict(
                market
            )

            market_copy[
                "events"
            ] = [
                parent
            ]

            market_copy[
                "_discovery_parent_event_id"
            ] = str(
                event.get(
                    "id"
                )
                or ""
            )

            market_copy[
                "_discovery_parent_event_title"
            ] = str(
                event.get(
                    "title"
                )
                or ""
            )

            market_copy[
                "_discovery_parent_event_slug"
            ] = str(
                event.get(
                    "slug"
                )
                or ""
            )

            market_copy[
                "_discovery_parent_event_created_at"
            ] = str(
                event.get(
                    "createdAt"
                )
                or ""
            )

            market_copy[
                "_discovery_parent_event_start_date"
            ] = str(
                event.get(
                    "startDate"
                )
                or ""
            )

            market_copy[
                "_discovery_parent_event_end_date"
            ] = str(
                event.get(
                    "endDate"
                )
                or ""
            )

            flattened.append(
                market_copy
            )

    market_dedup = {}

    for market in flattened:
        key = str(
            market.get(
                "id"
            )
            or market.get(
                "conditionId"
            )
            or market.get(
                "slug"
            )
            or json.dumps(
                market,
                sort_keys=True,
            )
        )

        market_dedup[key] = market

    markets = list(
        market_dedup.values()
    )

    if not markets:
        raise RuntimeError(
            "Gamma Hong Kong events contained zero nested markets."
        )

    RAW_GAMMA.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with gzip.open(
        RAW_GAMMA,
        "wt",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "discovery_endpoint":
                    GAMMA_ENDPOINT,

                "discovery_filter":
                    {
                        "title_search":
                            "Hong Kong",

                        "end_date_min":
                            "2026-03-14T00:00:00Z",

                        "end_date_max":
                            "2026-09-03T23:59:59Z",
                    },

                "events":
                    events,

                "flattened_markets":
                    markets,
            },
            f,
            ensure_ascii=False,
        )

    return (
        markets,
        pd.DataFrame(
            diagnostics
        ),
    )

def combined_market_text(
    market,
):
    values = []

    for field in [
        "question",
        "slug",
        "description",
        "resolutionSource",
        "groupItemTitle",
        "groupItemThreshold",
    ]:
        x = market.get(
            field
        )

        if x is not None:
            values.append(
                str(x)
            )

    events = market.get(
        "events"
    )

    if isinstance(
        events,
        list,
    ):
        for event in events:
            if not isinstance(
                event,
                dict,
            ):
                continue

            for field in [
                "title",
                "slug",
                "description",
                "resolutionSource",
            ]:
                x = event.get(
                    field
                )

                if x is not None:
                    values.append(
                        str(x)
                    )

    return " | ".join(
        values
    )


def is_hk_temperature_candidate(
    market,
):
    text = combined_market_text(
        market
    ).lower()

    return (
        "hong kong"
        in text
        and (
            "highest temperature"
            in text
            or "maximum temperature"
            in text
        )
    )


MONTHS = {
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
}


def parse_contract_date(
    market,
):
    candidates = [
        market.get(
            "slug"
        ),
        market.get(
            "question"
        ),
    ]

    events = market.get(
        "events"
    )

    if isinstance(
        events,
        list,
    ):
        for event in events:
            if isinstance(
                event,
                dict,
            ):
                candidates.extend(
                    [
                        event.get(
                            "slug"
                        ),
                        event.get(
                            "title"
                        ),
                    ]
                )

    pattern = re.compile(
        r"\b("
        + "|".join(
            MONTHS.keys()
        )
        + r")[\s\-]+"
        + r"(\d{1,2})"
        + r"(?:[\s,\-]+(2026))?\b",
        re.I,
    )

    for value in candidates:
        if not value:
            continue

        match = pattern.search(
            str(value)
        )

        if not match:
            continue

        month = MONTHS[
            match.group(1).lower()
        ]

        day = int(
            match.group(2)
        )

        try:
            result = pd.Timestamp(
                year=2026,
                month=month,
                day=day,
            )
        except Exception:
            continue

        if (
            START_DATE
            <= result
            <= END_DATE
        ):
            return result

    return pd.NaT


def settlement_family(
    market,
):
    text = combined_market_text(
        market
    ).lower()

    strong_hko = (
        "hko.gov.hk"
        in text
        or (
            "hong kong observatory"
            in text
            and "daily extract"
            in text
        )
    )

    other_source = any(
        phrase in text
        for phrase in [
            "wunderground",
            "weather underground",
            "hong kong international airport",
            "hkg airport",
            "airport weather",
        ]
    )

    if strong_hko:
        return (
            "HKO_Daily_Extract_one_decimal",
            "HKO Daily Extract evidence detected.",
        )

    if other_source:
        return (
            "Wunderground_or_airport",
            "Non-HKO weather-source evidence detected.",
        )

    return (
        "ambiguous_or_unknown",
        "Insufficient HKO Daily Extract settlement evidence.",
    )


def parse_event_spec(
    market,
):
    label = (
        market.get(
            "groupItemTitle"
        )
        or market.get(
            "question"
        )
        or ""
    )

    text = (
        str(label)
        .replace(
            "º",
            "°",
        )
        .replace(
            "℃",
            "°C",
        )
        .strip()
    )

    lower = re.search(
        r"(-?\d+)"
        r"\s*°?\s*C"
        r"\s*(?:or\s*)?"
        r"(?:below|lower)",
        text,
        re.I,
    )

    if lower:
        k = int(
            lower.group(1)
        )

        return {
            "event_type":
                "lower_tail_endpoint",

            "threshold_c":
                k,

            "lower_bound_c":
                -np.inf,

            "upper_bound_c":
                k + 1.0,

            "event_set":
                f"(-infinity, {k + 1})",
        }

    upper = re.search(
        r"(-?\d+)"
        r"\s*°?\s*C"
        r"\s*(?:or\s*)?"
        r"(?:higher|above)",
        text,
        re.I,
    )

    if upper:
        k = int(
            upper.group(1)
        )

        return {
            "event_type":
                "upper_tail",

            "threshold_c":
                k,

            "lower_bound_c":
                float(k),

            "upper_bound_c":
                np.inf,

            "event_set":
                f"[{k}, infinity)",
        }

    interior = re.search(
        r"(-?\d+)"
        r"\s*°?\s*C\b",
        text,
        re.I,
    )

    if interior:
        k = int(
            interior.group(1)
        )

        return {
            "event_type":
                "interior_bin",

            "threshold_c":
                k,

            "lower_bound_c":
                float(k),

            "upper_bound_c":
                float(
                    k + 1
                ),

            "event_set":
                f"[{k}, {k + 1})",
        }

    # Slug fallback.
    slug = str(
        market.get(
            "slug"
        )
        or ""
    ).lower()

    lower_slug = re.search(
        r"-(\d+)c(?:or)?below(?:-|$)",
        slug,
    )

    if lower_slug:
        k = int(
            lower_slug.group(1)
        )

        return {
            "event_type":
                "lower_tail_endpoint",
            "threshold_c":
                k,
            "lower_bound_c":
                -np.inf,
            "upper_bound_c":
                float(
                    k + 1
                ),
            "event_set":
                f"(-infinity, {k + 1})",
        }

    upper_slug = re.search(
        r"-(\d+)c(?:or)?higher(?:-|$)",
        slug,
    )

    if upper_slug:
        k = int(
            upper_slug.group(1)
        )

        return {
            "event_type":
                "upper_tail",
            "threshold_c":
                k,
            "lower_bound_c":
                float(k),
            "upper_bound_c":
                np.inf,
            "event_set":
                f"[{k}, infinity)",
        }

    interior_slug = re.search(
        r"-(\d+)c(?:-|$)",
        slug,
    )

    if interior_slug:
        k = int(
            interior_slug.group(1)
        )

        return {
            "event_type":
                "interior_bin",
            "threshold_c":
                k,
            "lower_bound_c":
                float(k),
            "upper_bound_c":
                float(
                    k + 1
                ),
            "event_set":
                f"[{k}, {k + 1})",
        }

    return {
        "event_type":
            "unknown",

        "threshold_c":
            np.nan,

        "lower_bound_c":
            np.nan,

        "upper_bound_c":
            np.nan,

        "event_set":
            "",
    }


def yes_token_id(
    market,
):
    outcomes = parse_jsonish(
        market.get(
            "outcomes"
        )
    )

    tokens = parse_jsonish(
        market.get(
            "clobTokenIds"
        )
    )

    if not isinstance(
        outcomes,
        list,
    ):
        return ""

    if not isinstance(
        tokens,
        list,
    ):
        return ""

    if len(
        outcomes
    ) != len(
        tokens
    ):
        return ""

    for outcome, token in zip(
        outcomes,
        tokens,
    ):
        if (
            str(
                outcome
            )
            .strip()
            .lower()
            == "yes"
        ):
            return str(
                token
            )

    return ""


def candidate_rows_from_gamma(
    markets,
):
    rows = []

    for market in markets:
        if not is_hk_temperature_candidate(
            market
        ):
            continue

        event_date = (
            parse_contract_date(
                market
            )
        )

        family, family_reason = (
            settlement_family(
                market
            )
        )

        spec = parse_event_spec(
            market
        )

        rows.append(
            {
    
            "parent_event_id":
                market.get(
                    "_discovery_parent_event_id"
                ),

            "parent_event_slug":
                market.get(
                    "_discovery_parent_event_slug"
                ),

            "parent_event_title":
                market.get(
                    "_discovery_parent_event_title"
                ),

            "parent_event_created_at":
                market.get(
                    "_discovery_parent_event_created_at"
                ),

            "parent_event_start_date":
                market.get(
                    "_discovery_parent_event_start_date"
                ),

            "parent_event_end_date":
                market.get(
                    "_discovery_parent_event_end_date"
                ),

            "market_id":
                    str(
                        market.get(
                            "id"
                        )
                        or ""
                    ),

                "condition_id":
                    str(
                        market.get(
                            "conditionId"
                        )
                        or ""
                    ),

                "event_date":
                    (
                        event_date.strftime(
                            "%Y-%m-%d"
                        )
                        if pd.notna(
                            event_date
                        )
                        else ""
                    ),

                "market_slug":
                    str(
                        market.get(
                            "slug"
                        )
                        or ""
                    ),

                "market_question":
                    str(
                        market.get(
                            "question"
                        )
                        or ""
                    ),

                "group_item_title":
                    str(
                        market.get(
                            "groupItemTitle"
                        )
                        or ""
                    ),

                "group_item_threshold_metadata":
                    str(
                        market.get(
                            "groupItemThreshold"
                        )
                        or ""
                    ),

                "resolution_source":
                    str(
                        market.get(
                            "resolutionSource"
                        )
                        or ""
                    ),

                "settlement_family":
                    family,

                "settlement_family_reason":
                    family_reason,

                "contract_event_type":
                    spec[
                        "event_type"
                    ],

                "threshold_c":
                    spec[
                        "threshold_c"
                    ],

                "lower_bound_c":
                    spec[
                        "lower_bound_c"
                    ],

                "upper_bound_c":
                    spec[
                        "upper_bound_c"
                    ],

                "event_set":
                    spec[
                        "event_set"
                    ],

                "yes_token_id":
                    yes_token_id(
                        market
                    ),

                "closed":
                    market.get(
                        "closed"
                    ),

                "active":
                    market.get(
                        "active"
                    ),

                "start_date_api":
                    market.get(
                        "startDate"
                    ),

                "end_date_api":
                    market.get(
                        "endDate"
                    ),
            }
        )

    df = pd.DataFrame(
        rows
    )

    if df.empty:
        raise RuntimeError(
            "No Hong Kong temperature-market candidates discovered."
        )

    df = df.drop_duplicates(
        subset=[
            "market_id"
        ],
        keep="last",
    )

    return df


def partition_status(
    group: pd.DataFrame,
):
    g = group.copy()

    if len(g) != 11:
        return (
            False,
            f"contract_count={len(g)}",
        )

    counts = (
        g[
            "contract_event_type"
        ]
        .value_counts()
        .to_dict()
    )

    expected = {
        "lower_tail_endpoint": 1,
        "interior_bin": 9,
        "upper_tail": 1,
    }

    for key, value in (
        expected.items()
    ):
        if counts.get(
            key,
            0,
        ) != value:
            return (
                False,
                "event_type_counts="
                + repr(
                    counts
                ),
            )

    if (
        g[
            "yes_token_id"
        ]
        .astype(str)
        .eq("")
        .any()
    ):
        return (
            False,
            "missing_yes_token",
        )

    if (
        g[
            "contract_event_type"
        ]
        .eq(
            "unknown"
        )
        .any()
    ):
        return (
            False,
            "unknown_event_type",
        )

    lower = g[
        g[
            "contract_event_type"
        ]
        == "lower_tail_endpoint"
    ].iloc[0]

    upper = g[
        g[
            "contract_event_type"
        ]
        == "upper_tail"
    ].iloc[0]

    interiors = (
        g[
            g[
                "contract_event_type"
            ]
            == "interior_bin"
        ]
        .sort_values(
            "lower_bound_c"
        )
    )

    expected_start = float(
        lower[
            "upper_bound_c"
        ]
    )

    for _, row in (
        interiors.iterrows()
    ):
        if not math.isclose(
            float(
                row[
                    "lower_bound_c"
                ]
            ),
            expected_start,
            abs_tol=1e-12,
        ):
            return (
                False,
                "partition_gap_or_overlap",
            )

        expected_start = float(
            row[
                "upper_bound_c"
            ]
        )

    if not math.isclose(
        expected_start,
        float(
            upper[
                "lower_bound_c"
            ]
        ),
        abs_tol=1e-12,
    ):
        return (
            False,
            "upper_tail_boundary_mismatch",
        )

    if (
        g[
            "yes_token_id"
        ]
        .duplicated()
        .any()
    ):
        return (
            False,
            "duplicate_yes_token_within_book",
        )

    return (
        True,
        "complete_11_event_partition",
    )


def resolve_duplicate_parent_books(
    hko: pd.DataFrame,
    *,
    event_date,
):
    """
    Resolve multiple complete HKO highest-temperature books for one date.

    This is used only when the date-level HKO candidate set is not already
    a single valid eleven-contract partition.

    A parent book is eligible for duplicate resolution when:

      1. it is itself a valid eleven-event partition; and
      2. its parent event had been created by event-day open.

    Event-day open is the latest of the four analysed decision cutoffs.
    Earlier decision rules remain protected independently because their
    market observations are selected only from records no later than their
    own cutoff.

    If exactly one eligible complete parent book exists, retain it.
    Otherwise the date remains excluded rather than resolving ambiguity
    arbitrarily.
    """

    required = [
        "parent_event_id",
        "parent_event_slug",
        "parent_event_created_at",
    ]

    missing = [
        c
        for c in required
        if c not in hko.columns
    ]

    if missing:
        raise RuntimeError(
            "Chronological duplicate-book resolution requires: "
            + repr(missing)
        )

    target_open = pd.Timestamp(
        event_date
    )

    if target_open.tzinfo is None:
        target_open = target_open.tz_localize(
            "Asia/Hong_Kong"
        )
    else:
        target_open = target_open.tz_convert(
            "Asia/Hong_Kong"
        )

    event_day_open_utc = (
        target_open.tz_convert(
            "UTC"
        )
    )

    eligible_books = []
    audit_rows = []

    for parent_id, book in hko.groupby(
        "parent_event_id",
        dropna=False,
    ):
        book = book.copy()

        structural_ok, detail = (
            partition_status(
                book
            )
        )

        created = pd.to_datetime(
            book[
                "parent_event_created_at"
            ],
            utc=True,
            errors="coerce",
        )

        unique_created = (
            created
            .dropna()
            .drop_duplicates()
        )

        if len(unique_created) == 1:
            parent_created = (
                unique_created.iloc[0]
            )
        else:
            parent_created = pd.NaT

        slug_values = (
            book[
                "parent_event_slug"
            ]
            .dropna()
            .astype(str)
        )

        parent_slug = (
            slug_values.iloc[0]
            if len(slug_values)
            else ""
        )

        created_by_open = bool(
            pd.notna(
                parent_created
            )
            and (
                parent_created
                <= event_day_open_utc
            )
        )

        eligible = bool(
            structural_ok
            and created_by_open
        )

        audit_rows.append(
            {
                "event_date":
                    str(
                        event_date
                    ),

                "parent_event_id":
                    str(
                        parent_id
                    ),

                "parent_event_slug":
                    parent_slug,

                "parent_event_created_at":
                    (
                        parent_created.isoformat()
                        if pd.notna(
                            parent_created
                        )
                        else ""
                    ),

                "event_day_open_utc":
                    event_day_open_utc.isoformat(),

                "contract_rows":
                    len(
                        book
                    ),

                "structurally_complete":
                    structural_ok,

                "partition_detail":
                    detail,

                "created_by_event_day_open":
                    created_by_open,

                "eligible_complete_book":
                    eligible,

                "selected":
                    False,
            }
        )

        if eligible:
            eligible_books.append(
                (
                    str(
                        parent_id
                    ),
                    parent_created,
                    book,
                )
            )

    if len(eligible_books) == 1:
        (
            selected_parent,
            selected_created,
            selected_book,
        ) = eligible_books[0]

        for row in audit_rows:
            if (
                row[
                    "parent_event_id"
                ]
                == selected_parent
            ):
                row[
                    "selected"
                ] = True

        selected_book = (
            selected_book.copy()
        )

        selected_book[
            "book_selection_rule"
        ] = (
            "chronology_resolved_unique_complete_parent_book"
        )

        selected_book[
            "selected_parent_event_id"
        ] = selected_parent

        selected_book[
            "selected_parent_event_created_at"
        ] = selected_created.isoformat()

        return (
            selected_book,
            audit_rows,
            "unique_complete_parent_book_created_by_event_day_open",
        )

    if len(eligible_books) == 0:
        return (
            None,
            audit_rows,
            "no_complete_parent_book_created_by_event_day_open",
        )

    return (
        None,
        audit_rows,
        (
            "multiple_complete_parent_books_created_by_event_day_open="
            + str(
                len(
                    eligible_books
                )
            )
        ),
    )


def certify_contract_universe(
    candidates: pd.DataFrame,
):
    issues = []
    retained = []
    chronology_audit = []

    candidates = candidates.copy()

    candidates[
        "event_date_dt"
    ] = pd.to_datetime(
        candidates[
            "event_date"
        ],
        errors="coerce",
    )

    for event_date, group in (
        candidates.groupby(
            "event_date",
            dropna=False,
        )
    ):
        if (
            not event_date
            or str(event_date)
            == "nan"
        ):
            for _, row in (
                group.iterrows()
            ):
                issues.append(
                    {
                        "issue":
                            "unparsed_contract_date",

                        "event_date":
                            "",

                        "market_id":
                            row[
                                "market_id"
                            ],

                        "market_slug":
                            row[
                                "market_slug"
                            ],

                        "detail":
                            (
                                "Contract date could not be parsed "
                                "from visible market metadata."
                            ),
                    }
                )

            continue

        hko = group[
            group[
                "settlement_family"
            ]
            == "HKO_Daily_Extract_one_decimal"
        ].copy()

        structural_ok, detail = (
            partition_status(
                hko
            )
        )

        # --------------------------------------------------------------
        # Ordinary case: exactly one valid HKO eleven-event book.
        # Preserve the original certification behaviour.
        # --------------------------------------------------------------

        if structural_ok:
            hko[
                "book_certified"
            ] = True

            hko[
                "book_selection_rule"
            ] = (
                "direct_complete_11_event_partition"
            )

            if (
                "parent_event_id"
                in hko.columns
            ):
                parent_ids = (
                    hko[
                        "parent_event_id"
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                )

                hko[
                    "selected_parent_event_id"
                ] = (
                    parent_ids[0]
                    if len(
                        parent_ids
                    ) == 1
                    else ""
                )

            retained.append(
                hko
            )

            continue

        # --------------------------------------------------------------
        # Non-standard case: there may be multiple complete parent books.
        # Resolve only through contemporaneous parent-event chronology.
        # --------------------------------------------------------------

        (
            selected,
            audit_rows,
            chronology_detail,
        ) = resolve_duplicate_parent_books(
            hko,
            event_date=event_date,
        )

        chronology_audit.extend(
            audit_rows
        )

        if selected is not None:
            selected[
                "book_certified"
            ] = True

            retained.append(
                selected
            )

            continue

        issues.append(
            {
                "issue":
                    "date_not_certified",

                "event_date":
                    event_date,

                "market_id":
                    "",

                "market_slug":
                    "",

                "detail":
                    (
                        detail
                        + "; chronology_resolution="
                        + chronology_detail
                    ),
            }
        )

    if not retained:
        raise RuntimeError(
            "No complete HKO eleven-contract books were certified."
        )

    universe = pd.concat(
        retained,
        ignore_index=True,
    )

    universe[
        "_lower_sort"
    ] = universe[
        "lower_bound_c"
    ].replace(
        -np.inf,
        -1e9,
    )

    universe = universe.sort_values(
        [
            "event_date_dt",
            "_lower_sort",
        ]
    )

    universe[
        "event_rank"
    ] = (
        universe.groupby(
            "event_date"
        )
        .cumcount()
    )

    universe = universe.drop(
        columns=[
            "_lower_sort",
            "event_date_dt",
        ]
    )

    issue_df = pd.DataFrame(
        issues
    )

    chronology_df = pd.DataFrame(
        chronology_audit
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    chronology_df.to_csv(
        OUTPUT_DIR
        / "contract_book_chronology_audit.csv",
        index=False,
    )

    return (
        universe,
        issue_df,
    )


# =============================================================================
# HKO TARGETS
# =============================================================================


def event_contains(
    value,
    lower,
    upper,
):
    if pd.isna(
        value
    ):
        return np.nan

    if np.isneginf(
        lower
    ):
        return int(
            value
            < upper
        )

    if np.isposinf(
        upper
    ):
        return int(
            value
            >= lower
        )

    return int(
        (
            value
            >= lower
        )
        and (
            value
            < upper
        )
    )


def build_contract_targets(
    universe,
):
    if not HKO_PANEL.exists():
        raise RuntimeError(
            f"Missing HKO panel: {HKO_PANEL}"
        )

    hko = pd.read_csv(
        HKO_PANEL
    )

    hko[
        "target_date"
    ] = pd.to_datetime(
        hko[
            "target_date"
        ]
    )

    hko = (
        hko[
            [
                "target_date",
                "hko_daily_max_c",
            ]
        ]
        .rename(
            columns={
                "target_date":
                    "event_date_dt"
            }
        )
    )

    targets = universe.copy()

    targets[
        "event_date_dt"
    ] = pd.to_datetime(
        targets[
            "event_date"
        ]
    )

    targets = targets.merge(
        hko,
        on="event_date_dt",
        how="left",
        validate="many_to_one",
    )

    targets[
        "target_available"
    ] = targets[
        "hko_daily_max_c"
    ].notna()

    targets[
        "Y"
    ] = [
        event_contains(
            value,
            lower,
            upper,
        )
        for (
            value,
            lower,
            upper,
        ) in zip(
            targets[
                "hko_daily_max_c"
            ],
            targets[
                "lower_bound_c"
            ],
            targets[
                "upper_bound_c"
            ],
        )
    ]

    targets[
        "Y"
    ] = pd.to_numeric(
        targets[
            "Y"
        ],
        errors="coerce",
    )

    targets[
        "empirical_period"
    ] = np.where(
        targets[
            "event_date_dt"
        ]
        <= DEVELOPMENT_END,
        "market_development",
        "external_validation",
    )

    return targets.drop(
        columns=[
            "event_date_dt"
        ]
    )


# =============================================================================
# DECISION TIMES
# =============================================================================


def decision_cutoff(
    event_date,
    rule,
):
    date_ts = pd.Timestamp(
        event_date
    )

    local_midnight = datetime(
        date_ts.year,
        date_ts.month,
        date_ts.day,
        0,
        0,
        0,
        tzinfo=HKT,
    )

    local_cutoff = (
        local_midnight
        + timedelta(
            hours=
                RULE_OFFSETS_HOURS[
                    rule
                ]
        )
    )

    return local_cutoff.astimezone(
        UTC
    )


# =============================================================================
# CLOB PRICE RECOVERY
# =============================================================================


def price_cache_path(
    token,
):
    return (
        RAW_PRICE_DIR
        / f"{token}.json.gz"
    )


def fetch_price_history_one(
    row,
):
    token = str(
        row[
            "yes_token_id"
        ]
    )

    event_date = pd.Timestamp(
        row[
            "event_date"
        ]
    )

    cache = price_cache_path(
        token
    )

    if cache.exists():
        try:
            with gzip.open(
                cache,
                "rt",
                encoding="utf-8",
            ) as f:
                payload = json.load(
                    f
                )

            history = payload.get(
                "history",
                []
            )

            if isinstance(
                history,
                list,
            ):
                return {
                    "token":
                        token,

                    "market_id":
                        row[
                            "market_id"
                        ],

                    "event_date":
                        row[
                            "event_date"
                        ],

                    "source":
                        "cache",

                    "status":
                        200,

                    "attempts":
                        0,

                    "error":
                        "",

                    "history":
                        history,
                }

        except Exception:
            pass

    event_open = decision_cutoff(
        event_date,
        "event_day_open",
    )

    start = (
        event_open
        - timedelta(
            days=
                PRICE_HISTORY_WINDOW_DAYS
        )
    )

    # One hour beyond open is queried only to avoid endpoint-boundary
    # truncation. Downstream selection still requires t <= cutoff.
    end = (
        event_open
        + timedelta(
            hours=1
        )
    )

    params = {
        "market":
            token,

        "startTs":
            int(
                start.timestamp()
            ),

        "endTs":
            int(
                end.timestamp()
            ),

        "fidelity":
            PRICE_HISTORY_FIDELITY_MINUTES,
    }

    (
        payload,
        status,
        error,
        url,
        attempts,
    ) = http_json(
        CLOB_HISTORY_ENDPOINT,
        params=params,
    )

    history = []

    if isinstance(
        payload,
        dict,
    ):
        x = payload.get(
            "history"
        )

        if isinstance(
            x,
            list,
        ):
            history = x

    cache.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with gzip.open(
        cache,
        "wt",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "history":
                    history,

                "request_params":
                    params,

                "retrieved_url":
                    url,

                "status":
                    status,

                "error":
                    error,
            },
            f,
        )

    return {
        "token":
            token,

        "market_id":
            row[
                "market_id"
            ],

        "event_date":
            row[
                "event_date"
            ],

        "source":
            "api",

        "status":
            status,

        "attempts":
            attempts,

        "error":
            error,

        "history":
            history,
    }


def recover_price_histories(
    targets,
):
    RAW_PRICE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    unique = (
        targets[
            [
                "market_id",
                "event_date",
                "yes_token_id",
            ]
        ]
        .drop_duplicates(
            "yes_token_id"
        )
        .to_dict(
            orient="records"
        )
    )

    results = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=
            MAX_WORKERS
    ) as executor:

        futures = [
            executor.submit(
                fetch_price_history_one,
                row,
            )
            for row in unique
        ]

        for i, future in enumerate(
            concurrent.futures.as_completed(
                futures
            ),
            start=1,
        ):
            result = future.result()

            results.append(
                result
            )

            if (
                i % 100
                == 0
                or i == len(
                    futures
                )
            ):
                print(
                    "CLOB histories:",
                    i,
                    "/",
                    len(
                        futures
                    ),
                )

    history_rows = []
    diagnostics = []

    for result in results:
        history = result[
            "history"
        ]

        diagnostics.append(
            {
                "yes_token_id":
                    result[
                        "token"
                    ],

                "market_id":
                    result[
                        "market_id"
                    ],

                "event_date":
                    result[
                        "event_date"
                    ],

                "source":
                    result[
                        "source"
                    ],

                "status":
                    result[
                        "status"
                    ],

                "attempts":
                    result[
                        "attempts"
                    ],

                "has_history":
                    bool(
                        history
                    ),

                "history_rows":
                    len(
                        history
                    ),

                "error":
                    result[
                        "error"
                    ],
            }
        )

        for item in history:
            try:
                t = int(
                    item[
                        "t"
                    ]
                )

                p = float(
                    item[
                        "p"
                    ]
                )

            except Exception:
                continue

            history_rows.append(
                {
                    "yes_token_id":
                        result[
                            "token"
                        ],

                    "market_id":
                        result[
                            "market_id"
                        ],

                    "event_date":
                        result[
                            "event_date"
                        ],

                    "price_timestamp_unix":
                        t,

                    "price_timestamp_utc":
                        datetime.fromtimestamp(
                            t,
                            tz=UTC,
                        ).isoformat(),

                    "market_yes_price":
                        p,
                }
            )

    history_df = pd.DataFrame(
        history_rows
    )

    diagnostics_df = (
        pd.DataFrame(
            diagnostics
        )
    )

    if history_df.empty:
        raise RuntimeError(
            "No CLOB history observations recovered."
        )

    history_df = (
        history_df.sort_values(
            [
                "yes_token_id",
                "price_timestamp_unix",
            ]
        )
        .drop_duplicates(
            [
                "yes_token_id",
                "price_timestamp_unix",
            ],
            keep="last",
        )
    )

    return (
        history_df,
        diagnostics_df,
    )


def build_decision_snapshots(
    targets,
    history,
):
    by_token = {
        token: group.sort_values(
            "price_timestamp_unix"
        )
        for token, group
        in history.groupby(
            "yes_token_id"
        )
    }

    rows = []

    for _, contract in (
        targets.iterrows()
    ):
        token = str(
            contract[
                "yes_token_id"
            ]
        )

        token_history = (
            by_token.get(
                token
            )
        )

        for rule in RULE_ORDER:
            cutoff = decision_cutoff(
                contract[
                    "event_date"
                ],
                rule,
            )

            selected = None

            if token_history is not None:
                eligible = token_history[
                    token_history[
                        "price_timestamp_unix"
                    ]
                    <= int(
                        cutoff.timestamp()
                    )
                ]

                if not eligible.empty:
                    selected = (
                        eligible.iloc[
                            -1
                        ]
                    )

            row = {
                "event_date":
                    contract[
                        "event_date"
                    ],

                "market_id":
                    contract[
                        "market_id"
                    ],

                "market_slug":
                    contract[
                        "market_slug"
                    ],

                "group_item_title":
                    contract[
                        "group_item_title"
                    ],

                "yes_token_id":
                    token,

                "contract_event_type":
                    contract[
                        "contract_event_type"
                    ],

                "threshold_c":
                    contract[
                        "threshold_c"
                    ],

                "lower_bound_c":
                    contract[
                        "lower_bound_c"
                    ],

                "upper_bound_c":
                    contract[
                        "upper_bound_c"
                    ],

                "event_rank":
                    contract[
                        "event_rank"
                    ],

                "decision_rule":
                    rule,

                "decision_cutoff_utc":
                    cutoff.isoformat(),

                "target_available":
                    contract[
                        "target_available"
                    ],

                "hko_daily_max_c":
                    contract[
                        "hko_daily_max_c"
                    ],

                "Y":
                    contract[
                        "Y"
                    ],

                "empirical_period":
                    contract[
                        "empirical_period"
                    ],

                "market_price_available":
                    selected
                    is not None,

                "market_raw_yes":
                    (
                        float(
                            selected[
                                "market_yes_price"
                            ]
                        )
                        if selected
                        is not None
                        else np.nan
                    ),

                "selected_price_timestamp_unix":
                    (
                        int(
                            selected[
                                "price_timestamp_unix"
                            ]
                        )
                        if selected
                        is not None
                        else np.nan
                    ),

                "selected_price_timestamp_utc":
                    (
                        selected[
                            "price_timestamp_utc"
                        ]
                        if selected
                        is not None
                        else ""
                    ),

                "record_age_hours":
                    (
                        (
                            cutoff.timestamp()
                            - float(
                                selected[
                                    "price_timestamp_unix"
                                ]
                            )
                        )
                        / 3600.0
                        if selected
                        is not None
                        else np.nan
                    ),
            }

            rows.append(
                row
            )

    snapshots = pd.DataFrame(
        rows
    )

    keys = [
        "event_date",
        "decision_rule",
    ]

    group_stats = (
        snapshots.groupby(
            keys,
            sort=False,
        )
        .agg(
            book_contracts=(
                "market_id",
                "size",
            ),

            prices_available=(
                "market_price_available",
                "sum",
            ),

            market_book_sum=(
                "market_raw_yes",
                lambda x:
                    x.sum(
                        min_count=1
                    ),
            ),
        )
        .reset_index()
    )

    group_stats[
        "market_book_complete"
    ] = (
        (
            group_stats[
                "book_contracts"
            ]
            == 11
        )
        & (
            group_stats[
                "prices_available"
            ]
            == 11
        )
        & (
            group_stats[
                "market_book_sum"
            ]
            > 0
        )
    )

    snapshots = snapshots.merge(
        group_stats,
        on=keys,
        how="left",
        validate="many_to_one",
    )

    snapshots[
        "market_normalised"
    ] = np.where(
        snapshots[
            "market_book_complete"
        ],
        (
            snapshots[
                "market_raw_yes"
            ]
            / snapshots[
                "market_book_sum"
            ]
        ),
        np.nan,
    )

    return snapshots


# =============================================================================
# MARKET-ONLY DIAGNOSTICS
# =============================================================================


def market_only_summaries(
    snapshots,
):
    score_rows = []

    scored = snapshots[
        snapshots[
            "market_price_available"
        ]
        & snapshots[
            "target_available"
        ]
    ].copy()

    scored[
        "binary_brier"
    ] = binary_brier(
        scored[
            "market_raw_yes"
        ],
        scored[
            "Y"
        ],
    )

    scored[
        "binary_log"
    ] = binary_log(
        scored[
            "market_raw_yes"
        ],
        scored[
            "Y"
        ],
    )

    for period in [
        "market_development",
        "external_validation",
        "all_market_period",
    ]:
        if period == "all_market_period":
            p = scored
        else:
            p = scored[
                scored[
                    "empirical_period"
                ]
                == period
            ]

        for rule in RULE_ORDER:
            x = p[
                p[
                    "decision_rule"
                ]
                == rule
            ]

            if x.empty:
                continue

            score_rows.append(
                {
                    "analysis_period":
                        period,

                    "decision_rule":
                        rule,

                    "event_rows":
                        len(x),

                    "dates":
                        x[
                            "event_date"
                        ].nunique(),

                    "mean_binary_brier":
                        x[
                            "binary_brier"
                        ].mean(),

                    "mean_binary_log":
                        x[
                            "binary_log"
                        ].mean(),

                    "mean_raw_yes":
                        x[
                            "market_raw_yes"
                        ].mean(),

                    "outcome_rate":
                        x[
                            "Y"
                        ].mean(),

                    "median_record_age_hours":
                        x[
                            "record_age_hours"
                        ].median(),

                    "p95_record_age_hours":
                        x[
                            "record_age_hours"
                        ].quantile(
                            0.95
                        ),
                }
            )

    book_rows = []

    complete = snapshots[
        snapshots[
            "market_book_complete"
        ]
        & snapshots[
            "target_available"
        ]
    ].copy()

    for (
        date,
        rule,
    ), g in complete.groupby(
        [
            "event_date",
            "decision_rule",
        ]
    ):
        if len(g) != 11:
            continue

        y = g[
            "Y"
        ].to_numpy(
            dtype=float
        )

        p = g[
            "market_normalised"
        ].to_numpy(
            dtype=float
        )

        winner = np.where(
            y == 1
        )[0]

        if len(
            winner
        ) != 1:
            continue

        book_rows.append(
            {
                "event_date":
                    date,

                "decision_rule":
                    rule,

                "empirical_period":
                    g[
                        "empirical_period"
                    ].iloc[0],

                "market_book_sum":
                    g[
                        "market_book_sum"
                    ].iloc[0],

                "abs_book_sum_error":
                    abs(
                        g[
                            "market_book_sum"
                        ].iloc[0]
                        - 1.0
                    ),

                "categorical_log":
                    -math.log(
                        max(
                            p[
                                winner[0]
                            ],
                            LOG_EPS,
                        )
                    ),

                "multiclass_brier":
                    float(
                        np.sum(
                            (
                                p - y
                            )
                            ** 2
                        )
                    ),

                "winning_probability":
                    p[
                        winner[0]
                    ],

                "max_record_age_hours":
                    g[
                        "record_age_hours"
                    ].max(),
            }
        )

    return (
        pd.DataFrame(
            score_rows
        ),
        pd.DataFrame(
            book_rows
        ),
    )


# =============================================================================
# WEATHER DISTRIBUTION -> EVENT PROBABILITY
# =============================================================================


def gaussian_event_probability(
    mu,
    sigma,
    lower,
    upper,
):
    if not np.isfinite(
        sigma
    ) or sigma <= 0:
        raise RuntimeError(
            "Invalid predictive sigma."
        )

    if np.isneginf(
        lower
    ):
        return float(
            norm.cdf(
                (
                    upper - mu
                )
                / sigma
            )
        )

    if np.isposinf(
        upper
    ):
        return float(
            1.0
            - norm.cdf(
                (
                    lower - mu
                )
                / sigma
            )
        )

    return float(
        norm.cdf(
            (
                upper - mu
            )
            / sigma
        )
        - norm.cdf(
            (
                lower - mu
            )
            / sigma
        )
    )


def deterministic_event_probability(
    value,
    lower,
    upper,
):
    return float(
        event_contains(
            value,
            lower,
            upper,
        )
    )


def build_weather_event_probabilities(
    targets,
):
    if not WEATHER_PREDICTIONS.exists():
        raise RuntimeError(
            "Frozen weather predictions are missing."
        )

    if not WEATHER_SELECTION.exists():
        raise RuntimeError(
            "Weather kernel selection is missing."
        )

    selection = json.loads(
        WEATHER_SELECTION.read_text()
    )

    selected_kernel = selection[
        "selected_kernel"
    ]

    weather = pd.read_csv(
        WEATHER_PREDICTIONS
    )

    weather[
        "target_date"
    ] = pd.to_datetime(
        weather[
            "target_date"
        ]
    )

    target_lookup = (
        targets.copy()
    )

    target_lookup[
        "event_date_dt"
    ] = pd.to_datetime(
        target_lookup[
            "event_date"
        ]
    )

    by_date = {
        date: group.copy()
        for date, group
        in target_lookup.groupby(
            "event_date_dt"
        )
    }

    rows = []

    for _, forecast in (
        weather.iterrows()
    ):
        date = forecast[
            "target_date"
        ]

        contracts = by_date.get(
            date
        )

        if contracts is None:
            continue

        raw_mean = float(
            forecast[
                "forecast_daily_max_c"
            ]
        )

        static_mean = float(
            forecast[
                "static_mean_c"
            ]
        )

        static_sd = float(
            forecast[
                "static_sd_c"
            ]
        )

        selected_mean = float(
            forecast[
                "selected_gp_mean_c"
            ]
        )

        selected_sd = float(
            forecast[
                "selected_gp_sd_c"
            ]
        )

        for _, contract in (
            contracts.iterrows()
        ):
            lower = float(
                contract[
                    "lower_bound_c"
                ]
            )

            upper = float(
                contract[
                    "upper_bound_c"
                ]
            )

            rows.append(
                {
                    "event_date":
                        contract[
                            "event_date"
                        ],

                    "decision_rule":
                        forecast[
                            "decision_rule"
                        ],

                    "empirical_period":
                        forecast[
                            "empirical_period"
                        ],

                    "market_id":
                        contract[
                            "market_id"
                        ],

                    "yes_token_id":
                        contract[
                            "yes_token_id"
                        ],

                    "group_item_title":
                        contract[
                            "group_item_title"
                        ],

                    "contract_event_type":
                        contract[
                            "contract_event_type"
                        ],

                    "event_rank":
                        contract[
                            "event_rank"
                        ],

                    "lower_bound_c":
                        lower,

                    "upper_bound_c":
                        upper,

                    "hko_daily_max_c":
                        contract[
                            "hko_daily_max_c"
                        ],

                    "target_available":
                        contract[
                            "target_available"
                        ],

                    "Y":
                        contract[
                            "Y"
                        ],

                    "raw_temperature_c":
                        raw_mean,

                    "static_mean_c":
                        static_mean,

                    "static_sd_c":
                        static_sd,

                    "selected_kernel":
                        selected_kernel,

                    "selected_gp_mean_c":
                        selected_mean,

                    "selected_gp_sd_c":
                        selected_sd,

                    "p_raw":
                        deterministic_event_probability(
                            raw_mean,
                            lower,
                            upper,
                        ),

                    "p_static":
                        gaussian_event_probability(
                            static_mean,
                            static_sd,
                            lower,
                            upper,
                        ),

                    "p_selected_gp":
                        gaussian_event_probability(
                            selected_mean,
                            selected_sd,
                            lower,
                            upper,
                        ),
                }
            )

    result = pd.DataFrame(
        rows
    )

    if result.empty:
        raise RuntimeError(
            "No weather event probabilities were generated."
        )

    return result


def probability_mass_audit(
    weather_probs,
):
    rows = []

    for (
        date,
        rule,
    ), g in weather_probs.groupby(
        [
            "event_date",
            "decision_rule",
        ]
    ):
        rows.append(
            {
                "event_date":
                    date,

                "decision_rule":
                    rule,

                "contracts":
                    len(g),

                "raw_sum":
                    g[
                        "p_raw"
                    ].sum(),

                "static_sum":
                    g[
                        "p_static"
                    ].sum(),

                "selected_gp_sum":
                    g[
                        "p_selected_gp"
                    ].sum(),

                "max_mass_error":
                    max(
                        abs(
                            g[
                                "p_raw"
                            ].sum()
                            - 1.0
                        ),
                        abs(
                            g[
                                "p_static"
                            ].sum()
                            - 1.0
                        ),
                        abs(
                            g[
                                "p_selected_gp"
                            ].sum()
                            - 1.0
                        ),
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# EXACT COMMON SUPPORT
# =============================================================================


def build_exact_common(
    weather_probs,
    snapshots,
):
    market = snapshots[
        snapshots[
            "market_book_complete"
        ]
    ].copy()

    common = weather_probs.merge(
        market[
            [
                "event_date",
                "decision_rule",
                "market_id",
                "market_raw_yes",
                "market_normalised",
                "market_book_sum",
                "record_age_hours",
                "decision_cutoff_utc",
                "selected_price_timestamp_utc",
            ]
        ],
        on=[
            "event_date",
            "decision_rule",
            "market_id",
        ],
        how="inner",
        validate="one_to_one",
    )

    common[
        "score_ready"
    ] = common[
        "target_available"
    ].astype(bool)

    return common


# =============================================================================
# BOOK METRICS
# =============================================================================


def categorical_log(
    p,
    y,
):
    winner = np.where(
        y == 1
    )[0]

    if len(
        winner
    ) != 1:
        return np.nan

    return float(
        -math.log(
            max(
                float(
                    p[
                        winner[0]
                    ]
                ),
                LOG_EPS,
            )
        )
    )


def multiclass_brier(
    p,
    y,
):
    return float(
        np.sum(
            (
                np.asarray(
                    p,
                    dtype=float,
                )
                - np.asarray(
                    y,
                    dtype=float,
                )
            )
            ** 2
        )
    )


def construct_book_metrics(
    common,
    pool_weight=None,
):
    rows = []

    for (
        date,
        rule,
    ), g in common.groupby(
        [
            "event_date",
            "decision_rule",
        ],
        sort=True,
    ):
        g = g.sort_values(
            "event_rank"
        )

        if len(g) != 11:
            continue

        p_raw = g[
            "p_raw"
        ].to_numpy(
            dtype=float
        )

        p_static = g[
            "p_static"
        ].to_numpy(
            dtype=float
        )

        p_gp = g[
            "p_selected_gp"
        ].to_numpy(
            dtype=float
        )

        p_market_raw = g[
            "market_raw_yes"
        ].to_numpy(
            dtype=float
        )

        p_market = g[
            "market_normalised"
        ].to_numpy(
            dtype=float
        )

        ranks = g[
            "event_rank"
        ].to_numpy(
            dtype=float
        )

        target_available = bool(
            g[
                "target_available"
            ].iloc[0]
        )

        row = {
            "event_date":
                date,

            "decision_rule":
                rule,

            "empirical_period":
                g[
                    "empirical_period"
                ].iloc[0],

            "market_book_sum":
                g[
                    "market_book_sum"
                ].iloc[0],

            "tv_raw":
                0.5
                * np.abs(
                    p_raw
                    - p_market
                ).sum(),

            "tv_static":
                0.5
                * np.abs(
                    p_static
                    - p_market
                ).sum(),

            "tv_selected_gp":
                0.5
                * np.abs(
                    p_gp
                    - p_market
                ).sum(),

            "expected_rank_raw":
                float(
                    ranks
                    @ p_raw
                ),

            "expected_rank_static":
                float(
                    ranks
                    @ p_static
                ),

            "expected_rank_selected_gp":
                float(
                    ranks
                    @ p_gp
                ),

            "expected_rank_market":
                float(
                    ranks
                    @ p_market
                ),

            "market_minus_gp_expected_rank":
                float(
                    ranks
                    @ p_market
                    - ranks
                    @ p_gp
                ),

            "target_available":
                target_available,
        }

        if (
            pool_weight
            is not None
        ):
            p_pool = (
                pool_weight
                * p_gp
                + (
                    1.0
                    - pool_weight
                )
                * p_market
            )

            row[
                "pool_weight_gp"
            ] = pool_weight

            row[
                "tv_pool"
            ] = (
                0.5
                * np.abs(
                    p_pool
                    - p_market
                ).sum()
            )

        if target_available:
            y = g[
                "Y"
            ].to_numpy(
                dtype=float
            )

            if not math.isclose(
                y.sum(),
                1.0,
                abs_tol=1e-12,
            ):
                raise RuntimeError(
                    "Book has invalid realised outcome."
                )

            winner = int(
                np.argmax(
                    y
                )
            )

            # Binary event-level scores use raw market YES.
            for label, p in [
                (
                    "static",
                    p_static,
                ),
                (
                    "selected_gp",
                    p_gp,
                ),
                (
                    "market",
                    p_market_raw,
                ),
            ]:
                row[
                    f"{label}_binary_brier"
                ] = float(
                    binary_brier(
                        p,
                        y,
                    ).mean()
                )

                row[
                    f"{label}_binary_log"
                ] = float(
                    binary_log(
                        p,
                        y,
                    ).mean()
                )

            # Categorical scores use coherent probability books.
            for label, p in [
                (
                    "static",
                    p_static,
                ),
                (
                    "selected_gp",
                    p_gp,
                ),
                (
                    "market",
                    p_market,
                ),
            ]:
                row[
                    f"{label}_categorical_log"
                ] = categorical_log(
                    p,
                    y,
                )

                row[
                    f"{label}_multiclass_brier"
                ] = multiclass_brier(
                    p,
                    y,
                )

            row[
                "winner_event_rank"
            ] = winner

            row[
                "winner_probability_static"
            ] = p_static[
                winner
            ]

            row[
                "winner_probability_selected_gp"
            ] = p_gp[
                winner
            ]

            row[
                "winner_probability_market"
            ] = p_market[
                winner
            ]

            row[
                "market_minus_gp_winner_probability"
            ] = (
                p_market[
                    winner
                ]
                - p_gp[
                    winner
                ]
            )

            if (
                pool_weight
                is not None
            ):
                p_pool = (
                    pool_weight
                    * p_gp
                    + (
                        1.0
                        - pool_weight
                    )
                    * p_market
                )

                row[
                    "pool_binary_brier"
                ] = float(
                    binary_brier(
                        p_pool,
                        y,
                    ).mean()
                )

                row[
                    "pool_binary_log"
                ] = float(
                    binary_log(
                        p_pool,
                        y,
                    ).mean()
                )

                row[
                    "pool_categorical_log"
                ] = categorical_log(
                    p_pool,
                    y,
                )

                row[
                    "pool_multiclass_brier"
                ] = multiclass_brier(
                    p_pool,
                    y,
                )

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# DATE-BALANCED SUMMARIES
# =============================================================================


METRICS = [
    "binary_brier",
    "binary_log",
    "categorical_log",
    "multiclass_brier",
]


def date_balanced_mean(
    book_metrics,
    column,
):
    x = book_metrics[
        book_metrics[
            "target_available"
        ].astype(bool)
        & book_metrics[
            column
        ].notna()
    ]

    if x.empty:
        return np.nan

    per_date = (
        x.groupby(
            "event_date"
        )[column]
        .mean()
    )

    return float(
        per_date.mean()
    )


def proper_score_summary(
    books,
):
    rows = []

    for period in [
        "market_development",
        "external_validation",
        "all_exact_support",
    ]:
        if period == "all_exact_support":
            x = books
        else:
            x = books[
                books[
                    "empirical_period"
                ]
                == period
            ]

        for source in [
            "static",
            "selected_gp",
            "pool",
            "market",
        ]:
            if (
                source == "pool"
                and "pool_binary_brier"
                not in x.columns
            ):
                continue

            row = {
                "analysis_period":
                    period,

                "source":
                    source,

                "books":
                    int(
                        x[
                            "target_available"
                        ].sum()
                    ),

                "dates":
                    int(
                        x.loc[
                            x[
                                "target_available"
                            ].astype(
                                bool
                            ),
                            "event_date",
                        ].nunique()
                    ),
            }

            for metric in METRICS:
                col = (
                    f"{source}_{metric}"
                )

                row[
                    metric
                ] = (
                    date_balanced_mean(
                        x,
                        col,
                    )
                    if col
                    in x.columns
                    else np.nan
                )

            rows.append(
                row
            )

    return pd.DataFrame(
        rows
    )


def tv_summary(
    books,
):
    rows = []

    for period in [
        "market_development",
        "external_validation",
        "all_exact_support",
    ]:
        if period == "all_exact_support":
            x = books
        else:
            x = books[
                books[
                    "empirical_period"
                ]
                == period
            ]

        values = {}

        for source in [
            "raw",
            "static",
            "selected_gp",
        ]:
            col = (
                f"tv_{source}"
            )

            if x.empty:
                value = np.nan
            else:
                value = float(
                    x.groupby(
                        "event_date"
                    )[col]
                    .mean()
                    .mean()
                )

            values[
                source
            ] = value

        raw = values[
            "raw"
        ]

        for source in [
            "raw",
            "static",
            "selected_gp",
        ]:
            value = values[
                source
            ]

            closure = (
                0.0
                if source
                == "raw"
                else (
                    1.0
                    - value
                    / raw
                    if (
                        np.isfinite(
                            raw
                        )
                        and raw > 0
                    )
                    else np.nan
                )
            )

            rows.append(
                {
                    "analysis_period":
                        period,

                    "source":
                        source,

                    "date_balanced_tv":
                        value,

                    "raw_distance_closure":
                        closure,

                    "dates":
                        int(
                            x[
                                "event_date"
                            ].nunique()
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# CONVEX POOL
# =============================================================================


def select_convex_pool(
    common,
):
    dev = common[
        (
            common[
                "empirical_period"
            ]
            == "market_development"
        )
        & common[
            "score_ready"
        ]
    ].copy()

    if dev.empty:
        raise RuntimeError(
            "No development exact-support rows for pool selection."
        )

    rows = []

    # Pre-build book vectors once.
    books = []

    for (
        date,
        rule,
    ), g in dev.groupby(
        [
            "event_date",
            "decision_rule",
        ]
    ):
        g = g.sort_values(
            "event_rank"
        )

        if len(g) != 11:
            continue

        y = g[
            "Y"
        ].to_numpy(
            dtype=float
        )

        winner = np.where(
            y == 1
        )[0]

        if len(
            winner
        ) != 1:
            continue

        books.append(
            {
                "date":
                    date,

                "rule":
                    rule,

                "gp_winner":
                    float(
                        g[
                            "p_selected_gp"
                        ].to_numpy(
                            dtype=float
                        )[
                            winner[0]
                        ]
                    ),

                "market_winner":
                    float(
                        g[
                            "market_normalised"
                        ].to_numpy(
                            dtype=float
                        )[
                            winner[0]
                        ]
                    ),
            }
        )

    book_df = pd.DataFrame(
        books
    )

    if book_df.empty:
        raise RuntimeError(
            "No complete development books for pool selection."
        )

    for w in POOL_GRID:
        p = (
            w
            * book_df[
                "gp_winner"
            ].to_numpy(
                dtype=float
            )
            + (
                1.0
                - w
            )
            * book_df[
                "market_winner"
            ].to_numpy(
                dtype=float
            )
        )

        loss = -np.log(
            np.clip(
                p,
                LOG_EPS,
                1.0,
            )
        )

        tmp = book_df[
            [
                "date",
                "rule",
            ]
        ].copy()

        tmp[
            "loss"
        ] = loss

        date_loss = (
            tmp.groupby(
                "date"
            )[
                "loss"
            ]
            .mean()
        )

        rows.append(
            {
                "weight_gp":
                    float(w),

                "weight_market":
                    float(
                        1.0
                        - w
                    ),

                "development_dates":
                    int(
                        date_loss.index.nunique()
                    ),

                "development_books":
                    int(
                        len(
                            book_df
                        )
                    ),

                "date_balanced_categorical_log":
                    float(
                        date_loss.mean()
                    ),
            }
        )

    grid = pd.DataFrame(
        rows
    )

    best_index = (
        grid[
            "date_balanced_categorical_log"
        ].idxmin()
    )

    best = grid.loc[
        best_index
    ]

    return (
        float(
            best[
                "weight_gp"
            ]
        ),
        grid,
    )


def apply_pool_probabilities(
    common,
    weight,
):
    result = common.copy()

    result[
        "p_pool"
    ] = (
        weight
        * result[
            "p_selected_gp"
        ]
        + (
            1.0
            - weight
        )
        * result[
            "market_normalised"
        ]
    )

    return result


# =============================================================================
# PAIRED DATE-LEVEL INFERENCE
# =============================================================================


def circular_block_indices(
    n,
    block_length,
    reps,
    rng,
):
    blocks = int(
        math.ceil(
            n
            / block_length
        )
    )

    starts = rng.integers(
        0,
        n,
        size=(
            reps,
            blocks,
        ),
    )

    offsets = np.arange(
        block_length
    )

    idx = (
        starts[
            :,
            :,
            None,
        ]
        + offsets[
            None,
            None,
            :,
        ]
    ) % n

    return idx.reshape(
        reps,
        -1,
    )[
        :,
        :n,
    ]


def bootstrap_interval(
    values,
    block=False,
    seed=0,
):
    values = np.asarray(
        values,
        dtype=float,
    )

    n = len(
        values
    )

    rng = np.random.default_rng(
        seed
    )

    if block:
        idx = circular_block_indices(
            n,
            BLOCK_LENGTH,
            BOOTSTRAP_REPS,
            rng,
        )

    else:
        idx = rng.integers(
            0,
            n,
            size=(
                BOOTSTRAP_REPS,
                n,
            ),
        )

    means = values[
        idx
    ].mean(
        axis=1
    )

    return (
        float(
            np.quantile(
                means,
                0.025,
            )
        ),
        float(
            np.quantile(
                means,
                0.975,
            )
        ),
    )


def construct_date_losses(
    books,
):
    rows = []

    score_ready = books[
        books[
            "target_available"
        ].astype(bool)
    ].copy()

    for date, g in (
        score_ready.groupby(
            "event_date"
        )
    ):
        row = {
            "event_date":
                date,

            "empirical_period":
                g[
                    "empirical_period"
                ].iloc[0],

            "rules":
                len(g),
        }

        for source in [
            "static",
            "selected_gp",
            "pool",
            "market",
        ]:
            for metric in METRICS:
                col = (
                    f"{source}_{metric}"
                )

                if col in g.columns:
                    row[
                        f"{source}_{metric}"
                    ] = g[
                        col
                    ].mean()

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


def paired_bootstrap_summary(
    date_losses,
):
    rows = []

    contrasts = [
        (
            "static",
            "market",
        ),
        (
            "selected_gp",
            "market",
        ),
        (
            "pool",
            "market",
        ),
        (
            "selected_gp",
            "static",
        ),
    ]

    for period in [
        "market_development",
        "external_validation",
    ]:
        x = (
            date_losses[
                date_losses[
                    "empirical_period"
                ]
                == period
            ]
            .sort_values(
                "event_date"
            )
        )

        for metric in METRICS:
            for source_a, source_b in (
                contrasts
            ):
                a = (
                    f"{source_a}_{metric}"
                )

                b = (
                    f"{source_b}_{metric}"
                )

                if (
                    a
                    not in x.columns
                    or b
                    not in x.columns
                ):
                    continue

                pair = x[
                    [
                        a,
                        b,
                    ]
                ].dropna()

                if len(
                    pair
                ) < 10:
                    continue

                diff = (
                    pair[
                        a
                    ]
                    - pair[
                        b
                    ]
                ).to_numpy(
                    dtype=float
                )

                ordinary = bootstrap_interval(
                    diff,
                    block=False,
                    seed=
                        BOOTSTRAP_SEED
                        + len(
                            rows
                        ),
                )

                moving = bootstrap_interval(
                    diff,
                    block=True,
                    seed=
                        BOOTSTRAP_SEED
                        + 1000
                        + len(
                            rows
                        ),
                )

                rows.append(
                    {
                        "analysis_period":
                            period,

                        "metric":
                            metric,

                        "source_a":
                            source_a,

                        "source_b":
                            source_b,

                        "n_dates":
                            len(
                                pair
                            ),

                        "mean_a_minus_b":
                            float(
                                diff.mean()
                            ),

                        "ordinary_lower_95":
                            ordinary[
                                0
                            ],

                        "ordinary_upper_95":
                            ordinary[
                                1
                            ],

                        "block7_lower_95":
                            moving[
                                0
                            ],

                        "block7_upper_95":
                            moving[
                                1
                            ],

                        "replications":
                            BOOTSTRAP_REPS,
                    }
                )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# SUPPORT / DISAGREEMENT
# =============================================================================


def exact_support_summary(
    targets,
    snapshots,
    weather_probs,
    common,
):
    rows = []

    for period in [
        "market_development",
        "external_validation",
        "all_market_period",
    ]:
        if period == "all_market_period":
            t = targets
            s = snapshots
            w = weather_probs
            c = common
        else:
            t = targets[
                targets[
                    "empirical_period"
                ]
                == period
            ]

            s = snapshots[
                snapshots[
                    "empirical_period"
                ]
                == period
            ]

            w = weather_probs[
                weather_probs[
                    "empirical_period"
                ]
                == period
            ]

            c = common[
                common[
                    "empirical_period"
                ]
                == period
            ]

        complete_books = (
            s[
                s[
                    "market_book_complete"
                ]
            ][
                [
                    "event_date",
                    "decision_rule",
                ]
            ]
            .drop_duplicates()
        )

        common_books = (
            c[
                [
                    "event_date",
                    "decision_rule",
                ]
            ]
            .drop_duplicates()
        )

        scored_books = (
            c[
                c[
                    "score_ready"
                ]
            ][
                [
                    "event_date",
                    "decision_rule",
                ]
            ]
            .drop_duplicates()
        )

        rows.append(
            {
                "analysis_period":
                    period,

                "certified_contract_rows":
                    len(t),

                "certified_market_dates":
                    t[
                        "event_date"
                    ].nunique(),

                "theoretical_market_cells":
                    len(s),

                "market_price_cells":
                    int(
                        s[
                            "market_price_available"
                        ].sum()
                    ),

                "complete_market_books":
                    len(
                        complete_books
                    ),

                "complete_market_dates":
                    complete_books[
                        "event_date"
                    ].nunique(),

                "weather_event_rows":
                    len(w),

                "exact_common_event_rows":
                    len(c),

                "exact_common_books":
                    len(
                        common_books
                    ),

                "exact_common_dates":
                    common_books[
                        "event_date"
                    ].nunique(),

                "score_ready_books":
                    len(
                        scored_books
                    ),

                "score_ready_dates":
                    scored_books[
                        "event_date"
                    ].nunique(),
            }
        )

    return pd.DataFrame(
        rows
    )


def disagreement_summary(
    books,
):
    rows = []

    for period in [
        "market_development",
        "external_validation",
        "all_exact_support",
    ]:
        if period == "all_exact_support":
            x = books
        else:
            x = books[
                books[
                    "empirical_period"
                ]
                == period
            ]

        if x.empty:
            continue

        row = {
            "analysis_period":
                period,

            "books":
                len(x),

            "dates":
                x[
                    "event_date"
                ].nunique(),

            "mean_market_minus_gp_expected_rank":
                x[
                    "market_minus_gp_expected_rank"
                ].mean(),
        }

        scored = x[
            x[
                "target_available"
            ].astype(bool)
        ]

        row[
            "mean_market_minus_gp_winner_probability"
        ] = (
            scored[
                "market_minus_gp_winner_probability"
            ].mean()
            if not scored.empty
            else np.nan
        )

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# FIGURES
# =============================================================================


def make_figures(
    tv,
    scores,
    snapshots,
):
    # Total variation.
    fig, ax = plt.subplots(
        figsize=(9, 5)
    )

    periods = [
        "market_development",
        "external_validation",
        "all_exact_support",
    ]

    sources = [
        "raw",
        "static",
        "selected_gp",
    ]

    width = 0.24

    x = np.arange(
        len(
            periods
        )
    )

    for i, source in enumerate(
        sources
    ):
        values = []

        for period in periods:
            row = tv[
                (
                    tv[
                        "analysis_period"
                    ]
                    == period
                )
                & (
                    tv[
                        "source"
                    ]
                    == source
                )
            ]

            values.append(
                (
                    row[
                        "date_balanced_tv"
                    ].iloc[0]
                    if not row.empty
                    else np.nan
                )
            )

        ax.bar(
            x
            + (
                i - 1
            )
            * width,
            values,
            width=width,
            label=source,
        )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        [
            "Mar–Jun development",
            "Jul–Aug external",
            "All exact support",
        ]
    )

    ax.set_ylabel(
        "Date-balanced total variation"
    )

    ax.set_title(
        "Weather probability-book distance to Polymarket"
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        TV_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    # External proper scores.
    ext = scores[
        scores[
            "analysis_period"
        ]
        == "external_validation"
    ].copy()

    if not ext.empty:
        fig, ax = plt.subplots(
            figsize=(10, 5)
        )

        methods = [
            "static",
            "selected_gp",
            "pool",
            "market",
        ]

        metrics = [
            "binary_brier",
            "binary_log",
            "categorical_log",
            "multiclass_brier",
        ]

        width = 0.19

        x = np.arange(
            len(
                metrics
            )
        )

        for i, method in enumerate(
            methods
        ):
            row = ext[
                ext[
                    "source"
                ]
                == method
            ]

            if row.empty:
                continue

            values = [
                row[
                    metric
                ].iloc[0]
                for metric
                in metrics
            ]

            ax.bar(
                x
                + (
                    i - 1.5
                )
                * width,
                values,
                width=width,
                label=method,
            )

        ax.set_xticks(
            x
        )

        ax.set_xticklabels(
            [
                "Binary Brier",
                "Binary log",
                "Categorical log",
                "Multiclass Brier",
            ]
        )

        ax.set_ylabel(
            "Loss"
        )

        ax.set_title(
            "External July–August exact-support losses"
        )

        ax.legend()

        fig.tight_layout()

        fig.savefig(
            EXTERNAL_SCORE_FIGURE,
            dpi=200,
            bbox_inches="tight",
        )

        plt.close(
            fig
        )

    # Market-book probability sums.
    complete = (
        snapshots[
            snapshots[
                "market_book_complete"
            ]
        ][
            [
                "event_date",
                "decision_rule",
                "market_book_sum",
            ]
        ]
        .drop_duplicates()
    )

    if not complete.empty:
        fig, ax = plt.subplots(
            figsize=(7, 5)
        )

        ax.hist(
            complete[
                "market_book_sum"
            ],
            bins=30,
        )

        ax.axvline(
            1.0,
            linestyle="--",
        )

        ax.set_xlabel(
            "Raw eleven-contract YES sum"
        )

        ax.set_ylabel(
            "Book count"
        )

        ax.set_title(
            "Polymarket book coherence"
        )

        fig.tight_layout()

        fig.savefig(
            BOOK_SUM_FIGURE,
            dpi=200,
            bbox_inches="tight",
        )

        plt.close(
            fig
        )


# =============================================================================
# INTEGRITY CHECKS
# =============================================================================


def build_integrity_checks(
    candidates,
    universe,
    targets,
    history,
    snapshots,
    weather_probs,
    mass_audit,
    common,
    books,
    pool_weight,
    score_summary,
    support_summary,
):
    known_targets = targets[
        targets[
            "target_available"
        ].astype(bool)
    ]

    winner_counts = (
        known_targets.groupby(
            "event_date"
        )[
            "Y"
        ]
        .sum()
    )

    complete_books = (
        snapshots[
            snapshots[
                "market_book_complete"
            ]
        ][
            [
                "event_date",
                "decision_rule",
            ]
        ]
        .drop_duplicates()
    )

    selected_with_price = snapshots[
        snapshots[
            "market_price_available"
        ]
    ]

    no_lookahead = True
    negative_age = False

    if not selected_with_price.empty:
        selected_ts = pd.to_datetime(
            selected_with_price[
                "selected_price_timestamp_utc"
            ],
            utc=True,
        )

        cutoffs = pd.to_datetime(
            selected_with_price[
                "decision_cutoff_utc"
            ],
            utc=True,
        )

        no_lookahead = bool(
            (
                selected_ts
                <= cutoffs
            ).all()
        )

        negative_age = bool(
            (
                selected_with_price[
                    "record_age_hours"
                ]
                < -1e-9
            ).any()
        )

    exact_books = (
        common[
            [
                "event_date",
                "decision_rule",
            ]
        ]
        .drop_duplicates()
    )

    exact_book_sizes = (
        common.groupby(
            [
                "event_date",
                "decision_rule",
            ]
        )
        .size()
    )

    development_score = score_summary[
        score_summary[
            "analysis_period"
        ]
        == "market_development"
    ]

    external_score = score_summary[
        score_summary[
            "analysis_period"
        ]
        == "external_validation"
    ]

    checks = [
        {
            "check":
                "gamma_candidates_nonempty",
            "passed":
                len(
                    candidates
                )
                > 0,
            "observed":
                len(
                    candidates
                ),
            "expected":
                ">0",
            "notes":
                "",
        },

        {
            "check":
                "certified_contract_universe_nonempty",
            "passed":
                len(
                    universe
                )
                > 0,
            "observed":
                len(
                    universe
                ),
            "expected":
                ">0",
            "notes":
                "",
        },

        {
            "check":
                "all_certified_dates_have_11_contracts",
            "passed":
                (
                    universe.groupby(
                        "event_date"
                    )
                    .size()
                    .eq(
                        11
                    )
                    .all()
                ),
            "observed":
                int(
                    universe.groupby(
                        "event_date"
                    )
                    .size()
                    .eq(
                        11
                    )
                    .all()
                ),
            "expected":
                1,
            "notes":
                "",
        },

        {
            "check":
                "all_known_target_dates_have_one_winner",
            "passed":
                winner_counts.eq(
                    1
                ).all(),
            "observed":
                int(
                    winner_counts.eq(
                        1
                    ).all()
                ),
            "expected":
                1,
            "notes":
                "",
        },

        {
            "check":
                "price_history_nonempty",
            "passed":
                len(
                    history
                )
                > 0,
            "observed":
                len(
                    history
                ),
            "expected":
                ">0",
            "notes":
                "",
        },

        {
            "check":
                "all_selected_market_prices_in_unit_interval",
            "passed":
                (
                    selected_with_price[
                        "market_raw_yes"
                    ]
                    .between(
                        0.0,
                        1.0,
                    )
                    .all()
                ),
            "observed":
                int(
                    selected_with_price[
                        "market_raw_yes"
                    ]
                    .between(
                        0.0,
                        1.0,
                    )
                    .all()
                ),
            "expected":
                1,
            "notes":
                "",
        },

        {
            "check":
                "market_no_lookahead",
            "passed":
                no_lookahead,
            "observed":
                int(
                    no_lookahead
                ),
            "expected":
                1,
            "notes":
                "",
        },

        {
            "check":
                "nonnegative_market_record_age",
            "passed":
                not negative_age,
            "observed":
                int(
                    negative_age
                ),
            "expected":
                0,
            "notes":
                "",
        },

        {
            "check":
                "some_complete_market_books",
            "passed":
                len(
                    complete_books
                )
                > 0,
            "observed":
                len(
                    complete_books
                ),
            "expected":
                ">0",
            "notes":
                "",
        },

        {
            "check":
                "weather_probability_books_have_11_events",
            "passed":
                mass_audit[
                    "contracts"
                ].eq(
                    11
                ).all(),
            "observed":
                int(
                    mass_audit[
                        "contracts"
                    ].eq(
                        11
                    ).all()
                ),
            "expected":
                1,
            "notes":
                "",
        },

        {
            "check":
                "weather_probability_mass",
            "passed":
                mass_audit[
                    "max_mass_error"
                ].max()
                < 1e-10,
            "observed":
                float(
                    mass_audit[
                        "max_mass_error"
                    ].max()
                ),
            "expected":
                "<1e-10",
            "notes":
                "",
        },

        {
            "check":
                "exact_common_support_nonempty",
            "passed":
                len(
                    common
                )
                > 0,
            "observed":
                len(
                    common
                ),
            "expected":
                ">0",
            "notes":
                "",
        },

        {
            "check":
                "exact_common_books_have_11_rows",
            "passed":
                exact_book_sizes.eq(
                    11
                ).all(),
            "observed":
                int(
                    exact_book_sizes.eq(
                        11
                    ).all()
                ),
            "expected":
                1,
            "notes":
                "",
        },

        {
            "check":
                "external_exact_support_exists",
            "passed":
                (
                    common[
                        "empirical_period"
                    ]
                    == "external_validation"
                ).any(),
            "observed":
                int(
                    (
                        common[
                            "empirical_period"
                        ]
                        == "external_validation"
                    ).any()
                ),
            "expected":
                1,
            "notes":
                "",
        },

        {
            "check":
                "pool_weight_in_unit_interval",
            "passed":
                (
                    0.0
                    <= pool_weight
                    <= 1.0
                ),
            "observed":
                pool_weight,
            "expected":
                "[0,1]",
            "notes":
                "selected on March–June only",
        },

        {
            "check":
                "development_scores_exist",
            "passed":
                not development_score.empty,
            "observed":
                len(
                    development_score
                ),
            "expected":
                ">0",
            "notes":
                "",
        },

        {
            "check":
                "external_scores_exist",
            "passed":
                not external_score.empty,
            "observed":
                len(
                    external_score
                ),
            "expected":
                ">0",
            "notes":
                "31 Aug may remain target-pending",
        },

        {
            "check":
                "support_summary_has_three_period_rows",
            "passed":
                len(
                    support_summary
                )
                == 3,
            "observed":
                len(
                    support_summary
                ),
            "expected":
                3,
            "notes":
                "",
        },
    ]

    status = (
        "PASS"
        if all(
            row[
                "passed"
            ]
            for row in checks
        )
        else "FAILED"
    )

    return (
        pd.DataFrame(
            checks
        ),
        status,
    )


# =============================================================================
# MAIN
# =============================================================================





def main():
    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -------------------------------------------------------------------------
    # Step 24: Gamma acquisition
    # -------------------------------------------------------------------------

    print(
        "Step 24: discovering Polymarket markets..."
    )

    (
        gamma_markets,
        gamma_diag,
    ) = discover_gamma_markets()

    gamma_diag.to_csv(
        GAMMA_FETCH_DIAGNOSTICS,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 25: contract certification
    # -------------------------------------------------------------------------

    print(
        "Step 25: parsing/certifying contract-event universe..."
    )

    candidates = (
        candidate_rows_from_gamma(
            gamma_markets
        )
    )

    candidates.to_csv(
        CONTRACT_CANDIDATES,
        index=False,
    )

    (
        universe,
        issues,
    ) = certify_contract_universe(
        candidates
    )

    universe.to_csv(
        CONTRACT_UNIVERSE,
        index=False,
    )

    issues.to_csv(
        UNIVERSE_ISSUES,
        index=False,
    )

    date_summary = (
        universe.groupby(
            "event_date"
        )
        .agg(
            contracts=(
                "market_id",
                "size",
            ),

            lower_tails=(
                "contract_event_type",
                lambda x:
                    (
                        x
                        == "lower_tail_endpoint"
                    ).sum(),
            ),

            interiors=(
                "contract_event_type",
                lambda x:
                    (
                        x
                        == "interior_bin"
                    ).sum(),
            ),

            upper_tails=(
                "contract_event_type",
                lambda x:
                    (
                        x
                        == "upper_tail"
                    ).sum(),
            ),
        )
        .reset_index()
    )

    date_summary.to_csv(
        CONTRACT_DATE_SUMMARY,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 26: HKO targets
    # -------------------------------------------------------------------------

    print(
        "Step 26: joining HKO outcomes..."
    )

    targets = (
        build_contract_targets(
            universe
        )
    )

    targets.to_csv(
        CONTRACT_TARGETS,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 27: CLOB price histories
    # -------------------------------------------------------------------------

    print(
        "Step 27: recovering CLOB YES-token histories..."
    )

    (
        history,
        clob_diag,
    ) = recover_price_histories(
        targets
    )

    history.to_csv(
        PRICE_HISTORY_PANEL,
        index=False,
        compression="gzip",
    )

    clob_diag.to_csv(
        CLOB_FETCH_DIAGNOSTICS,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 28: no-look-ahead snapshots
    # -------------------------------------------------------------------------

    print(
        "Step 28: building four decision snapshots..."
    )

    snapshots = (
        build_decision_snapshots(
            targets,
            history,
        )
    )

    snapshots.to_csv(
        DECISION_SNAPSHOTS,
        index=False,
        compression="gzip",
    )

    snapshots[
        ~snapshots[
            "market_price_available"
        ]
    ].to_csv(
        MISSING_SNAPSHOTS,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 29: market-only scoring
    # -------------------------------------------------------------------------

    print(
        "Step 29: market-only scoring..."
    )

    (
        market_scores,
        market_books,
    ) = market_only_summaries(
        snapshots
    )

    market_scores.to_csv(
        MARKET_SCORE_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    market_books.to_csv(
        MARKET_BOOK_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 30: weather event probabilities
    # -------------------------------------------------------------------------

    print(
        "Step 30: mapping frozen weather laws into eleven events..."
    )

    weather_probs = (
        build_weather_event_probabilities(
            targets
        )
    )

    weather_probs.to_csv(
        WEATHER_EVENT_PROBS,
        index=False,
        compression="gzip",
    )

    mass_audit = (
        probability_mass_audit(
            weather_probs
        )
    )

    mass_audit.to_csv(
        WEATHER_MASS_AUDIT,
        index=False,
        float_format="%.12f",
    )

    # -------------------------------------------------------------------------
    # Step 31: exact common support
    # -------------------------------------------------------------------------

    print(
        "Step 31: building exact complete-book common support..."
    )

    common = (
        build_exact_common(
            weather_probs,
            snapshots,
        )
    )

    # -------------------------------------------------------------------------
    # Step 32: pre-pool proper-score and TV objects
    # -------------------------------------------------------------------------

    print(
        "Step 32: constructing exact-support book metrics..."
    )

    books_pre_pool = (
        construct_book_metrics(
            common
        )
    )

    # -------------------------------------------------------------------------
    # Step 33: total variation / disagreement
    # -------------------------------------------------------------------------

    print(
        "Step 33: probability-book reconciliation diagnostics..."
    )

    tv_pre_pool = (
        tv_summary(
            books_pre_pool
        )
    )

    # -------------------------------------------------------------------------
    # Step 34: development-only convex pool
    # -------------------------------------------------------------------------

    print(
        "Step 34: selecting convex pool on March–June only..."
    )

    (
        pool_weight,
        pool_grid,
    ) = select_convex_pool(
        common
    )

    pool_grid.to_csv(
        POOL_GRID_OUTPUT,
        index=False,
        float_format="%.10f",
    )

    pool_selection = {
        "weight_gp":
            pool_weight,

        "weight_market":
            1.0
            - pool_weight,

        "grid_start":
            0.0,

        "grid_end":
            1.0,

        "grid_step":
            0.001,

        "selection_period":
            "2026-03-16 to 2026-06-30",

        "selection_metric":
            "date-balanced categorical log loss",

        "selected_weather_source":
            "weather-selected GP",

        "external_validation_used":
            False,

        "trading_pnl_used":
            False,
    }

    POOL_SELECTION_JSON.write_text(
        json.dumps(
            pool_selection,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    # -------------------------------------------------------------------------
    # Step 35: apply frozen pool + proper-score evaluation
    # -------------------------------------------------------------------------

    print(
        "Step 35: applying frozen pool and scoring development/external periods..."
    )

    common = apply_pool_probabilities(
        common,
        pool_weight,
    )

    common.to_csv(
        EXACT_COMMON_EVENTS,
        index=False,
        compression="gzip",
    )

    books = construct_book_metrics(
        common,
        pool_weight=
            pool_weight,
    )

    books.to_csv(
        BOOK_METRICS,
        index=False,
        float_format="%.10f",
    )

    score_summary = (
        proper_score_summary(
            books
        )
    )

    score_summary.to_csv(
        SCORE_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    tv = tv_summary(
        books
    )

    tv.to_csv(
        TV_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    disagreement = (
        disagreement_summary(
            books
        )
    )

    disagreement.to_csv(
        DISAGREEMENT_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 36: paired date-level inference
    # -------------------------------------------------------------------------

    print(
        "Step 36: paired date-level inference..."
    )

    date_losses = (
        construct_date_losses(
            books
        )
    )

    date_losses.to_csv(
        DATE_LOSSES,
        index=False,
        float_format="%.10f",
    )

    bootstrap = (
        paired_bootstrap_summary(
            date_losses
        )
    )

    bootstrap.to_csv(
        BOOTSTRAP_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 37: final audit
    # -------------------------------------------------------------------------

    print(
        "Step 37: final market-stage audit..."
    )

    support_summary = (
        exact_support_summary(
            targets,
            snapshots,
            weather_probs,
            common,
        )
    )

    support_summary.to_csv(
        EXACT_SUPPORT_SUMMARY,
        index=False,
    )

    (
        checks,
        status,
    ) = build_integrity_checks(
        candidates,
        universe,
        targets,
        history,
        snapshots,
        weather_probs,
        mass_audit,
        common,
        books,
        pool_weight,
        score_summary,
        support_summary,
    )

    checks.to_csv(
        CHECKS_CSV,
        index=False,
    )

    make_figures(
        tv,
        score_summary,
        snapshots,
    )

    pending_target_dates = sorted(
        targets.loc[
            ~targets[
                "target_available"
            ].astype(bool),
            "event_date",
        ]
        .drop_duplicates()
        .tolist()
    )

    selected_kernel = json.loads(
        WEATHER_SELECTION.read_text()
    )[
        "selected_kernel"
    ]

    summary = {
        "status":
            status,

        "stage":
            "steps_24_37",

        "study_start":
            START_DATE.strftime(
                "%Y-%m-%d"
            ),

        "study_end":
            END_DATE.strftime(
                "%Y-%m-%d"
            ),

        "development_end":
            DEVELOPMENT_END.strftime(
                "%Y-%m-%d"
            ),

        "external_start":
            EXTERNAL_START.strftime(
                "%Y-%m-%d"
            ),

        "gamma_markets_downloaded":
            len(
                gamma_markets
            ),

        "hong_kong_temperature_candidates":
            len(
                candidates
            ),

        "certified_contract_rows":
            len(
                universe
            ),

        "certified_market_dates":
            int(
                universe[
                    "event_date"
                ].nunique()
            ),

        "certified_books_are_11_contracts":
            bool(
                universe.groupby(
                    "event_date"
                )
                .size()
                .eq(
                    11
                )
                .all()
            ),

        "price_history_rows":
            len(
                history
            ),

        "price_tokens":
            int(
                history[
                    "yes_token_id"
                ].nunique()
            ),

        "decision_snapshot_cells":
            len(
                snapshots
            ),

        "decision_price_cells":
            int(
                snapshots[
                    "market_price_available"
                ].sum()
            ),

        "missing_decision_price_cells":
            int(
                (
                    ~snapshots[
                        "market_price_available"
                    ].astype(bool)
                ).sum()
            ),

        "complete_market_books":
            int(
                snapshots[
                    snapshots[
                        "market_book_complete"
                    ]
                ][
                    [
                        "event_date",
                        "decision_rule",
                    ]
                ]
                .drop_duplicates()
                .shape[0]
            ),

        "weather_event_probability_rows":
            len(
                weather_probs
            ),

        "weather_probability_books":
            len(
                mass_audit
            ),

        "maximum_weather_probability_mass_error":
            float(
                mass_audit[
                    "max_mass_error"
                ].max()
            ),

        "exact_common_event_rows":
            len(
                common
            ),

        "exact_common_books":
            int(
                common[
                    [
                        "event_date",
                        "decision_rule",
                    ]
                ]
                .drop_duplicates()
                .shape[0]
            ),

        "exact_common_dates":
            int(
                common[
                    "event_date"
                ].nunique()
            ),

        "score_ready_books":
            int(
                books[
                    "target_available"
                ].sum()
            ),

        "score_ready_dates":
            int(
                books.loc[
                    books[
                        "target_available"
                    ].astype(bool),
                    "event_date",
                ].nunique()
            ),

        "pending_target_dates":
            pending_target_dates,

        "selected_weather_kernel":
            selected_kernel,

        "pool_weight_gp":
            pool_weight,

        "pool_weight_market":
            1.0
            - pool_weight,

        "pool_selection_uses_external":
            False,

        "pool_selection_uses_pnl":
            False,

        "binary_market_probability":
            "raw event-level YES value",

        "categorical_market_probability":
            "normalised complete eleven-event YES book",

        "raw_weather_book":
            "deterministic one-hot event book",

        "static_weather_book":
            "Gaussian static residual law mapped analytically through event boundaries",

        "selected_gp_weather_book":
            "weather-selected Gaussian GP law mapped analytically through event boundaries",

        "clob_history_window_days":
            PRICE_HISTORY_WINDOW_DAYS,

        "clob_history_fidelity_minutes":
            PRICE_HISTORY_FIDELITY_MINUTES,

        "bootstrap_replications":
            BOOTSTRAP_REPS,

        "moving_block_length":
            BLOCK_LENGTH,

        "contract_universe_sha256":
            sha256_file(
                CONTRACT_UNIVERSE
            ),

        "decision_snapshots_sha256":
            sha256_file(
                DECISION_SNAPSHOTS
            ),

        "weather_event_probabilities_sha256":
            sha256_file(
                WEATHER_EVENT_PROBS
            ),

        "exact_common_events_sha256":
            sha256_file(
                EXACT_COMMON_EVENTS
            ),

        "generated_utc":
            datetime.now(
                UTC
            ).isoformat(),
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    provenance = {
        "gamma_endpoint":
            GAMMA_ENDPOINT,

        "clob_price_history_endpoint":
            CLOB_HISTORY_ENDPOINT,

        "gamma_query_period":
            "end_date_min=2026-03-14; end_date_max=2026-09-03",

        "gamma_closed_states_queried":
            [
                True,
                False,
            ],

        "event_date_source":
            "visible market slug/question/event title; API closing date not used as contract date",

        "temperature_boundary_source":
            "visible groupItemTitle/question/slug; groupItemThreshold retained only as metadata",

        "settlement_family":
            "HKO Daily Extract one-decimal",

        "lower_endpoint_rule":
            "k°C or below -> (-infinity, k+1)",

        "interior_rule":
            "k°C -> [k,k+1)",

        "upper_rule":
            "K°C or higher -> [K,infinity)",

        "price_selection_rule":
            "latest recovered YES-token observation no later than decision cutoff",

        "price_history_fidelity_minutes":
            PRICE_HISTORY_FIDELITY_MINUTES,

        "price_history_window_days":
            PRICE_HISTORY_WINDOW_DAYS,

        "retrieved_utc":
            datetime.now(
                UTC
            ).isoformat(),
    }

    PROVENANCE_JSON.write_text(
        json.dumps(
            provenance,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print()
    print(
        "status="
        + status
    )
    print(
        "certified_market_dates="
        + str(
            summary[
                "certified_market_dates"
            ]
        )
    )
    print(
        "certified_contract_rows="
        + str(
            summary[
                "certified_contract_rows"
            ]
        )
    )
    print(
        "decision_price_cells="
        + str(
            summary[
                "decision_price_cells"
            ]
        )
    )
    print(
        "complete_market_books="
        + str(
            summary[
                "complete_market_books"
            ]
        )
    )
    print(
        "exact_common_dates="
        + str(
            summary[
                "exact_common_dates"
            ]
        )
    )
    print(
        "exact_common_books="
        + str(
            summary[
                "exact_common_books"
            ]
        )
    )
    print(
        "pool_weight_gp="
        + f"{pool_weight:.3f}"
    )

    if status != "PASS":
        failed = checks[
            ~checks[
                "passed"
            ]
        ]

        print(
            "failed_checks="
            + failed.to_json(
                orient="records"
            )
        )

        return 2

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
