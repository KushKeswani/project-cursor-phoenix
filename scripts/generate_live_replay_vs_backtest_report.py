#!/usr/bin/env python3
"""
Build reports/LIVE_REPLAY_VS_BACKTEST.md comparing each portfolio preset's live replay
stats JSON to a traditional contiguous backtest on the same calendar window and contracts.

Traditional backtest: full-session bars, run_backtest per instrument, merged_scaled_trades.
Live replay: live_backtest_trades (and trades CSV) from phoenix_live_pace_replay output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from backtester import (
    INSTRUMENTS,
    daily_sharpe,
    load_bars,
    max_drawdown,
    merged_scaled_trades,
    raw_trades_frame,
    resolve_data_dir,
    trade_metrics,
)
from configs.strategy_configs import get_config
from configs.tick_config import TICK_SIZES
from engine.fast_engine import run_backtest

ET = ZoneInfo("America/New_York")


def _contracts_from_json(c: dict[str, object]) -> dict[str, int]:
    return {i: int(c.get(i, 0) or 0) for i in INSTRUMENTS}


def _daily_pnl_et_from_merged(merged: pd.DataFrame) -> pd.Series:
    if merged.empty:
        return pd.Series(dtype=float)
    t = pd.to_datetime(merged["exit_ts"])
    if getattr(t.dt, "tz", None) is None:
        t = t.dt.tz_localize("UTC", ambiguous="infer", nonexistent="shift_forward")
    else:
        t = t.dt.tz_convert("UTC")
    t_et = t.dt.tz_convert(ET)
    day = t_et.dt.normalize()
    x = merged.copy()
    x["_d"] = day
    return x.groupby("_d", sort=True)["pnl_usd"].sum()


def _monthly_pnl_et_from_merged(merged: pd.DataFrame) -> pd.Series:
    if merged.empty:
        return pd.Series(dtype=float)
    t = pd.to_datetime(merged["exit_ts"])
    if getattr(t.dt, "tz", None) is None:
        t = t.dt.tz_localize("UTC", ambiguous="infer", nonexistent="shift_forward")
    else:
        t = t.dt.tz_convert("UTC")
    t_et = t.dt.tz_convert(ET)
    x = merged.copy()
    x["_m"] = t_et.dt.to_period("M").dt.to_timestamp()
    return x.groupby("_m", sort=True)["pnl_usd"].sum()


def _daily_pnl_from_live_csv(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    if df.empty or "exit_ts_et" not in df.columns or "pnl_usd" not in df.columns:
        return pd.Series(dtype=float)
    t = pd.to_datetime(df["exit_ts_et"])
    if getattr(t.dt, "tz", None) is None:
        t = t.dt.tz_localize(ET, ambiguous="infer", nonexistent="shift_forward")
    else:
        t = t.dt.tz_convert(ET)
    x = df.copy()
    x["_d"] = t.dt.normalize()
    return x.groupby("_d", sort=True)["pnl_usd"].sum()


def _monthly_pnl_from_live_csv(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    if df.empty or "exit_ts_et" not in df.columns or "pnl_usd" not in df.columns:
        return pd.Series(dtype=float)
    t = pd.to_datetime(df["exit_ts_et"])
    if getattr(t.dt, "tz", None) is None:
        t = t.dt.tz_localize(ET, ambiguous="infer", nonexistent="shift_forward")
    else:
        t = t.dt.tz_convert(ET)
    x = df.copy()
    x["_m"] = t.dt.to_period("M").dt.to_timestamp()
    return x.groupby("_m", sort=True)["pnl_usd"].sum()


def _trade_block_from_csv(path: Path) -> dict[str, float]:
    df = pd.read_csv(path)
    if df.empty or "pnl_usd" not in df.columns:
        return {
            "n_trades": 0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "expectancy_usd": 0.0,
            "trade_sharpe": 0.0,
            "total_pnl_usd": 0.0,
            "gross_profit_usd": 0.0,
            "gross_loss_usd": 0.0,
        }
    pnls = df["pnl_usd"].to_numpy(dtype=float)
    m = trade_metrics(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gp = float(wins.sum()) if len(wins) else 0.0
    gl = float(abs(losses.sum())) if len(losses) else 0.0
    return {
        "n_trades": int(m["n_trades"]),
        "win_rate_pct": float(m["win_rate"]),
        "profit_factor": float(m["profit_factor"]),
        "expectancy_usd": float(m["expectancy"]),
        "trade_sharpe": float(m["sharpe"]),
        "total_pnl_usd": float(pnls.sum()),
        "gross_profit_usd": gp,
        "gross_loss_usd": gl,
    }


def run_traditional_merged(
    *,
    data_dir: Path,
    start: str,
    end: str,
    contracts: dict[str, int],
) -> pd.DataFrame:
    raw_by_inst: dict[str, pd.DataFrame] = {}
    for inst in INSTRUMENTS:
        if contracts[inst] <= 0:
            raw_by_inst[inst] = pd.DataFrame()
            continue
        _, bars = load_bars(inst, data_dir, start, end)
        cfg = get_config(inst)
        raw_by_inst[inst] = raw_trades_frame(
            run_backtest(cfg, bars, TICK_SIZES[inst], return_trades=True)
        )
    return merged_scaled_trades(raw_by_inst, contracts)


def _fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def _fmt_pct(x: float) -> str:
    return f"{x:.2f}%"


def _fmt_float(x: float) -> str:
    if abs(x) >= 1e6:
        return f"{x:,.2f}"
    return f"{x:.4f}"


def _row_triple(metric: str, a: str, b: str, d: str) -> str:
    return f"| {metric} | {a} | {b} | {d} |"


def _delta_str(trad: float, live: float, *, is_pct_point: bool = False) -> str:
    d = live - trad
    if is_pct_point:
        return f"{d:+.2f} pp"
    return f"{d:+,.2f}" if abs(d) >= 0.01 else f"{d:+.4f}"


def build_markdown(
    *,
    live_dir: Path,
    out_md: Path,
    data_dir_fallback: Path | None,
) -> str:
    live_dir = live_dir.resolve()
    json_files = sorted(
        p
        for p in live_dir.glob("*.json")
        if p.is_file() and p.name.upper() != "MANIFEST.JSON"
    )
    lines: list[str] = [
        "# Live replay vs traditional backtest",
        "",
        "For each Phoenix portfolio preset, **traditional backtest** is a contiguous "
        "`run_backtest` on full session bars for the **same `start_date`–`end_date` and contract counts** "
        "recorded in that preset’s live replay stats JSON. **Live replay** uses closed trades collected "
        "during bar-step replay (deduped engine closes; see `live_backtest_trades.description` in the JSON).",
        "",
        "**Daily / monthly path metrics** below aggregate realized PnL by **US/Eastern calendar day** of `exit_ts` "
        "(traditional: engine timestamps interpreted as UTC then converted to ET; live: `exit_ts_et`).",
        "",
        "**Trade count:** Live replay often reports **more closed trades** than the traditional run because it records "
        "round-trips discovered across many `as_of` bar steps (see `unique_signal_fingerprints` vs `n_trades` in the JSON). "
        "Per-day realized PnL can still line up on the same number of Eastern trading days when you bucket exits by date.",
        "",
    ]

    for jpath in json_files:
        data = json.loads(jpath.read_text(encoding="utf-8"))
        preset_name = jpath.stem
        start = str(data.get("start_date", ""))
        end = str(data.get("end_date", ""))
        dd = Path(str(data.get("data_dir", "")))
        if not dd.is_dir() and data_dir_fallback is not None:
            dd = data_dir_fallback
        elif not dd.is_dir():
            lines.extend(
                [
                    f"## {preset_name}",
                    "",
                    f"Skipped: data_dir missing (`{data.get('data_dir')}`).",
                    "",
                ]
            )
            continue

        contracts = _contracts_from_json(data.get("contracts") or {})
        cstr = ", ".join(f"{k} {contracts[k]}" for k in INSTRUMENTS)

        live_lt = data.get("live_backtest_trades")
        trades_csv = Path(str(data.get("trades_csv", "")))
        if not isinstance(live_lt, dict) or "n_trades" not in live_lt:
            live_lt = _trade_block_from_csv(trades_csv) if trades_csv.is_file() else {}
        else:
            live_lt = dict(live_lt)

        merged = run_traditional_merged(data_dir=dd, start=start, end=end, contracts=contracts)
        pnls = merged["pnl_usd"].to_numpy(dtype=float) if not merged.empty else np.array([], dtype=float)
        tm = trade_metrics(pnls)
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        trad = {
            "n_trades": int(tm["n_trades"]),
            "win_rate_pct": float(tm["win_rate"]),
            "profit_factor": float(tm["profit_factor"]),
            "expectancy_usd": float(tm["expectancy"]),
            "trade_sharpe": float(tm["sharpe"]),
            "total_pnl_usd": float(pnls.sum()) if len(pnls) else 0.0,
            "gross_profit_usd": float(wins.sum()) if len(wins) else 0.0,
            "gross_loss_usd": float(abs(losses.sum())) if len(losses) else 0.0,
        }

        daily_t = _daily_pnl_et_from_merged(merged)
        monthly_t = _monthly_pnl_et_from_merged(merged)
        daily_l = _daily_pnl_from_live_csv(trades_csv) if trades_csv.is_file() else pd.Series(dtype=float)
        monthly_l = _monthly_pnl_from_live_csv(trades_csv) if trades_csv.is_file() else pd.Series(dtype=float)

        trad_dd = max_drawdown(daily_t.cumsum()) if not daily_t.empty else 0.0
        live_dd = max_drawdown(daily_l.cumsum()) if not daily_l.empty else 0.0
        trad_am = float(monthly_t.mean()) if not monthly_t.empty else 0.0
        live_am = float(monthly_l.mean()) if not monthly_l.empty else 0.0
        trad_ds = daily_sharpe(daily_t, 0.0)
        live_ds = daily_sharpe(daily_l, 0.0)

        live = {
            "n_trades": int(live_lt.get("n_trades", 0)),
            "win_rate_pct": float(live_lt.get("win_rate_pct", 0.0)),
            "profit_factor": float(live_lt.get("profit_factor", 0.0)),
            "expectancy_usd": float(live_lt.get("expectancy_usd", 0.0)),
            "trade_sharpe": float(live_lt.get("trade_sharpe", 0.0)),
            "total_pnl_usd": float(live_lt.get("total_pnl_usd", 0.0)),
            "gross_profit_usd": float(live_lt.get("gross_profit_usd", 0.0)),
            "gross_loss_usd": float(live_lt.get("gross_loss_usd", 0.0)),
        }

        lines.extend(
            [
                f"## {preset_name}",
                "",
                f"- **Window:** {start} → {end}",
                f"- **Data:** `{dd}`",
                f"- **Contracts:** {cstr}",
                f"- **Live stats JSON:** `{jpath}`",
                f"- **Live trades CSV:** `{trades_csv}`" if trades_csv.is_file() else "- **Live trades CSV:** (missing)",
                "",
                "### Portfolio trade statistics",
                "",
                "| Metric | Traditional backtest | Live replay | Δ (live − traditional) |",
                "|---|---:|---:|---|",
                _row_triple(
                    "Closed trades",
                    str(trad["n_trades"]),
                    str(live["n_trades"]),
                    str(live["n_trades"] - trad["n_trades"]),
                ),
                _row_triple(
                    "Win rate",
                    _fmt_pct(trad["win_rate_pct"]),
                    _fmt_pct(live["win_rate_pct"]),
                    _delta_str(trad["win_rate_pct"], live["win_rate_pct"], is_pct_point=True),
                ),
                _row_triple(
                    "Profit factor",
                    _fmt_float(trad["profit_factor"]),
                    _fmt_float(live["profit_factor"]),
                    _delta_str(trad["profit_factor"], live["profit_factor"]),
                ),
                _row_triple(
                    "Expectancy / trade",
                    _fmt_money(trad["expectancy_usd"]),
                    _fmt_money(live["expectancy_usd"]),
                    _delta_str(trad["expectancy_usd"], live["expectancy_usd"]),
                ),
                _row_triple(
                    "Trade Sharpe (rf=0)",
                    _fmt_float(trad["trade_sharpe"]),
                    _fmt_float(live["trade_sharpe"]),
                    _delta_str(trad["trade_sharpe"], live["trade_sharpe"]),
                ),
                _row_triple(
                    "Total PnL",
                    _fmt_money(trad["total_pnl_usd"]),
                    _fmt_money(live["total_pnl_usd"]),
                    _delta_str(trad["total_pnl_usd"], live["total_pnl_usd"]),
                ),
                _row_triple(
                    "Gross profit",
                    _fmt_money(trad["gross_profit_usd"]),
                    _fmt_money(live["gross_profit_usd"]),
                    _delta_str(trad["gross_profit_usd"], live["gross_profit_usd"]),
                ),
                _row_triple(
                    "Gross loss",
                    _fmt_money(trad["gross_loss_usd"]),
                    _fmt_money(live["gross_loss_usd"]),
                    _delta_str(trad["gross_loss_usd"], live["gross_loss_usd"]),
                ),
                "",
                "### Daily path (Eastern exit date)",
                "",
                "| Metric | Traditional | Live replay | Δ |",
                "|---|---:|---:|---|",
                _row_triple(
                    "Trading days with PnL",
                    str(int(len(daily_t))),
                    str(int(len(daily_l))),
                    str(int(len(daily_l) - len(daily_t))),
                ),
                _row_triple(
                    "Max drawdown (daily cum PnL)",
                    _fmt_money(trad_dd),
                    _fmt_money(live_dd),
                    _delta_str(trad_dd, live_dd),
                ),
                _row_triple(
                    "Avg monthly PnL",
                    _fmt_money(trad_am),
                    _fmt_money(live_am),
                    _delta_str(trad_am, live_am),
                ),
                _row_triple(
                    "Daily Sharpe (rf=0)",
                    _fmt_float(trad_ds),
                    _fmt_float(live_ds),
                    _delta_str(trad_ds, live_ds),
                ),
                "",
                "### Replay run metadata (live JSON only)",
                "",
                "| Field | Value |",
                "|---|---|",
                f"| Timeline points | {data.get('timeline_points', '—')} |",
                f"| Steps executed | {data.get('steps_executed', '—')} |",
                f"| Steps with any hit | {data.get('steps_with_any_hit', '—')} |",
                f"| Total hit events | {data.get('total_hit_events', '—')} |",
                f"| Unique signal fingerprints | {data.get('unique_signal_fingerprints', '—')} |",
                f"| Wall seconds (replay) | {data.get('wall_seconds', '—')} |",
                f"| Step mode | {data.get('step_mode', '—')} |",
                f"| Sim step seconds | {data.get('sim_step_seconds', '—')} |",
                f"| Entry fill mode | {data.get('entry_fill_mode', '—')} |",
                "",
            ]
        )

    lines.append(
        "---\n\n*Generated by `scripts/generate_live_replay_vs_backtest_report.py`.*\n"
    )
    text = "\n".join(lines)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--live-dir",
        type=Path,
        default=REPO_ROOT / "reports" / "live_replay_by_profile",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "reports" / "LIVE_REPLAY_VS_BACKTEST.md",
    )
    p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="If a profile JSON data_dir is missing, use this path",
    )
    args = p.parse_args()
    fallback = None
    if args.data_dir is not None:
        fallback = Path(args.data_dir).expanduser().resolve()
    else:
        try:
            fallback = resolve_data_dir(None)
        except FileNotFoundError:
            fallback = None

    build_markdown(live_dir=args.live_dir, out_md=args.out, data_dir_fallback=fallback)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
