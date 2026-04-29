#!/usr/bin/env python3
"""Discover realistically profitable strategy variants for CL/MGC/MNQ/YM."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from telegram_script_done import run_with_telegram

from backtester import load_bars, max_drawdown, raw_trades_frame, resolve_data_dir, scaled_trades, trade_metrics
from configs.strategy_configs import get_config
from configs.strategy_research_specs import FAMILY_SPECS, REALISTIC_EXECUTION, SESSION_WINDOWS
from configs.tick_config import TICK_SIZES
from engine.fast_engine import ExecutionOptions, FastConfig, run_backtest

INSTRUMENTS = ["CL", "MGC", "MNQ", "YM"]


def _mk_exec() -> ExecutionOptions:
    return ExecutionOptions(
        entry_fill_mode=str(REALISTIC_EXECUTION["entry_fill_mode"]),
        stop_slippage_ticks=float(REALISTIC_EXECUTION["stop_slippage_ticks"]),
        close_slippage_ticks=float(REALISTIC_EXECUTION["close_slippage_ticks"]),
    )


def _variant_grid(instrument: str, family: str, session_mode: str, max_variants: int) -> list[tuple[str, FastConfig]]:
    base = get_config(instrument)
    spec = FAMILY_SPECS[family]
    keys = list(spec.grid.keys())
    combos = list(product(*(spec.grid[k] for k in keys)))
    t_start, t_end = SESSION_WINDOWS[session_mode][instrument]
    out: list[tuple[str, FastConfig]] = []
    for idx, values in enumerate(combos):
        if idx >= max_variants:
            break
        params = dict(zip(keys, values))
        cfg = FastConfig(**asdict(base))
        cfg.trade_start_minutes = t_start
        cfg.trade_end_minutes = t_end
        cfg.close_all_minutes = min(base.close_all_minutes, t_end + 60)
        cfg.bar_minutes = int(params.get("bar_minutes", cfg.bar_minutes))
        cfg.entry_tick_offset = int(params.get("entry_tick_offset", cfg.entry_tick_offset))
        cfg.max_entries_per_day = int(params.get("max_entries_per_day", cfg.max_entries_per_day))
        cfg.breakeven_on = bool(params.get("breakeven_on", cfg.breakeven_on))
        cfg.trail_on = bool(params.get("trail_on", cfg.trail_on))
        if family == "atr_volatility":
            cfg.atr_adaptive = True
            cfg.sl_atr_mult = float(params["sl_atr_mult"])
            cfg.pt_atr_mult = float(params["pt_atr_mult"])
            cfg.trail_atr_mult = float(params["trail_atr_mult"])
            cfg.stop_loss_ticks = 0.0
            cfg.profit_target_ticks = 0.0
        else:
            stop = float(params["stop_loss_ticks"])
            rr = float(params["rr_multiple"])
            cfg.atr_adaptive = False
            cfg.stop_loss_ticks = stop
            cfg.profit_target_ticks = max(stop + 1.0, stop * rr)
            if family == "time_exit":
                close_buffer = int(params["close_buffer_minutes"])
                cfg.close_all_minutes = min(cfg.close_all_minutes, t_end + close_buffer)
                cfg.breakeven_on = True
                cfg.breakeven_after_ticks = max(8.0, stop * 0.5)
                cfg.trail_start_after_ticks = max(10.0, stop * 0.75)
        out.append((f"{instrument}_{session_mode}_{family}_{idx:03d}", cfg))
    return out


def _daily_pnl(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float)
    return trades.groupby("exit_date")["pnl_usd"].sum().sort_index()


def _walk_forward_score(daily: pd.Series, folds: int = 4) -> float:
    if daily.empty or len(daily) < 60:
        return 0.0
    vals = daily.to_numpy(dtype=float)
    chunk = max(1, len(vals) // folds)
    scores = []
    for i in range(folds):
        seg = vals[i * chunk : (i + 1) * chunk]
        if len(seg) < 8:
            continue
        mu = float(np.mean(seg))
        sd = float(np.std(seg, ddof=0))
        scores.append(0.0 if sd <= 1e-9 else mu / sd)
    if not scores:
        return 0.0
    return float(np.mean(scores) - np.std(np.array(scores), ddof=0))


def _run_variant(instrument: str, cfg: FastConfig, bars: pd.DataFrame, contracts: int, exec_opts: ExecutionOptions) -> dict[str, float]:
    result = run_backtest(cfg, bars, TICK_SIZES[instrument], return_trades=True, execution=exec_opts)
    raw = raw_trades_frame(result)
    trades = scaled_trades(raw, instrument, contracts)
    if trades.empty:
        return {
            "n_trades": 0.0,
            "total_pnl_usd": 0.0,
            "profit_factor": 0.0,
            "expectancy_usd": 0.0,
            "win_rate": 0.0,
            "max_dd_usd": 0.0,
            "walk_forward": 0.0,
            "profitability_score": -1e9,
        }
    pn = trades["pnl_usd"].to_numpy(dtype=float)
    tm = trade_metrics(pn)
    equity = trades.sort_values("exit_ts")["pnl_usd"].cumsum()
    dd = max_drawdown(equity)
    daily = _daily_pnl(trades)
    wf = _walk_forward_score(daily)
    pnl = float(pn.sum())
    score = pnl - (dd * 1.25) + (tm["profit_factor"] * 900.0) + (wf * 1200.0)
    return {
        "n_trades": float(tm["n_trades"]),
        "total_pnl_usd": pnl,
        "profit_factor": float(tm["profit_factor"]),
        "expectancy_usd": float(tm["expectancy"]),
        "win_rate": float(tm["win_rate"]),
        "max_dd_usd": float(dd),
        "walk_forward": float(wf),
        "profitability_score": float(score),
    }


def _dedupe_key(row: pd.Series) -> tuple[Any, ...]:
    return (
        row["instrument"],
        row["family"],
        row["session_mode"],
        round(float(row["total_pnl_usd"]) / 250.0),
        round(float(row["profit_factor"]), 2),
        round(float(row["max_dd_usd"]) / 100.0),
        int(row["n_trades"] // 20),
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Find realistically profitable candidates.")
    p.add_argument("--data-dir", default=None)
    p.add_argument("--reports-dir", default=str(SCRIPT_DIR.parent / "reports" / "profitability_discovery"))
    p.add_argument("--oos-start", default="2023-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--max-variants-per-family", type=int, default=60)
    p.add_argument("--contracts-per-test", type=int, default=1)
    p.add_argument("--min-trades", type=int, default=120)
    p.add_argument("--min-profit-factor", type=float, default=1.15)
    p.add_argument("--top-k-per-instrument", type=int, default=12)
    args = p.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    out_dir = Path(args.reports_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    exec_opts = _mk_exec()

    rows: list[dict[str, Any]] = []
    for inst in INSTRUMENTS:
        _, bars = load_bars(inst, data_dir, args.oos_start, args.oos_end)
        for family in FAMILY_SPECS:
            for session_mode in ("full_day", "after_1pm"):
                for variant_id, cfg in _variant_grid(inst, family, session_mode, args.max_variants_per_family):
                    metrics = _run_variant(inst, cfg, bars, args.contracts_per_test, exec_opts)
                    rows.append(
                        {
                            "instrument": inst,
                            "variant_id": variant_id,
                            "family": family,
                            "session_mode": session_mode,
                            **metrics,
                        }
                    )

    all_df = pd.DataFrame(rows)
    all_df.to_csv(out_dir / "all_candidates_realistic.csv", index=False)

    # de-duplicate near-identical variants
    deduped_parts = []
    for inst, g in all_df.groupby("instrument"):
        g = g.sort_values("profitability_score", ascending=False).copy()
        seen = set()
        keep_idx = []
        for i, row in g.iterrows():
            k = _dedupe_key(row)
            if k in seen:
                continue
            seen.add(k)
            keep_idx.append(i)
        deduped = g.loc[keep_idx]
        deduped_parts.append(deduped)
    deduped_df = pd.concat(deduped_parts, ignore_index=True) if deduped_parts else pd.DataFrame()
    deduped_df.to_csv(out_dir / "deduped_candidates.csv", index=False)

    viable = deduped_df[
        (deduped_df["total_pnl_usd"] > 0.0)
        & (deduped_df["profit_factor"] >= float(args.min_profit_factor))
        & (deduped_df["n_trades"] >= float(args.min_trades))
        & (deduped_df["walk_forward"] >= 0.0)
    ].copy()
    viable = viable.sort_values(["instrument", "profitability_score"], ascending=[True, False])
    viable.to_csv(out_dir / "profitable_candidates.csv", index=False)

    near_miss = deduped_df[
        (deduped_df["profit_factor"] >= 1.0)
        & (deduped_df["n_trades"] >= float(args.min_trades))
    ].copy()
    near_miss = near_miss.sort_values(["instrument", "profitability_score"], ascending=[True, False])
    near_miss.to_csv(out_dir / "near_miss_candidates.csv", index=False)

    top_parts = []
    source_df = viable if not viable.empty else near_miss
    for inst, g in source_df.groupby("instrument"):
        top_parts.append(g.head(args.top_k_per_instrument))
    top_df = pd.concat(top_parts, ignore_index=True) if top_parts else pd.DataFrame()
    top_df.to_csv(out_dir / "top_candidates_for_promotion.csv", index=False)

    summary = {
        "reports_dir": str(out_dir),
        "oos_start": args.oos_start,
        "oos_end": args.oos_end,
        "total_tested": int(len(all_df)),
        "deduped_count": int(len(deduped_df)),
        "profitable_count": int(len(viable)),
        "near_miss_count": int(len(near_miss)),
        "promotion_count": int(len(top_df)),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_telegram(main, script_name="run_profitability_discovery_test"))
