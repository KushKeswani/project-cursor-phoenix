#!/usr/bin/env python3
"""
Replay Phoenix ``run_scan_once`` on local data (Data-DataBento CSV/parquet) with optional
wall-clock pacing — closest local analogue to live polling without Gateway.

  * Same code path as ``projectx.main`` Phoenix scan: ``run_scan_once`` + ``fresh_entries``.
  * Default ``--bars-window session_day``: reloads each **calendar day** only (fast; **not**
    continuous cross-day state). Use ``--bars-window range_prefix`` with a **short** range
    (e.g. one week/month) for causal bars from ``--start-date`` through each ``as_of`` — closer
    to live + full backtest.
  * **grid** mode: advance simulated ``as_of_et`` every ``--sim-step-seconds`` (default 30)
    on **weekdays** during **08:00–17:59 ET** (rough futures pit/session window).
  * **bar** mode: advance to each **resampled bar** timestamp (union across instruments) — much
    fewer steps; good for skimming a full year quickly (pair with ``--no-sleep``).

**Wall time:** each step sleeps ``sim_step_seconds / speed`` seconds (unless ``--no-sleep``).
A full year at 30s grid is ~300k+ steps → many hours even at 10x; use ``--bar`` mode,
``--no-sleep``, ``--max-steps``, or a narrower ``--start-date``/``--end-date``.

Examples::

  # Full 2026, bar-aligned, no sleep (minutes of wall time)
  python3 scripts/phoenix_live_pace_replay.py --year 2026 --data-dir Data-DataBento \\
    --step-mode bar --no-sleep

  # “30s live poll” at 10x for one week (shorter wall clock)
  python3 scripts/phoenix_live_pace_replay.py --start-date 2026-03-01 --end-date 2026-03-07 \\
    --data-dir Data-DataBento --sim-step-seconds 30 --speed 10

  # Log JSONL for later
  python3 scripts/phoenix_live_pace_replay.py --year 2026 --step-mode bar --no-sleep \\
    --trace-jsonl /tmp/phoenix_replay_2026.jsonl

By default a **summary JSON** is written under ``reports/phoenix_live_replay_stats_<tag>.json``.
Use ``--no-stats`` to skip, or ``--stats-out path.json`` to set the file.

**Live backtest PnL (WR / PF):** unless ``--no-live-trade-stats``, each step runs
``run_backtest`` on the **same** session bars trimmed to ``as_of_et`` as ``run_scan_once``
(see ``fresh_entries_for_latest_bar``). Newly completed round-trips (vs prior steps) are
deduped and scaled by ``TICK_VALUES × contracts`` — portfolio-level WR/PF/PnL, not batch
``run_portfolio_preset`` on the whole year.

**Trade CSV:** with live trade stats, use ``--trades-csv PATH`` or omit it to write
``<stats_stem>_trades.csv`` next to the stats JSON. Columns include entry/exit timestamps,
hold duration, prices, and scaled PnL.

**Progress file:** with ``--stats-out``, writes ``<stem>.progress.json`` periodically
(bar timeline % and ETA) for status dashboards / Telegram.

**Live entry parity (optional):** use ``--live-entry-parity`` to drop engine hits that live would
skip with ``execution.phoenix_entry_order: limit`` (resting stop invalid vs last bar close — same
check as ``entry_breakout_stop_valid`` in ``projectx/main.py``). Add ``--parity-market-entry`` to
assume market entry (skip that gate). Does not simulate arm orders, risk manager, or partial Gateway bars.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from telegram_script_done import run_with_telegram

from backtester import raw_trades_frame, scaled_trades, trade_metrics
from configs.strategy_configs import get_config
from configs.tick_config import TICK_SIZES, TICK_VALUES
from engine.fast_engine import ExecutionOptions, run_backtest
from projectx.strategy.phoenix_auto import (
    ensure_scripts_on_path,
    run_scan_once,
    trade_fingerprint,
)
from projectx.strategy.phoenix_replay_parity import filter_hits_with_live_stop_gate

ensure_scripts_on_path()

ET = ZoneInfo("America/New_York")


def _stub_imap(symbols: list[str]) -> dict[str, dict[str, Any]]:
    return {s.upper(): {"symbol": s.upper(), "search_text": s.upper()} for s in symbols}


def _grid_times(
    start_d: date,
    end_d: date,
    *,
    step_seconds: int,
) -> list[datetime]:
    """Weekdays only, 08:00–17:59:59 ET, ``step_seconds`` apart."""
    out: list[datetime] = []
    d = start_d
    while d <= end_d:
        if d.weekday() < 5:
            t0 = datetime(d.year, d.month, d.day, 8, 0, 0, tzinfo=ET)
            t_end = datetime(d.year, d.month, d.day, 17, 59, 59, tzinfo=ET)
            cur = t0
            step = timedelta(seconds=max(1, int(step_seconds)))
            while cur <= t_end:
                out.append(cur)
                cur += step
        d += timedelta(days=1)
    return out


def _write_live_replay_trades_csv(merged: pd.DataFrame, path: Path) -> None:
    """One row per deduped closed trade: execution prices, timestamps, hold time, PnL."""
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "instrument",
        "contracts",
        "direction",
        "entry_ts_et",
        "exit_ts_et",
        "hold_minutes",
        "entry_price",
        "exit_price",
        "entry_trigger",
        "exit_reason",
        "pnl_ticks",
        "pnl_usd",
    ]
    if merged.empty:
        pd.DataFrame(columns=header).to_csv(path, index=False)
        return
    out = merged.copy()
    ent = pd.to_datetime(out["entry_ts"])
    exi = pd.to_datetime(out["exit_ts"])
    out["hold_minutes"] = (exi - ent).dt.total_seconds() / 60.0

    def _to_et_str(s: pd.Series) -> pd.Series:
        t = pd.to_datetime(s)
        if getattr(t.dt, "tz", None) is None:
            t = t.dt.tz_localize(ET, ambiguous="infer", nonexistent="shift_forward")
        else:
            t = t.dt.tz_convert(ET)
        return t.dt.strftime("%Y-%m-%d %H:%M:%S")

    out["entry_ts_et"] = _to_et_str(out["entry_ts"])
    out["exit_ts_et"] = _to_et_str(out["exit_ts"])
    preferred = [
        "instrument",
        "contracts",
        "direction",
        "entry_ts_et",
        "exit_ts_et",
        "hold_minutes",
        "entry_price",
        "exit_price",
        "entry_trigger",
        "exit_reason",
        "pnl_ticks",
        "pnl_usd",
    ]
    if "contracts" not in out.columns:
        out["contracts"] = ""
    cols = [c for c in preferred if c in out.columns]
    out[cols].to_csv(path, index=False)


_PROGRESS_WRITE_EVERY = 2000


def _write_replay_progress(
    path: Path,
    *,
    steps: int,
    timeline_points: int,
    replay_wall_seconds: float,
    live_trades_n: int,
) -> None:
    """Heartbeat for batch runners (Telegram % / ETA). Removed when final stats JSON is written."""
    total = max(1, int(timeline_points))
    s = min(int(steps), total)
    pct = min(100.0, 100.0 * s / total)
    eta_bar: float | None = None
    if s > 0 and s < total and replay_wall_seconds > 0:
        sec_per_step = replay_wall_seconds / float(s)
        eta_bar = (total - s) * sec_per_step
    doc = {
        "steps_executed": s,
        "timeline_points": total,
        "pct_timeline": round(pct, 2),
        "replay_wall_seconds": round(replay_wall_seconds, 3),
        "eta_seconds_bar_remaining": round(eta_bar, 1) if eta_bar is not None else None,
        "live_trades_accumulated": int(live_trades_n),
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def _trade_close_key(inst: str, tr: dict[str, Any]) -> tuple[str, str, str, str]:
    """Stable id for a completed engine round-trip (per instrument)."""
    et = pd.Timestamp(tr["entry_ts"]).isoformat()
    xt = pd.Timestamp(tr["exit_ts"]).isoformat()
    return (inst, et, str(tr.get("direction", "")), xt)


def _bar_timeline(
    data_dir: Path,
    instruments: list[str],
    start_s: str,
    end_s: str,
) -> list[datetime]:
    from backtester import load_bars

    idx_set: set[pd.Timestamp] = set()
    for inst in instruments:
        _, bars = load_bars(inst, data_dir, start_s, end_s)
        if bars is None or bars.empty:
            continue
        for ts in bars.index:
            idx_set.add(pd.Timestamp(ts))
    merged = sorted(idx_set)
    out: list[datetime] = []
    for ts in merged:
        if ts.tzinfo is None:
            out.append(ts.tz_localize(ET).to_pydatetime())
        else:
            out.append(ts.tz_convert(ET).to_pydatetime())
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Paced local replay of Phoenix run_scan_once.")
    p.add_argument("--year", type=int, default=None, help="Calendar year (with --start/--end optional)")
    p.add_argument("--start-date", default=None, help="YYYY-MM-DD (overrides year start)")
    p.add_argument("--end-date", default=None, help="YYYY-MM-DD (overrides year end)")
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument(
        "--instruments",
        default="MNQ,MGC,YM",
        help="Comma symbols (default MNQ,MGC,YM - matches typical survival book)",
    )
    p.add_argument(
        "--contracts",
        default="1",
        help="Comma counts aligned to instruments (default 1 each)",
    )
    p.add_argument(
        "--step-mode",
        choices=("grid", "bar"),
        default="grid",
        help="grid = fixed sim step seconds; bar = jump to each resampled bar time",
    )
    p.add_argument(
        "--sim-step-seconds",
        type=int,
        default=30,
        help="Simulated poll interval for grid mode (default 30)",
    )
    p.add_argument(
        "--speed",
        type=float,
        default=10.0,
        help="Wall sleep = sim_step_seconds / speed (default 10)",
    )
    p.add_argument(
        "--no-sleep",
        action="store_true",
        help="Do not sleep (full run as fast as CPU allows)",
    )
    p.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Stop after this many iterations (safety)",
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
        help="Slippage applied to stop/trigger exits (and entries unless overridden)",
    )
    p.add_argument(
        "--close-slippage-ticks",
        type=float,
        default=0.0,
        help="Slippage applied to close-all / flatten exits",
    )
    p.add_argument(
        "--entry-slippage-ticks",
        type=float,
        default=None,
        help="Optional entry-only slippage override; defaults to --stop-slippage-ticks",
    )
    p.add_argument(
        "--exit-slippage-ticks",
        type=float,
        default=None,
        help="Optional exit-only slippage override; defaults to --stop-slippage-ticks",
    )
    p.add_argument("--trace-jsonl", type=Path, default=None)
    p.add_argument(
        "--stats-out",
        type=Path,
        default=None,
        help="Write run summary JSON here (default: reports/phoenix_live_replay_stats_<range>.json)",
    )
    p.add_argument(
        "--no-stats",
        action="store_true",
        help="Do not write a summary JSON file",
    )
    p.add_argument(
        "--no-live-trade-stats",
        action="store_true",
        help="Skip per-step run_backtest WR/PF/PnL (faster; omits live_backtest_trades in stats JSON)",
    )
    p.add_argument(
        "--bars-window",
        choices=("session_day", "range_prefix"),
        default="session_day",
        help=(
            "session_day: run_scan_once uses only the calendar day of as_of (default). "
            "range_prefix: load bars from --start-date 00:00 ET through as_of (causal; use short ranges)."
        ),
    )
    p.add_argument(
        "--trades-csv",
        type=Path,
        default=None,
        help=(
            "Write deduped live-replay closed trades (requires live trade stats). "
            "Default: <stats_stem>_trades.csv next to --stats-out."
        ),
    )
    p.add_argument(
        "--live-entry-parity",
        action="store_true",
        help=(
            "After each run_scan_once, drop hits that live would skip with stop@trigger "
            "(execution.phoenix_entry_order limit): same as entry_breakout_stop_valid vs last "
            "bar close in projectx/main.py. Use --parity-market-entry to mimic --phoenix-market-entry."
        ),
    )
    p.add_argument(
        "--parity-market-entry",
        action="store_true",
        help="With --live-entry-parity, assume market entry (skip stop-validity; matches --phoenix-market-entry).",
    )
    args = p.parse_args()

    if args.trades_csv is not None and args.no_live_trade_stats:
        p.error("--trades-csv requires live trade stats (omit --no-live-trade-stats)")
    if args.trades_csv is not None and args.no_stats:
        p.error("--trades-csv cannot be used with --no-stats")

    if args.year is None and (args.start_date is None or args.end_date is None):
        p.error("Provide --year or both --start-date and --end-date")

    if args.start_date and args.end_date:
        start_d = date.fromisoformat(args.start_date)
        end_d = date.fromisoformat(args.end_date)
    else:
        y = int(args.year)
        start_d = date(y, 1, 1)
        end_d = date(y, 12, 31)

    start_s = start_d.isoformat() + " 00:00:00"
    end_s = end_d.isoformat() + " 23:59:59"

    data_dir = Path(args.data_dir).expanduser().resolve()
    if not data_dir.is_dir():
        raise SystemExit(f"data-dir not found: {data_dir}")

    replay_range_start_et: datetime | None = None
    if args.bars_window == "range_prefix":
        replay_range_start_et = datetime(start_d.year, start_d.month, start_d.day, 0, 0, 0, tzinfo=ET)
        span_days = (end_d - start_d).days + 1
        if span_days > 120:
            print(
                f"Warning: --bars-window range_prefix over {span_days} days reloads a growing "
                f"bar history every step (slow). Prefer ~1 month or less for this mode.",
                file=sys.stderr,
                flush=True,
            )

    instruments = [x.strip().upper() for x in args.instruments.split(",") if x.strip()]
    parts = [x.strip() for x in args.contracts.split(",") if x.strip()]
    sizes = {}
    for i, inst in enumerate(instruments):
        n = int(parts[i]) if i < len(parts) else int(parts[-1])
        sizes[inst] = max(1, n)

    imap = _stub_imap(instruments)
    exec_opts = ExecutionOptions(
        entry_fill_mode=args.entry_fill_mode,
        stop_slippage_ticks=float(args.stop_slippage_ticks),
        close_slippage_ticks=float(args.close_slippage_ticks),
        entry_slippage_ticks=(
            float(args.entry_slippage_ticks)
            if args.entry_slippage_ticks is not None
            else None
        ),
        exit_slippage_ticks=(
            float(args.exit_slippage_ticks)
            if args.exit_slippage_ticks is not None
            else None
        ),
    )
    cache: dict[tuple[str, str], pd.DataFrame] | None = (
        {} if args.bars_window == "session_day" else None
    )

    if args.step_mode == "grid":
        timeline = _grid_times(start_d, end_d, step_seconds=args.sim_step_seconds)
    else:
        timeline = _bar_timeline(data_dir, instruments, start_s, end_s)

    n = len(timeline)
    if n == 0:
        print("No timeline points; check data range and files.", file=sys.stderr)
        return 1

    sleep_s = 0.0 if args.no_sleep else max(0.0, float(args.sim_step_seconds) / max(0.001, float(args.speed)))
    est_wall = n * sleep_s
    print(
        f"Phoenix live-pace replay: mode={args.step_mode} steps={n} "
        f"instruments={instruments} sleep_s={sleep_s:.4f} est_wall_h={est_wall/3600:.2f}",
        flush=True,
    )
    if n > 50_000 and not args.no_sleep and sleep_s > 0:
        print(
            "Warning: long run. Consider --no-sleep, --step-mode bar, --max-steps, or a shorter date range.",
            flush=True,
        )

    trace_fh = open(args.trace_jsonl, "a", encoding="utf-8") if args.trace_jsonl else None
    steps_done = 0
    steps_with_hits = 0
    total_hit_events = 0
    hit_fingerprints: dict[str, dict[str, Any]] = {}
    hits_by_symbol: dict[str, int] = {i: 0 for i in instruments}
    want_live_trades = not args.no_stats and not args.no_live_trade_stats
    live_seen: set[tuple[str, str, str, str]] = set()
    live_closed_rows: list[pd.DataFrame] = []
    wall_t0 = time.perf_counter()
    progress_path: Path | None = None
    if not args.no_stats and args.stats_out is not None:
        progress_path = (
            Path(args.stats_out).expanduser().resolve().with_suffix(".progress.json")
        )
    parity_limit_entry = not bool(args.parity_market_entry)
    parity_skip_totals: dict[str, int] = {}
    steps_with_eligible_hits = 0
    total_eligible_hit_events = 0

    try:
        for as_of in timeline:
            hits, _diag, _audit, bars_by = run_scan_once(
                instruments=instruments,
                sizes=sizes,
                data_dir=data_dir,
                client=None,
                gateway_sim=True,
                imap=imap,
                as_of_et=as_of,
                tick_sizes=TICK_SIZES,
                tick_values=TICK_VALUES,
                get_config_fn=get_config,
                collect_diagnostics=False,
                opening_range_addon_fetch=True,
                execution_options=exec_opts,
                session_bar_cache=cache,
                replay_range_start_et=replay_range_start_et,
            )
            raw_hits = hits
            if args.live_entry_parity:
                hits, sk = filter_hits_with_live_stop_gate(
                    raw_hits,
                    bars_by,
                    TICK_SIZES,
                    phoenix_limit_entry=parity_limit_entry,
                )
                for k, v in sk.items():
                    parity_skip_totals[k] = parity_skip_totals.get(k, 0) + v
            else:
                hits = raw_hits

            if want_live_trades:
                for inst in instruments:
                    b = bars_by.get(inst)
                    if b is None or len(b) < 12:
                        continue
                    cfg = get_config(inst)
                    tsz = float(TICK_SIZES[inst])
                    eng = run_backtest(
                        cfg,
                        b,
                        tsz,
                        return_trades=True,
                        execution=exec_opts,
                    )
                    for tr in eng.get("trades") or []:
                        k = _trade_close_key(inst, tr)
                        if k in live_seen:
                            continue
                        live_seen.add(k)
                        one = raw_trades_frame({"trades": [tr]})
                        row = scaled_trades(one, inst, sizes[inst])
                        row["instrument"] = inst
                        row["contracts"] = int(sizes[inst])
                        live_closed_rows.append(row)
            parts_ln = [
                f"as_of={as_of.isoformat()}",
                f"raw_hits={len(raw_hits)}",
            ]
            if args.live_entry_parity:
                parts_ln.append(f"eligible_hits={len(hits)}")
            else:
                parts_ln.append(f"hits={len(hits)}")
            for inst in instruments:
                b = bars_by.get(inst)
                nb = len(b) if b is not None else 0
                last = ""
                if b is not None and nb:
                    last = str(b.index[-1])
                parts_ln.append(f"{inst}:n={nb}last={last}")
            if raw_hits:
                steps_with_hits += 1
                total_hit_events += len(raw_hits)
            if hits and args.live_entry_parity:
                steps_with_eligible_hits += 1
                total_eligible_hit_events += len(hits)
            if hits:
                for h in hits:
                    inst_h, tr, _r, _rw = h[0], h[1], h[2], h[3]
                    fp = trade_fingerprint(inst_h, tr)
                    hits_by_symbol[inst_h] = hits_by_symbol.get(inst_h, 0) + 1
                    if fp not in hit_fingerprints:
                        hit_fingerprints[fp] = {
                            "symbol": inst_h,
                            "first_as_of_et": as_of.isoformat(),
                            "last_as_of_et": as_of.isoformat(),
                            "direction": str(tr.get("direction", "")),
                            "count": 0,
                        }
                    hit_fingerprints[fp]["last_as_of_et"] = as_of.isoformat()
                    hit_fingerprints[fp]["count"] += 1
                parts_ln.append(
                    "NEW=" + ",".join(trade_fingerprint(h[0], h[1]) for h in hits)
                )
            line = " | ".join(parts_ln)
            print(line, flush=True)
            if trace_fh:
                trace_payload: dict[str, Any] = {
                    "as_of_et": as_of.isoformat(),
                    "raw_hits": len(raw_hits),
                    "hits": len(hits),
                    "fingerprints": [trade_fingerprint(h[0], h[1]) for h in hits],
                    "bars_n": {
                        i: (0 if bars_by.get(i) is None else len(bars_by.get(i)))
                        for i in instruments
                    },
                }
                if args.live_entry_parity:
                    trace_payload["live_entry_parity"] = True
                trace_fh.write(json.dumps(trace_payload) + "\n")
            steps_done += 1
            if progress_path is not None and (
                steps_done == 1
                or steps_done % _PROGRESS_WRITE_EVERY == 0
                or steps_done == n
            ):
                _write_replay_progress(
                    progress_path,
                    steps=steps_done,
                    timeline_points=n,
                    replay_wall_seconds=time.perf_counter() - wall_t0,
                    live_trades_n=len(live_closed_rows),
                )
            if args.max_steps is not None and steps_done >= args.max_steps:
                print(f"Stopped at --max-steps {args.max_steps}", flush=True)
                break
            if sleep_s > 0:
                time.sleep(sleep_s)
    finally:
        if trace_fh:
            trace_fh.close()

    wall_s = time.perf_counter() - wall_t0

    if not args.no_stats:
        if args.stats_out is not None:
            stats_path = Path(args.stats_out).expanduser().resolve()
        else:
            rep = REPO_ROOT / "reports"
            rep.mkdir(parents=True, exist_ok=True)
            if args.year is not None:
                tag = f"{int(args.year)}_{args.step_mode}"
            else:
                tag = f"{start_d.isoformat()}_{end_d.isoformat()}_{args.step_mode}"
            stats_path = rep / f"phoenix_live_replay_stats_{tag}.json"

        summary: dict[str, Any] = {
            "script": "phoenix_live_pace_replay.py",
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "bars_window": args.bars_window,
            "step_mode": args.step_mode,
            "sim_step_seconds": args.sim_step_seconds,
            "speed": args.speed,
            "no_sleep": bool(args.no_sleep),
            "instruments": instruments,
            "contracts": sizes,
            "entry_fill_mode": args.entry_fill_mode,
            "stop_slippage_ticks": float(args.stop_slippage_ticks),
            "close_slippage_ticks": float(args.close_slippage_ticks),
            "entry_slippage_ticks": (
                float(args.entry_slippage_ticks)
                if args.entry_slippage_ticks is not None
                else None
            ),
            "exit_slippage_ticks": (
                float(args.exit_slippage_ticks)
                if args.exit_slippage_ticks is not None
                else None
            ),
            "data_dir": str(data_dir),
            "timeline_points": n,
            "steps_executed": steps_done,
            "steps_with_any_hit": steps_with_hits,
            "total_hit_events": total_hit_events,
            "unique_signal_fingerprints": len(hit_fingerprints),
            "hits_by_symbol": hits_by_symbol,
            "signals": list(hit_fingerprints.values()),
            "wall_seconds": round(wall_s, 3),
        }
        if args.live_entry_parity:
            summary["live_entry_parity"] = {
                "enabled": True,
                "phoenix_limit_entry": parity_limit_entry,
                "steps_with_eligible_hit": steps_with_eligible_hits,
                "total_eligible_hit_events": total_eligible_hit_events,
                "stop_gate_skip_reasons": dict(
                    sorted(parity_skip_totals.items(), key=lambda kv: kv[0])
                ),
                "note": (
                    "When enabled, NEW=/fingerprints/hits_by_symbol count only hits that pass "
                    "entry_breakout_stop_valid (stop@trigger vs last bar close), matching "
                    "projectx/main.py before bracket execution. total_hit_events is still raw engine hits."
                ),
            }
        else:
            summary["live_entry_parity"] = {"enabled": False}
        if want_live_trades:
            _lt_desc = (
                "Closed round-trips from run_backtest on causal prefix bars from start_date through each "
                "as_of_et (bars_window=range_prefix; same window as run_scan_once); first time each "
                "(symbol, entry, exit, dir) appears in the engine trade list. "
                "Scaled pnl_usd = pnl_ticks × TICK_VALUES × contracts."
                if args.bars_window == "range_prefix"
                else (
                    "Closed round-trips from run_backtest on session-day-only bars trimmed to each as_of_et "
                    "(bars_window=session_day; same window as run_scan_once); first time each "
                    "(symbol, entry, exit, dir) appears in the engine trade list. "
                    "Scaled pnl_usd = pnl_ticks × TICK_VALUES × contracts."
                )
            )
            if live_closed_rows:
                merged = pd.concat(live_closed_rows, ignore_index=True).sort_values(
                    "exit_ts", kind="mergesort"
                )
                pnls = merged["pnl_usd"].to_numpy(dtype=float)
                m = trade_metrics(pnls)
                wins = pnls[pnls > 0]
                losses = pnls[pnls < 0]
                gross_profit = float(wins.sum()) if len(wins) else 0.0
                gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
                summary["live_backtest_trades"] = {
                    "description": _lt_desc,
                    "n_trades": int(m["n_trades"]),
                    "win_rate_pct": round(float(m["win_rate"]), 6),
                    "profit_factor": round(float(m["profit_factor"]), 6),
                    "expectancy_usd": round(float(m["expectancy"]), 6),
                    "trade_sharpe": round(float(m["sharpe"]), 6),
                    "total_pnl_usd": round(float(pnls.sum()), 6),
                    "gross_profit_usd": round(gross_profit, 6),
                    "gross_loss_usd": round(gross_loss, 6),
                }
            else:
                summary["live_backtest_trades"] = {
                    "description": _lt_desc,
                    "n_trades": 0,
                    "win_rate_pct": 0.0,
                    "profit_factor": 0.0,
                    "expectancy_usd": 0.0,
                    "trade_sharpe": 0.0,
                    "total_pnl_usd": 0.0,
                    "gross_profit_usd": 0.0,
                    "gross_loss_usd": 0.0,
                }
            trades_csv_path = (
                Path(args.trades_csv).expanduser().resolve()
                if args.trades_csv is not None
                else stats_path.with_name(stats_path.stem + "_trades.csv")
            )
            merged_for_csv = (
                pd.concat(live_closed_rows, ignore_index=True).sort_values(
                    "exit_ts", kind="mergesort"
                )
                if live_closed_rows
                else pd.DataFrame()
            )
            _write_live_replay_trades_csv(merged_for_csv, trades_csv_path)
            summary["trades_csv"] = str(trades_csv_path)
            print(f"Wrote trades CSV: {trades_csv_path}", flush=True)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        pp = stats_path.with_suffix(".progress.json")
        if pp.is_file():
            try:
                pp.unlink()
            except OSError:
                pass
        print(f"Wrote stats: {stats_path}", flush=True)
        if want_live_trades and summary.get("live_backtest_trades"):
            lt = summary["live_backtest_trades"]
            print(
                f"Live backtest closes: n_trades={lt.get('n_trades')} "
                f"WR%={lt.get('win_rate_pct')} PF={lt.get('profit_factor')} "
                f"total_pnl_usd={lt.get('total_pnl_usd')}",
                flush=True,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_telegram(main, script_name="phoenix_live_pace_replay"))
