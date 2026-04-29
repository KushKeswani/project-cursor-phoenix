"""Tests for Phoenix replay ↔ live stop-gate parity helpers."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from projectx.strategy.phoenix_replay_parity import (  # noqa: E402
    live_stop_entry_eligibility,
)

_TEST_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
if sys.platform == "win32":
    _TEST_ENV["PYTHONUTF8"] = "1"


class TestLiveStopEntryEligibility(unittest.TestCase):
    def test_market_mode_skips_gate(self) -> None:
        ok, reason = live_stop_entry_eligibility(
            "MNQ",
            {"direction": "long", "entry_price": 100.0},
            None,
            0.25,
            phoenix_limit_entry=False,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "market_entry_no_stop_check")

    def test_long_stop_valid_when_last_below_trigger(self) -> None:
        bars = pd.DataFrame({"close": [99.0]})
        ok, _ = live_stop_entry_eligibility(
            "MNQ",
            {"direction": "long", "entry_price": 100.0},
            bars,
            0.25,
            phoenix_limit_entry=True,
        )
        self.assertTrue(ok)

    def test_long_stop_invalid_when_last_through_trigger(self) -> None:
        bars = pd.DataFrame({"close": [100.5]})
        ok, reason = live_stop_entry_eligibility(
            "MNQ",
            {"direction": "long", "entry_price": 100.0},
            bars,
            0.25,
            phoenix_limit_entry=True,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "entry_breakout_stop_invalid")


class TestVpsParityScriptSmoke(unittest.TestCase):
    def test_help_exits_zero(self) -> None:
        script = REPO_ROOT / "scripts" / "run_phoenix_vps_parity_suite.py"
        self.assertTrue(script.is_file())
        subprocess.run(
            [sys.executable, str(script), "--help"],
            check=True,
            capture_output=True,
            text=True,
            env=_TEST_ENV,
        )


if __name__ == "__main__":
    unittest.main()
