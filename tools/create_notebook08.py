#!/usr/bin/env python3
"""Create canonical Notebook 08."""

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


def markdown(text: str):
    return nbf.v4.new_markdown_cell(
        dedent(text).strip()
    )


def code(text: str):
    return nbf.v4.new_code_cell(
        dedent(text).strip()
    )


notebook = nbf.v4.new_notebook()

notebook["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
}

notebook["cells"] = [
    markdown(
        """
        # 08 — Locked Event Probabilities

        This notebook converts each locked calibrated temperature
        distribution into probabilities over the certified eleven-event
        partition.

        The construction does not use realised outcomes or market prices.
        """
    ),
    code(
        """
        from pathlib import Path
        import json
        import subprocess
        import sys

        import pandas as pd

        def locate_repository(start: Path) -> Path:
            current = start.resolve()

            for candidate in (current, *current.parents):
                if (
                    candidate
                    / "config/"
                    "event_probability_construction_spec.yaml"
                ).exists():
                    return candidate

            raise FileNotFoundError("Repository root not found.")

        ROOT = locate_repository(Path.cwd())

        completed = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "tools/"
                    "construct_locked_event_probabilities.py"
                ),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        print(completed.stdout)

        if completed.returncode != 0:
            print(completed.stderr)
            raise RuntimeError(
                "Locked event probability construction failed."
            )
        """
    ),
    markdown(
        r"""
        ## Quantile-particle construction

        For settlement date \(d\), decision rule \(r\), and event \(A_{d,j}\),
        define

        \[
        \widehat p_{d,r,j}
        =
        \frac{1}{99}
        \sum_{m=1}^{99}
        \mathbf 1
        \left\{
        \widehat Q_{d,r}\!\left(\frac{m}{100}\right)
        \in A_{d,j}
        \right\}.
        \]

        The 99 predictive quantiles are treated as equally weighted
        deterministic quadrature particles. They are not interpreted as
        independent Monte Carlo draws.
        """
    ),
    code(
        """
        probabilities = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "08_locked_event_probability_panel.csv"
        )

        summary = pd.read_csv(
            ROOT
            / "outputs/final_tables/"
            "08_event_probability_book_summary.csv"
        )

        print(
            "Probability rows:",
            len(probabilities),
        )

        print(
            "Prediction books:",
            probabilities["row_id"].nunique(),
        )

        print(
            "Events per book:",
            probabilities.groupby("row_id").size().min(),
        )

        print(
            "Maximum probability-sum error:",
            (
                summary["probability_sum"]
                - 1.0
            ).abs().max(),
        )
        """
    ),
    markdown(
        r"""
        ## Event boundaries

        Every event is left closed and right open. Thus a value equal to an
        integer boundary enters the interval beginning at that boundary.

        The lowest event is unbounded below and the highest event is
        unbounded above. The eleven events therefore form a complete
        partition of the real line.
        """
    ),
    code(
        """
        example_row_id = probabilities["row_id"].iloc[0]

        example = probabilities.loc[
            probabilities["row_id"].eq(example_row_id),
            [
                "event_order",
                "event_label",
                "quantile_particle_count",
                "raw_event_probability",
            ],
        ]

        print(example.to_string(index=False))
        """
    ),
    markdown(
        """
        ## Probability resolution and zero values

        Since 99 particles are used, every raw event probability is a multiple
        of \(1/99\).

        Events containing no particle retain probability zero at this stage.
        No clipping, additive constant or uniform mixing is introduced
        retrospectively.
        """
    ),
    code(
        """
        manifest = json.loads(
            (
                ROOT
                / "data/manifests/"
                "08_event_probability_manifest.json"
            ).read_text(encoding="utf-8")
        )

        assert manifest["probability_construction_locked"] is True
        assert manifest["probability_regularisation_applied"] is False
        assert manifest["realised_outcomes_accessed"] is False
        assert manifest["categorical_scores_calculated"] is False
        assert manifest["market_prices_accessed"] is False
        assert manifest["trading_returns_calculated"] is False

        print(
            "Event probability construction locked:",
            True,
        )
        """
    ),
    markdown(
        """
        ## Evidential boundary

        This notebook constructs probability vectors but does not score them.

        Uniform probability mixing, categorical evaluation, market comparison
        and trading analysis are separate later stages.
        """
    ),
]

destination = Path(
    "notebooks/final/"
    "08_locked_event_probabilities.ipynb"
)

nbf.write(
    notebook,
    destination,
)

print("Created:", destination)
