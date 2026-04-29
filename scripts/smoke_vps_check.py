#!/usr/bin/env python3
"""
Quick environment check before running live/replay on a new machine (e.g. Windows VPS).

  * Verifies core scripts answer --help (exit 0).
  * Optionally runs a tiny ``phoenix_live_pace_replay`` (needs Data-DataBento or --data-dir).

Usage (from repository root)::

  python scripts/smoke_vps_check.py
  python scripts/smoke_vps_check.py --data-dir D:\\Data\\Data-DataBento
  python scripts/smoke_vps_check.py --skip-replay
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    # Windows cp1252 consoles choke on Unicode in argparse --help; force UTF-8 IO.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if sys.platform == "win32":
        env["PYTHONUTF8"] = "1"
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Parquet root for optional replay (default: env PHOENIX_TEST_DATA_DIR or ./Data-DataBento)",
    )
    p.add_argument(
        "--skip-replay",
        action="store_true",
        help="Only run --help checks (no data required)",
    )
    args = p.parse_args()

    py = sys.executable
    failures: list[str] = []

    help_scripts = [
        SCRIPT_DIR / "run_portfolio_preset.py",
        SCRIPT_DIR / "phoenix_live_pace_replay.py",
        SCRIPT_DIR / "run_live_replay_all_portfolio_presets.py",
        SCRIPT_DIR / "smoke_vps_check.py",
        SCRIPT_DIR / "backtester.py",
    ]
    print("== CLI --help ==")
    for script in help_scripts:
        if not script.is_file():
            failures.append(f"missing {script}")
            print(f"  FAIL missing {script.name}")
            continue
        r = _run([py, str(script), "--help"], cwd=REPO_ROOT)
        if r.returncode != 0:
            failures.append(f"{script.name} --help exit {r.returncode}")
            print(f"  FAIL {script.name} --help stderr={r.stderr[:500]!r}")
        else:
            print(f"  OK   {script.name}")

    print("== projectx.main --help ==")
    r = _run([py, "-m", "projectx.main", "--help"], cwd=REPO_ROOT)
    if r.returncode != 0:
        failures.append(f"projectx.main --help exit {r.returncode}")
        print(f"  FAIL projectx.main --help stderr={r.stderr[:500]!r}")
    else:
        print("  OK   projectx.main")

    if args.skip_replay:
        if failures:
            print("\nSmoke FAILED:", *failures, sep="\n  ")
            return 1
        print("\nSmoke OK (replay skipped).")
        return 0

    data_dir = args.data_dir
    if data_dir is None:
        env = os.environ.get("PHOENIX_TEST_DATA_DIR", "").strip()
        data_dir = Path(env).expanduser() if env else REPO_ROOT / "Data-DataBento"
    else:
        data_dir = Path(data_dir).expanduser().resolve()

    if not data_dir.is_dir():
        print(f"\n== replay SKIPPED (no data dir: {data_dir}) ==")
        if failures:
            print("Smoke FAILED:", *failures, sep="\n  ")
            return 1
        print("Smoke OK (no data for replay).")
        return 0

    print(f"\n== short replay (range_prefix, max 6 steps) data-dir={data_dir} ==")
    cmd = [
        py,
        str(SCRIPT_DIR / "phoenix_live_pace_replay.py"),
        "--start-date",
        "2024-06-03",
        "--end-date",
        "2024-06-05",
        "--data-dir",
        str(data_dir),
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
        "6",
    ]
    r = _run(cmd, cwd=REPO_ROOT)
    if r.returncode != 0:
        failures.append(f"phoenix_live_pace_replay short run exit {r.returncode}")
        print(f"  FAIL replay stdout={r.stdout[-2000:]!r} stderr={r.stderr[-2000:]!r}")
    else:
        print("  OK   phoenix_live_pace_replay (6 steps)")

    if failures:
        print("\nSmoke FAILED:", *failures, sep="\n  ")
        return 1
    print("\nSmoke OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
