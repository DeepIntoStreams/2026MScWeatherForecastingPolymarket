from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.trading_contrast_extension import stage2 as s2


ROOT = Path(".")
OUT = ROOT / "outputs/trading_contrast_extension/stage2"
PANEL_PATH = OUT / "canonical_four_model_event_panel.csv.gz"

PRIORITY_PATHS = [
    ROOT
    / "data/processed/final_pipeline/weather_models/"
    / "frozen_weather_model_predictions_mar_aug.csv",
    ROOT
    / "data/processed/final_pipeline/market/"
    / "weather_event_probabilities.csv.gz",
]


def one_numeric_per_book(
    x: pd.DataFrame,
    col: str,
) -> pd.DataFrame:
    y = x[
        ["event_date", "decision_rule", col]
    ].copy()

    y[col] = pd.to_numeric(
        y[col],
        errors="coerce",
    )

    def collapse(s: pd.Series) -> float:
        vals = s.dropna().unique()

        if len(vals) == 0:
            return np.nan

        if len(vals) > 1:
            if float(np.max(vals) - np.min(vals)) > 1e-10:
                raise RuntimeError(
                    f"Multiple {col} values within one date/rule."
                )

        return float(vals[0])

    return (
        y.groupby(
            ["event_date", "decision_rule"],
            as_index=False,
        )
        .agg(**{
            col: (
                col,
                collapse,
            )
        })
    )


def ranked_mean_cols(
    columns: list[str],
    require_rbf: bool,
) -> list[str]:
    scored = []

    for c in columns:
        lc = c.lower()

        if require_rbf and "rbf" not in lc:
            continue

        if any(
            bad in lc
            for bad in [
                "error",
                "residual",
                "target",
                "hko",
                "crps",
                "loss",
                "score",
                "prob",
                "price",
                "sd",
                "std",
                "sigma",
                "scale",
                "variance",
            ]
        ):
            continue

        score = 0

        if "rbf" in lc:
            score += 20
        if "mean" in lc:
            score += 8
        if "forecast" in lc:
            score += 7
        if "prediction" in lc or "predicted" in lc:
            score += 6
        if "_mu" in lc:
            score += 5
        if lc.endswith("_c"):
            score += 2

        if score > 0:
            scored.append((score, c))

    scored.sort(
        key=lambda z: (z[0], -len(z[1])),
        reverse=True,
    )

    return [c for _, c in scored]


def ranked_sd_cols(
    columns: list[str],
    require_rbf: bool,
) -> list[str]:
    scored = []

    for c in columns:
        lc = c.lower()

        if require_rbf and "rbf" not in lc:
            continue

        if any(
            bad in lc
            for bad in [
                "error",
                "residual",
                "target",
                "hko",
                "crps",
                "loss",
                "score",
            ]
        ):
            continue

        score = 0

        if "rbf" in lc:
            score += 20
        if "sd" in lc:
            score += 9
        if "std" in lc:
            score += 9
        if "sigma" in lc:
            score += 9
        if "scale" in lc:
            score += 7

        if "mean" in lc:
            score -= 30

        if score > 0:
            scored.append((score, c))

    scored.sort(
        key=lambda z: (z[0], -len(z[1])),
        reverse=True,
    )

    return [c for _, c in scored]


def find_model_col(
    x: pd.DataFrame,
) -> str | None:
    for c in [
        "model",
        "method",
        "weather_model",
        "kernel",
        "source",
    ]:
        if c in x.columns:
            mapped = x[c].map(
                s2.normalize_model_name
            )

            if (mapped == "rbf").any():
                return c

    for c in x.columns:
        if x[c].dtype != object:
            continue

        mapped = x[c].map(
            s2.normalize_model_name
        )

        if (mapped == "rbf").any():
            return c

    return None


def candidate_paths() -> list[Path]:
    paths: list[Path] = []

    for p in PRIORITY_PATHS:
        if p.exists():
            paths.append(p)

    for root in [
        ROOT / "data/processed/final_pipeline",
        ROOT / "outputs/final_pipeline",
    ]:
        if not root.exists():
            continue

        for p in sorted(root.rglob("*.csv*")):
            if p in paths:
                continue

            try:
                small = pd.read_csv(
                    p,
                    nrows=25,
                )
            except Exception:
                continue

            cols_have_rbf = any(
                "rbf" in c.lower()
                for c in small.columns
            )

            values_have_rbf = False

            for c in small.columns:
                if small[c].dtype == object:
                    if (
                        small[c]
                        .astype(str)
                        .str.lower()
                        .str.contains(
                            "rbf",
                            regex=False,
                        )
                        .any()
                    ):
                        values_have_rbf = True
                        break

            if cols_have_rbf or values_have_rbf:
                paths.append(p)

    return paths


def parameter_candidate(
    path: Path,
) -> tuple[pd.DataFrame, dict] | None:
    try:
        x = pd.read_csv(path)
        x = s2.normalize_date_rule(x)
    except Exception:
        return None

    mcol = find_model_col(x)

    if mcol is not None:
        mapped = x[mcol].map(
            s2.normalize_model_name
        )

        xr = x.loc[
            mapped == "rbf"
        ].copy()

        means = ranked_mean_cols(
            list(xr.columns),
            require_rbf=False,
        )
        sds = ranked_sd_cols(
            list(xr.columns),
            require_rbf=False,
        )

        for mean_col in means:
            for sd_col in sds:
                if mean_col == sd_col:
                    continue

                mean_table = one_numeric_per_book(
                    xr,
                    mean_col,
                )
                sd_table = one_numeric_per_book(
                    xr,
                    sd_col,
                )

                pars = mean_table.merge(
                    sd_table,
                    on=[
                        "event_date",
                        "decision_rule",
                    ],
                    how="outer",
                    validate="one_to_one",
                ).rename(
                    columns={
                        mean_col: "mean_c",
                        sd_col: "sd_c",
                    }
                )

                good = (
                    pars["mean_c"].notna()
                    & pars["sd_c"].notna()
                    & (pars["sd_c"] > 0)
                )

                if good.mean() >= 0.99:
                    return pars, {
                        "path": str(path),
                        "format": "long",
                        "model_col": mcol,
                        "mean_col": mean_col,
                        "sd_col": sd_col,
                    }

    means = ranked_mean_cols(
        list(x.columns),
        require_rbf=True,
    )
    sds = ranked_sd_cols(
        list(x.columns),
        require_rbf=True,
    )

    for mean_col in means:
        for sd_col in sds:
            if mean_col == sd_col:
                continue

            mean_table = one_numeric_per_book(
                x,
                mean_col,
            )
            sd_table = one_numeric_per_book(
                x,
                sd_col,
            )

            pars = mean_table.merge(
                sd_table,
                on=[
                    "event_date",
                    "decision_rule",
                ],
                how="outer",
                validate="one_to_one",
            ).rename(
                columns={
                    mean_col: "mean_c",
                    sd_col: "sd_c",
                }
            )

            good = (
                pars["mean_c"].notna()
                & pars["sd_c"].notna()
                & (pars["sd_c"] > 0)
            )

            if good.mean() >= 0.99:
                return pars, {
                    "path": str(path),
                    "format": "wide",
                    "mean_col": mean_col,
                    "sd_col": sd_col,
                }

    return None


def derive(
    panel: pd.DataFrame,
    pars: pd.DataFrame,
) -> pd.Series:
    m = panel[
        [
            "event_date",
            "decision_rule",
            "event_lower_c",
            "event_upper_c",
        ]
    ].merge(
        pars,
        on=[
            "event_date",
            "decision_rule",
        ],
        how="left",
        validate="many_to_one",
    )

    if m["mean_c"].isna().any():
        raise RuntimeError(
            "RBF predictive mean does not cover all canonical event rows."
        )

    if (
        m["sd_c"].isna().any()
        or (m["sd_c"] <= 0).any()
    ):
        raise RuntimeError(
            "Invalid RBF predictive SD."
        )

    mean = m["mean_c"].to_numpy(float)
    sd = m["sd_c"].to_numpy(float)
    lower = m["event_lower_c"].to_numpy(float)
    upper = m["event_upper_c"].to_numpy(float)

    p = (
        norm.cdf(
            (upper - mean) / sd
        )
        - norm.cdf(
            (lower - mean) / sd
        )
    )

    return pd.Series(
        p,
        index=panel.index,
        dtype=float,
    )


def book_check(
    panel: pd.DataFrame,
    p: pd.Series,
) -> dict:
    z = panel[
        ["event_date", "decision_rule"]
    ].copy()

    z["p"] = p.to_numpy()

    mass = (
        z.groupby(
            ["event_date", "decision_rule"]
        )["p"]
        .sum()
    )

    return {
        "books": int(len(mass)),
        "max_probability_mass_error": float(
            np.abs(
                mass.to_numpy()
                - 1.0
            ).max()
        ),
        "books_sum_to_one": bool(
            np.isclose(
                mass,
                1.0,
                atol=5e-6,
            ).all()
        ),
        "valid_probabilities": bool(
            (
                (p >= -1e-12)
                & (p <= 1 + 1e-12)
            ).all()
        ),
    }


def main() -> None:
    panel = pd.read_csv(
        PANEL_PATH
    )

    static = panel[
        "p_static"
    ].astype(float)

    old_rbf = panel[
        "p_rbf"
    ].astype(float)

    attempts = []
    accepted = None

    for path in candidate_paths():
        candidate = parameter_candidate(
            path
        )

        if candidate is None:
            continue

        pars, provenance = candidate

        try:
            p = derive(
                panel,
                pars,
            )
        except Exception as exc:
            provenance[
                "rejected_reason"
            ] = str(exc)
            attempts.append(
                provenance
            )
            continue

        checks = book_check(
            panel,
            p,
        )

        d = (
            p
            - static
        ).abs()

        provenance.update(
            checks
        )
        provenance[
            "max_abs_difference_from_static"
        ] = float(d.max())
        provenance[
            "rows_different_from_static_gt_1e_12"
        ] = int(
            (d > 1e-12).sum()
        )

        attempts.append(
            provenance
        )

        if (
            checks[
                "books_sum_to_one"
            ]
            and checks[
                "valid_probabilities"
            ]
            and provenance[
                "rows_different_from_static_gt_1e_12"
            ]
            > 0
        ):
            accepted = (
                p,
                pars,
                provenance,
            )
            break

    pre_diff = (
        old_rbf
        - static
    ).abs()

    audit = {
        "pre_repair_max_abs_rbf_minus_static": float(
            pre_diff.max()
        ),
        "pre_repair_rows_different_gt_1e_12": int(
            (pre_diff > 1e-12).sum()
        ),
        "candidate_attempts": attempts,
    }

    if accepted is None:
        (
            OUT
            / "rbf_provenance_repair_audit.json"
        ).write_text(
            json.dumps(
                audit,
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n"
        )

        raise RuntimeError(
            "No distinct explicit frozen RBF predictive law could be "
            "verified. Stage 3 is blocked."
        )

    p, pars, provenance = accepted

    panel["p_rbf"] = p

    post_diff = (
        panel["p_rbf"]
        - panel["p_static"]
    ).abs()

    audit.update(
        {
            "repair_applied": True,
            "accepted_provenance": provenance,
            "post_repair_max_abs_rbf_minus_static": float(
                post_diff.max()
            ),
            "post_repair_mean_abs_rbf_minus_static": float(
                post_diff.mean()
            ),
            "post_repair_rows_different_gt_1e_12": int(
                (post_diff > 1e-12).sum()
            ),
        }
    )

    if audit[
        "post_repair_rows_different_gt_1e_12"
    ] == 0:
        raise RuntimeError(
            "Verified explicit RBF source is still identical to Static."
        )

    panel.to_csv(
        PANEL_PATH,
        index=False,
        compression="gzip",
    )

    pars.to_csv(
        OUT
        / "explicit_rbf_predictive_parameters.csv",
        index=False,
    )

    (
        OUT
        / "rbf_provenance_repair_audit.json"
    ).write_text(
        json.dumps(
            audit,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n"
    )

    print(
        json.dumps(
            audit,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
