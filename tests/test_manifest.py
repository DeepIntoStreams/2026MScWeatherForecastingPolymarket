from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from weather_polymarket.manifest import write_json_atomic


class ManifestTests(unittest.TestCase):
    def test_common_objects_are_json_serialised(self) -> None:
        payload = {
            "date": date(2026, 7, 31),
            "datetime": datetime(
                2026,
                9,
                1,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            "path": Path("config/analysis.yaml"),
            "set": {"b", "a"},
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"

            write_json_atomic(output, payload)

            loaded = json.loads(
                output.read_text(encoding="utf-8")
            )

        self.assertEqual(
            loaded["date"],
            "2026-07-31",
        )

        self.assertEqual(
            loaded["datetime"],
            "2026-09-01T12:00:00+00:00",
        )

        self.assertEqual(
            loaded["path"],
            "config/analysis.yaml",
        )

        self.assertEqual(
            loaded["set"],
            ["a", "b"],
        )


if __name__ == "__main__":
    unittest.main()
