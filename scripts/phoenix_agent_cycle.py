#!/usr/bin/env python3
"""Periodic validation: pytest, VPS smoke, optional portfolio backtest; log + Telegram.

Typical scheduling (every few hours):

  cd \"<Project Cursor>\" && python3 scripts/phoenix_agent_cycle.py

With a fast portfolio refresh when `Data-DataBento` has bars:

  python3 scripts/phoenix_agent_cycle.py --run-backtest --profile Balanced_50k_survival --mc-sims 2000

Telegram uses the same env vars as ProjectX (`PROJECTX_TELEGRAM_*`). Use `--no-telegram`
for CI; the session log is always appended.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


def _append_log(text: str) -> None:
    log = REPO_ROOT / "AGENT_SESSION_LOG.md"
    with log.open("a", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def _telegram(msg: str) -> None:
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(SCRIPTS))
    from telegram_script_done import load_projectx_env_if_present
    from projectx.notify.telegram import send_telegram_if_configured

    load_projectx_env_if_present()
    send_telegram_if_configured(msg)


def _has_bar_data(data_dir: Path) -> bool:
    for name in ("MNQ.parquet", "nq-data.csv"):
        if (data_dir / name).is_file():
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram ping")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument(
        "--smoke-full",
        action="store_true",
        help="Run replay inside smoke_vps_check (needs MNQ.parquet or nq-data.csv)",
    )
    parser.add_argument(
        "--run-backtest",
        action="store_true",
        help="If MNQ data exists, run run_portfolio_preset.py",
    )
    parser.add_argument("--profile", default="Balanced_50k_survival")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--mc-sims", type=int, default=2000)
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve() if args.data_dir else REPO_ROOT / "Data-DataBento"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [f"\n\n## {ts} — phoenix_agent_cycle\n\n"]
    ok_all = True
    summary_lines: list[str] = ["[Phoenix agent] Health cycle"]

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    if not args.skip_pytest:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_core_scripts.py", "-v"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env=env,
        )
        ok = r.returncode == 0
        ok_all = ok_all and ok
        lines.append(f"- pytest tests/test_core_scripts.py: {'PASS' if ok else 'FAIL'} (exit {r.returncode})\n")
        summary_lines.append(f"pytest: {'OK' if ok else 'FAIL'}")

    if not args.skip_smoke:
        cmd = [sys.executable, str(SCRIPTS / "smoke_vps_check.py")]
        if not args.smoke_full:
            cmd.append("--skip-replay")
        r = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
        ok = r.returncode == 0
        ok_all = ok_all and ok
        tag = "full+replay" if args.smoke_full else "skip-replay"
        lines.append(f"- smoke_vps_check ({tag}): {'PASS' if ok else 'FAIL'}\n")
        summary_lines.append(f"smoke ({tag}): {'OK' if ok else 'FAIL'}")

    bt_tail = ""
    if args.run_backtest and _has_bar_data(data_dir):
        cmd = [
            sys.executable,
            str(SCRIPTS / "run_portfolio_preset.py"),
            "--profile",
            args.profile,
            "--data-dir",
            str(data_dir),
            "--mc-sims",
            str(args.mc_sims),
        ]
        r = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
        ok = r.returncode == 0
        ok_all = ok_all and ok
        lines.append(f"- run_portfolio_preset --profile {args.profile}: {'PASS' if ok else 'FAIL'}\n")
        summary_lines.append(f"backtest ({args.profile}): {'OK' if ok else 'FAIL'}")
        blob = (r.stdout or "") + (r.stderr or "")
        if blob.strip():
            bt_tail = blob.strip()[-1200:]
    elif args.run_backtest:
        lines.append("- run_portfolio_preset: SKIPPED (no MNQ.parquet / nq-data.csv)\n")
        summary_lines.append("backtest: skipped (no MNQ data)")

    has_data = _has_bar_data(data_dir)
    lines.append(f"- bar data in {data_dir}: {'present' if has_data else 'missing'}\n")
    summary_lines.append(f"bars: {'OK' if has_data else 'missing'}")
    lines.append(f"- overall: {'PASS' if ok_all else 'FAIL'}\n")

    _append_log("".join(lines))

    if not args.no_telegram:
        body = "\n".join(summary_lines)
        if bt_tail:
            body = f"{body}\n---\n{bt_tail}"
        try:
            _telegram(body)
        except Exception as exc:
            _append_log(f"- Telegram send error: {exc}\n")

    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
