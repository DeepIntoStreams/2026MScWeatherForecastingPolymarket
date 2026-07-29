from __future__ import annotations

import csv
import hashlib
import json
import unittest
import zipfile
from pathlib import Path


class Phase24Test(unittest.TestCase):
    root = Path.cwd()
    output = root / "outputs/v2_completion/phase24_thesis_writing_handover"
    config = root / "config/v2_completion/phase24_thesis_handover_spec.json"
    archive = output / "phase24_thesis_writing_handover.zip"

    def test_status_and_checks(self) -> None:
        spec = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(spec["status"], "PASSED")
        self.assertTrue(spec["non_empirical_phase"])
        with (self.output / "phase24_validation_checks.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 7)
        self.assertTrue(all(r["status"] == "PASSED" for r in rows))

    def test_archive(self) -> None:
        self.assertTrue(self.archive.is_file())
        self.assertLess(self.archive.stat().st_size, 25 * 1024 * 1024)
        with zipfile.ZipFile(self.archive, "r") as z:
            self.assertIsNone(z.testzip())
            names = set(z.namelist())
        self.assertIn("START_HERE.md", names)
        self.assertIn("FILE_MANIFEST.csv", names)
        self.assertIn("phase22_thesis_evidence_pack/phase22_empirical_instruction_book.md", names)
        self.assertIn("phase23_final_freeze/phase23_thesis_handover.md", names)
        self.assertFalse(any("__pycache__" in n or n.endswith((".pyc", ".pyo", ".joblib", ".pkl", ".pickle")) for n in names))

    def test_manifest_hashes(self) -> None:
        manifest = json.loads((self.output / "phase24_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "PASSED")
        for item in manifest["outputs"]:
            p = self.root / item["relative_path"]
            self.assertTrue(p.is_file())
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), item["sha256"])


if __name__ == "__main__":
    unittest.main()
