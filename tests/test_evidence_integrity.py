from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.evidence_utils import build_data_manifest


class TestEvidenceIntegrity(unittest.TestCase):
    def test_data_manifest_contains_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = root / "a.csv"
            b = root / "b.csv"
            a.write_text("x,y\n1,2\n", encoding="utf-8")
            b.write_text("x,y\n3,4\n", encoding="utf-8")
            m = build_data_manifest([a, b])
            self.assertEqual(m["n_files"], 2)
            self.assertTrue(m["manifest_sha256"])
            self.assertEqual(len(m["files"]), 2)
            for f in m["files"]:
                self.assertIn("sha256", f)
                self.assertIn("size_bytes", f)

    def test_quality_gate_schema_minimal(self) -> None:
        payload = {
            "max_pool_days_ratio": 1.5,
            "min_rolling_pass_windows": 200,
            "allow_nonparity": False,
            "checks": [],
            "failures": [],
            "pass": True,
        }
        txt = json.dumps(payload)
        parsed = json.loads(txt)
        self.assertIn("checks", parsed)
        self.assertIn("failures", parsed)
        self.assertIn("pass", parsed)


if __name__ == "__main__":
    unittest.main()

