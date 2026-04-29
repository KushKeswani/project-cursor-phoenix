"""Smoke: core CLIs respond to --help."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _help_env() -> dict[str, str]:
    """Avoid Windows cp1252 UnicodeEncodeError when argparse prints --help."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if sys.platform == "win32":
        env["PYTHONUTF8"] = "1"
    return env


class TestCoreScriptsHelp(unittest.TestCase):
    def test_help_exits_zero(self) -> None:
        for name in (
            "run_portfolio_preset.py",
            "phoenix_live_pace_replay.py",
            "run_phoenix_vps_parity_suite.py",
            "run_live_replay_all_portfolio_presets.py",
            "smoke_vps_check.py",
            "backtester.py",
            "phoenix_agent_cycle.py",
        ):
            script = REPO_ROOT / "scripts" / name
            self.assertTrue(script.is_file(), msg=str(script))
            subprocess.run(
                [sys.executable, str(script), "--help"],
                check=True,
                capture_output=True,
                text=True,
                env=_help_env(),
            )


if __name__ == "__main__":
    unittest.main()
