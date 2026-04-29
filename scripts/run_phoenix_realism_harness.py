#!/usr/bin/env python3
"""
Run a strict Phoenix live-replay harness and archive the artifacts in a dedicated folder.

This does not place broker orders. It uses the same Phoenix scan path as production
(`run_scan_once` via `phoenix_live_pace_replay.py`) but forces realism-oriented execution:

- causal `range_prefix` replay by default
- configurable fill mode and slippage
- data fingerprints for provenance
- replay stats JSON, closed-trade CSV, and fingerprint traces

Example:

  python3 scripts/run_phoenix_realism_harness.py \\
    --data-dir Data-DataBento/april_frontmonth \\
    --start-date 2026-03-28 --end-date 2026-04-28 \\
    --preset Balanced_150k_high

For a true 30-second poll emulation, add `--step-mode grid --sim-step-seconds 30`.
For a faster historical causal replay, use the default `--step-mode bar`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from configs.portfolio_presets import PORTFOLIO_PRESETS
from telegram_script_done import load_projectx_env_if_present

try:
    from projectx.notify.telegram import send_telegram_if_configured
except Exception:  # pragma: no cover - optional import fallback
    def send_telegram_if_configured(body: str, *, logger: Any | None = None) -> None:  # type: ignore[no-redef]
        _ = (body, logger)
        return


def _fingerprint_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False}
    st = path.stat()
    h = hashlib.blake2b(digest_size=8)
    with open(path, "rb") as f:
        h.update(f.read(1_000_000))
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": int(st.st_size),
        "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        "blake2b_64": h.hexdigest(),
    }


def _slug(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


def _parse_date_range(args: argparse.Namespace) -> tuple[str, str]:
    if args.year is not None:
        y = int(args.year)
        return f"{y}-01-01", f"{y}-12-31"
    if not args.start_date or not args.end_date:
        raise SystemExit("Provide either --year or both --start-date and --end-date")
    return str(args.start_date), str(args.end_date)


def _write_trade_keys(trades_csv: Path, out_csv: Path) -> None:
    if not trades_csv.is_file():
        return
    df = pd.read_csv(trades_csv)
    if df.empty:
        pd.DataFrame(
            columns=[
                "instrument",
                "entry_ts_et",
                "exit_ts_et",
                "direction",
                "fingerprint",
                "pnl_usd",
            ]
        ).to_csv(out_csv, index=False)
        return
    out = pd.DataFrame()
    for col in ("instrument", "entry_ts_et", "exit_ts_et", "direction", "pnl_usd"):
        if col in df.columns:
            out[col] = df[col]
    if "entry_ts_et" not in out.columns and "entry_ts" in df.columns:
        out["entry_ts_et"] = pd.to_datetime(df["entry_ts"], utc=True).dt.tz_convert(
            "America/New_York"
        ).dt.strftime("%Y-%m-%d %H:%M:%S")
    if "exit_ts_et" not in out.columns and "exit_ts" in df.columns:
        out["exit_ts_et"] = pd.to_datetime(df["exit_ts"], utc=True).dt.tz_convert(
            "America/New_York"
        ).dt.strftime("%Y-%m-%d %H:%M:%S")
    if "instrument" not in out.columns:
        out["instrument"] = ""
    if "direction" not in out.columns:
        out["direction"] = ""
    if "pnl_usd" not in out.columns:
        out["pnl_usd"] = 0.0
    out["fingerprint"] = (
        out["instrument"].astype(str)
        + "|"
        + out["entry_ts_et"].astype(str)
        + "|"
        + out["direction"].astype(str)
        + "|"
        + out["exit_ts_et"].astype(str)
    )
    out.to_csv(out_csv, index=False)


def _send_telegram_progress(
    *,
    preset: str,
    start_date: str,
    end_date: str,
    run_root: Path,
    progress_path: Path,
) -> None:
    if not progress_path.is_file():
        return
    try:
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    pct = payload.get("pct_timeline")
    steps = payload.get("steps_executed")
    total = payload.get("timeline_points")
    eta = payload.get("eta_seconds_bar_remaining")
    trades = payload.get("live_trades_accumulated")
    lines = [
        f"Phoenix realism update: {preset}",
        f"Range: {start_date} -> {end_date}",
        f"Progress: {pct}% ({steps}/{total})",
        f"Live closes accumulated: {trades}",
        f"Run dir: {run_root}",
    ]
    if eta is not None:
        try:
            eta_min = float(eta) / 60.0
            lines.insert(3, f"ETA: ~{eta_min:.1f} min")
        except (TypeError, ValueError):
            pass
    send_telegram_if_configured("\n".join(lines))


def _send_telegram_final(
    *,
    preset: str,
    start_date: str,
    end_date: str,
    run_root: Path,
    stats_path: Path,
    ok: bool,
    exit_code: int,
) -> None:
    if not stats_path.is_file():
        send_telegram_if_configured(
            "\n".join(
                [
                    f"Phoenix realism {'done' if ok else 'failed'}: {preset}",
                    f"Range: {start_date} -> {end_date}",
                    f"Exit code: {exit_code}",
                    f"Run dir: {run_root}",
                ]
            )
        )
        return
    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stats = {}
    lt = stats.get("live_backtest_trades", {}) if isinstance(stats, dict) else {}
    lines = [
        f"Phoenix realism {'done' if ok else 'failed'}: {preset}",
        f"Range: {start_date} -> {end_date}",
        f"Exit code: {exit_code}",
        f"Run dir: {run_root}",
    ]
    if isinstance(lt, dict) and lt:
        lines.extend(
            [
                f"Trades: {lt.get('n_trades', 0)}",
                f"WR: {lt.get('win_rate_pct', 0)}%",
                f"PF: {lt.get('profit_factor', 0)}",
                f"Total PnL: ${lt.get('total_pnl_usd', 0)}",
            ]
        )
    send_telegram_if_configured("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Phoenix strict live-realism replay harness")
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--year", type=int, default=None)
    p.add_argument("--start-date", default=None)
    p.add_argument("--end-date", default=None)
    p.add_argument(
        "--preset",
        default="Balanced_150k_high",
        choices=sorted(PORTFOLIO_PRESETS.keys()),
        help="Portfolio preset used for contracts and trade sizing",
    )
    p.add_argument(
        "--step-mode",
        default="bar",
        choices=("bar", "grid"),
        help="bar = causal per-bar replay; grid = 30s poll emulation",
    )
    p.add_argument("--sim-step-seconds", type=int, default=30)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--no-sleep", action="store_true")
    p.add_argument(
        "--bars-window",
        default="range_prefix",
        choices=("range_prefix", "session_day"),
    )
    p.add_argument(
        "--entry-fill-mode",
        default="touch_strict",
        choices=("touch", "touch_legacy", "touch_strict", "next_bar_open"),
    )
    p.add_argument("--stop-slippage-ticks", type=float, default=1.0)
    p.add_argument("--close-slippage-ticks", type=float, default=1.0)
    p.add_argument("--entry-slippage-ticks", type=float, default=None)
    p.add_argument("--exit-slippage-ticks", type=float, default=None)
    p.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "reports" / "live_realism",
    )
    p.add_argument("--tag", default=None)
    p.add_argument("--max-steps", type=int, default=None)
    p.add_argument(
        "--telegram-progress-minutes",
        type=float,
        default=10.0,
        help="Send Telegram progress every N minutes when credentials are configured (0 disables).",
    )
    args = p.parse_args(argv)

    load_projectx_env_if_present()

    start_date, end_date = _parse_date_range(args)
    preset = PORTFOLIO_PRESETS[args.preset]
    slug = _slug(args.preset)
    tag = args.tag or f"{start_date}_to_{end_date}"
    run_root = Path(args.output_root).expanduser().resolve() / slug / _slug(tag)
    run_root.mkdir(parents=True, exist_ok=True)

    stats_path = run_root / "phoenix_live_replay_stats.json"
    trades_csv = run_root / "phoenix_live_replay_trades.csv"
    trace_jsonl = run_root / "phoenix_live_replay_trace.jsonl"
    manifest_path = run_root / "manifest.json"
    trade_keys_path = run_root / "trade_keys.csv"
    progress_path = stats_path.with_suffix(".progress.json")

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "preset": args.preset,
        "contracts": preset,
        "start_date": start_date,
        "end_date": end_date,
        "data_dir": str(Path(args.data_dir).expanduser().resolve()),
        "data_fingerprints": {
            inst: _fingerprint_file(Path(args.data_dir).expanduser().resolve() / f"{inst}.parquet")
            for inst in preset
        },
        "replay": {
            "step_mode": args.step_mode,
            "sim_step_seconds": args.sim_step_seconds,
            "speed": args.speed,
            "no_sleep": bool(args.no_sleep),
            "bars_window": args.bars_window,
            "entry_fill_mode": args.entry_fill_mode,
            "stop_slippage_ticks": float(args.stop_slippage_ticks),
            "close_slippage_ticks": float(args.close_slippage_ticks),
            "entry_slippage_ticks": args.entry_slippage_ticks,
            "exit_slippage_ticks": args.exit_slippage_ticks,
            "max_steps": args.max_steps,
        },
        "outputs": {
            "stats": str(stats_path),
            "trades": str(trades_csv),
            "trace": str(trace_jsonl),
            "trade_keys": str(trade_keys_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    active_legs = [(inst, int(qty)) for inst, qty in preset.items() if int(qty) > 0]
    if not active_legs:
        raise SystemExit(f"Preset {args.preset} has no active contracts (>0).")
    instruments = ",".join(inst for inst, _ in active_legs)
    contracts = ",".join(str(qty) for _, qty in active_legs)
    replay_py = SCRIPT_DIR / "phoenix_live_pace_replay.py"
    cmd = [
        sys.executable,
        str(replay_py),
        "--start-date",
        start_date,
        "--end-date",
        end_date,
        "--data-dir",
        str(Path(args.data_dir).expanduser().resolve()),
        "--instruments",
        instruments,
        "--contracts",
        contracts,
        "--step-mode",
        args.step_mode,
        "--sim-step-seconds",
        str(args.sim_step_seconds),
        "--speed",
        str(args.speed),
        "--bars-window",
        args.bars_window,
        "--entry-fill-mode",
        args.entry_fill_mode,
        "--stop-slippage-ticks",
        str(args.stop_slippage_ticks),
        "--close-slippage-ticks",
        str(args.close_slippage_ticks),
        "--stats-out",
        str(stats_path),
        "--trades-csv",
        str(trades_csv),
        "--trace-jsonl",
        str(trace_jsonl),
    ]
    if args.no_sleep:
        cmd.append("--no-sleep")
    if args.entry_slippage_ticks is not None:
        cmd.extend(["--entry-slippage-ticks", str(args.entry_slippage_ticks)])
    if args.exit_slippage_ticks is not None:
        cmd.extend(["--exit-slippage-ticks", str(args.exit_slippage_ticks)])
    if args.max_steps is not None:
        cmd.extend(["--max-steps", str(args.max_steps)])

    print("Running:", " ".join(cmd), flush=True)
    env = os.environ.copy()
    env["SKIP_TELEGRAM_SCRIPT_DONE"] = "1"
    env["MPLCONFIGDIR"] = str((run_root / ".mplconfig").resolve())
    Path(env["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), env=env)
    interval_sec = max(0.0, float(args.telegram_progress_minutes) * 60.0)
    next_ping = time.monotonic() + interval_sec if interval_sec > 0 else float("inf")
    while True:
        code = proc.poll()
        if code is not None:
            break
        if interval_sec > 0 and time.monotonic() >= next_ping:
            _send_telegram_progress(
                preset=args.preset,
                start_date=start_date,
                end_date=end_date,
                run_root=run_root,
                progress_path=progress_path,
            )
            next_ping = time.monotonic() + interval_sec
        time.sleep(5)
    if code != 0:
        _send_telegram_final(
            preset=args.preset,
            start_date=start_date,
            end_date=end_date,
            run_root=run_root,
            stats_path=stats_path,
            ok=False,
            exit_code=int(code),
        )
        raise subprocess.CalledProcessError(int(code), cmd)
    _write_trade_keys(trades_csv, trade_keys_path)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "stats": str(stats_path),
        "trades": str(trades_csv),
        "trace": str(trace_jsonl),
        "trade_keys": str(trade_keys_path),
    }
    (run_root / "run_complete.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _send_telegram_final(
        preset=args.preset,
        start_date=start_date,
        end_date=end_date,
        run_root=run_root,
        stats_path=stats_path,
        ok=True,
        exit_code=0,
    )
    print(f"Run archived at {run_root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
