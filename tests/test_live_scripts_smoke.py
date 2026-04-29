"""Smoke tests for live/replay CLIs and optional short replay (needs data dir)."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts"


def _subprocess_env() -> dict[str, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if sys.platform == "win32":
        env["PYTHONUTF8"] = "1"
    return env


def _data_dir() -> Path | None:
    env = os.environ.get("PHOENIX_TEST_DATA_DIR", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.is_dir() else None
    p = REPO_ROOT / "Data-DataBento"
    return p if p.is_dir() else None


class TestLiveScriptsHelp(unittest.TestCase):
    def test_smoke_vps_check_help_only(self) -> None:
        r = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "smoke_vps_check.py"), "--skip-replay"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env=_subprocess_env(),
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr + r.stdout)

    def test_projectx_main_help(self) -> None:
        r = subprocess.run(
            [sys.executable, "-m", "projectx.main", "--help"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            env=_subprocess_env(),
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr)


@unittest.skipUnless(_data_dir() is not None, "Data-DataBento or PHOENIX_TEST_DATA_DIR required")
class TestLiveReplayShortRun(unittest.TestCase):
    def test_phoenix_live_pace_replay_range_prefix(self) -> None:
        data = _data_dir()
        assert data is not None
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "phoenix_live_pace_replay.py"),
            "--start-date",
            "2024-06-03",
            "--end-date",
            "2024-06-04",
            "--data-dir",
            str(data),
            "--step-mode",
            "bar",
            "--no-sleep",
            "--instruments",
            "MNQ",
            "--contracts",
            "1",
            "--no-stats",
            "--bars-window",
            "range_prefix",
            "--max-steps",
            "8",
        ]
        r = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            env=_subprocess_env(),
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr + r.stdout)

    def test_smoke_vps_check_with_replay(self) -> None:
        data = _data_dir()
        assert data is not None
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "smoke_vps_check.py"),
                "--data-dir",
                str(data),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            env=_subprocess_env(),
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
