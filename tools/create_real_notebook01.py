#!/usr/bin/env python3

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


def markdown(text: str):
    return nbf.v4.new_markdown_cell(dedent(text).strip())


def code(text: str):
    return nbf.v4.new_code_cell(dedent(text).strip())


path = Path(
    "notebooks/final/"
    "01_hko_settlement_and_event_certification.ipynb"
)

notebook = nbf.v4.new_notebook()

notebook["metadata"]["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}

notebook["cells"] = [
    markdown(
        """
        # 01 — HKO Settlement and Event Certification

        This notebook loads the migrated contract definitions and official
        HKO daily maximum outcomes, then certifies exactly one winning
        contract in every retained eleven-event book.
        """
    ),
    code(
        """
        from pathlib import Path
        import hashlib
        import json
        import sys
        from datetime import datetime, timezone

        def locate_repository(start: Path) -> Path:
            current = start.resolve()

            for candidate in (current, *current.parents):
                if (candidate / "config" / "analysis.yaml").exists():
                    return candidate

            raise FileNotFoundError("Repository root not found.")

        ROOT = locate_repository(Path.cwd())
        SRC = ROOT / "src"

        if str(SRC) not in sys.path:
            sys.path.insert(0, str(SRC))

        print(f"Repository root: {ROOT}")
        """
    ),
    code(
        """
        from weather_polymarket.contract_source import (
            load_contract_definitions,
        )
        from weather_polymarket.hko_source import load_hko_daily_max
        from weather_polymarket.certification import (
            certify_real_event_books,
        )

        contract_path = (
            ROOT / "data/interim/canonical_contract_definitions.csv"
        )

        hko_path = ROOT / "data/interim/hko_daily_max.csv"

        contracts = load_contract_definitions(contract_path)
        hko = load_hko_daily_max(hko_path)

        print("Contract rows:", len(contracts))
        print("Contract dates:", contracts["event_date"].nunique())
        print("HKO dates:", hko["event_date"].nunique())
        """
    ),
    code(
        """
        certified, certification_by_date = certify_real_event_books(
            contracts,
            hko,
        )

        assert certification_by_date["event_count"].eq(11).all()
        assert certification_by_date["winner_count"].eq(1).all()

        print("Certified dates:", len(certification_by_date))
        print(
            "Date range:",
            certification_by_date["event_date"].min(),
            "to",
            certification_by_date["event_date"].max(),
        )
        print(
            "Eleven events per date:",
            certification_by_date["event_count"].eq(11).all(),
        )
        print(
            "One winner per date:",
            certification_by_date["winner_count"].eq(1).all(),
        )
        """
    ),
    code(
        """
        processed_path = (
            ROOT / "data/processed/certified_event_books.csv"
        )

        by_date_path = (
            ROOT
            / "outputs/diagnostics/"
            "01_event_book_certification_by_date.csv"
        )

        summary_path = (
            ROOT
            / "outputs/diagnostics/"
            "01_event_book_certification_summary.json"
        )

        manifest_path = (
            ROOT
            / "data/manifests/"
            "01_event_book_certification_manifest.json"
        )

        processed_path.parent.mkdir(parents=True, exist_ok=True)
        by_date_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        certified.to_csv(processed_path, index=False)
        certification_by_date.to_csv(by_date_path, index=False)

        source_manifest = json.loads(
            (
                ROOT
                / "data/manifests/"
                "01_source_migration_manifest.json"
            ).read_text(encoding="utf-8")
        )

        summary = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "status": "REAL_EVENT_BOOKS_CERTIFIED",
            "certified_dates": int(len(certification_by_date)),
            "certified_rows": int(len(certified)),
            "start_date": str(
                certification_by_date["event_date"].min()
            ),
            "end_date": str(
                certification_by_date["event_date"].max()
            ),
            "all_dates_have_11_events": bool(
                certification_by_date["event_count"].eq(11).all()
            ),
            "all_dates_have_one_winner": bool(
                certification_by_date["winner_count"].eq(1).all()
            ),
            "selected_contract_source": (
                source_manifest["selected_contract_source"]["source"]
            ),
            "selected_hko_source": (
                source_manifest["selected_hko_source"]["source"]
            ),
        }

        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\\n",
            encoding="utf-8",
        )

        def sha256(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        manifest = {
            **summary,
            "inputs": {
                str(contract_path.relative_to(ROOT)): {
                    "sha256": sha256(contract_path),
                    "rows": int(len(contracts)),
                },
                str(hko_path.relative_to(ROOT)): {
                    "sha256": sha256(hko_path),
                    "rows": int(len(hko)),
                },
            },
            "outputs": {
                str(processed_path.relative_to(ROOT)): {
                    "sha256": sha256(processed_path),
                    "rows": int(len(certified)),
                },
                str(by_date_path.relative_to(ROOT)): {
                    "sha256": sha256(by_date_path),
                    "rows": int(len(certification_by_date)),
                },
            },
        }

        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\\n",
            encoding="utf-8",
        )

        print(f"Certified panel: {processed_path}")
        print(f"Date audit: {by_date_path}")
        print(f"Summary: {summary_path}")
        print(f"Manifest: {manifest_path}")
        """
    ),
    markdown(
        """
        ## Evidential boundary

        This notebook certifies settlement outcomes and contract partitions.
        Forecast-time information availability is audited separately in
        Notebook 02.
        """
    ),
]

path.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, path)

print(f"Created {path}")
