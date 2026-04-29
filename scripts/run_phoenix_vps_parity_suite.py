#!/usr/bin/env python3
"""
VPS-friendly Phoenix parity run (2–3 months, or any range you pass).

Runs ``phoenix_live_pace_replay.py`` in **bar** mode with **--live-entry-parity** so replay
counts match **live stop@trigger gating** (``entry_breakout_stop_valid`` in ``projectx/main.py``).

Windows (PowerShell, from repo root)::

    .\\.venv\\Scripts\\activate
    pip install -r requirements.txt -r scripts/requirements.txt -r projectx/requirements.txt
    python scripts\\run_phoenix_vps_parity_suite.py ^
        --data-dir Data-DataBento ^
        --start-date 2026-01-01 --end-date 2026-03-31 ^
        --instruments MNQ,MGC,YM --contracts 1,3,1

Linux/macOS::

    python3 scripts/run_phoenix_vps_parity_suite.py \\
        --data-dir Data-DataBento \\
        --start-date 2026-01-01 --end-date 2026-03-31

Tips:

- Use ``--bars-window session_day`` (default) for speed; it matches **local**
  ``--phoenix-data-dir`` day-scoped bars in ``run_scan_once``.
- Use ``--bars-window range_prefix`` for strict causal history (slower on long ranges).
- Align ``--entry-fill-mode`` with ``execution.phoenix_entry_fill`` in ``projectx/config/settings.yaml``.
- ``--parity-market-entry`` mimics ``--phoenix-market-entry`` (skips stop-validity).

Output: JSON at ``reports/vps_parity_<start>_<end>.json`` unless ``--out-json`` is set.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--instruments", default="MNQ,MGC,YM")
    p.add_argument("--contracts", default="1,3,1")
    p.add_argument(
        "--bars-window",
        choices=("session_day", "range_prefix"),
        default="session_day",
    )
    p.add_argument(
        "--entry-fill-mode",
        default="touch",
        choices=("touch", "touch_legacy", "touch_strict", "next_bar_open", "stop_market"),
    )
    p.add_argument(
        "--stop-slippage-ticks",
        type=float,
        default=0.0,
    )
    p.add_argument(
        "--close-slippage-ticks",
        type=float,
        default=0.0,
    )
    p.add_argument("--out-json", type=Path, default=None)
    p.add_argument("--parity-market-entry", action="store_true")
    p.add_argument(
        "--skip-live-trade-stats",
        action="store_true",
        help="Faster: signal counts only (omit run_backtest WR/PF block)",
    )
    p.add_argument("--max-steps", type=int, default=None)
    args = p.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    if args.out_json is not None:
        out_json = Path(args.out_json).expanduser().resolve()
    else:
        out_json = (
            REPO_ROOT / "reports" / f"vps_parity_{args.start_date}_to_{args.end_date}.json"
        )
    out_json.parent.mkdir(parents=True, exist_ok=True)

    replay = REPO_ROOT / "scripts" / "phoenix_live_pace_replay.py"
    cmd: list[str] = [
        sys.executable,
        str(replay),
        "--data-dir",
        str(data_dir),
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--instruments",
        args.instruments,
        "--contracts",
        args.contracts,
        "--step-mode",
        "bar",
        "--no-sleep",
        "--bars-window",
        args.bars_window,
        "--entry-fill-mode",
        args.entry_fill_mode,
        "--stop-slippage-ticks",
        str(args.stop_slippage_ticks),
        "--close-slippage-ticks",
        str(args.close_slippage_ticks),
        "--stats-out",
        str(out_json),
        "--live-entry-parity",
    ]
    if args.parity_market_entry:
        cmd.append("--parity-market-entry")
    if args.skip_live_trade_stats:
        cmd.append("--no-live-trade-stats")
    if args.max_steps is not None:
        cmd.extend(["--max-steps", str(args.max_steps)])

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if sys.platform == "win32":
        env["PYTHONUTF8"] = "1"
    print("Running:", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    if proc.returncode == 0:
        print(f"OK — wrote {out_json}", flush=True)
    else:
        print(f"Failed with exit code {proc.returncode}", flush=True)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
