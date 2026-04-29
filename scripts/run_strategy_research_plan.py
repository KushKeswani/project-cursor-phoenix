#!/usr/bin/env python3
"""End-to-end CL/MGC/MNQ/YM strategy research pipeline."""

from __future__ import annotations

import argparse
import json
import math
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

from backtester import (
    INSTRUMENTS,
    bust_probability,
    load_bars,
    max_drawdown,
    raw_trades_frame,
    resolve_data_dir,
    scaled_trades,
    trade_metrics,
)
from configs.portfolio_presets import PORTFOLIO_PRESETS
from configs.strategy_configs import get_config
from configs.strategy_research_specs import (
    DEFAULT_NEIGHBORHOOD_PERTURB,
    DEFAULT_TOP_N_PER_INSTRUMENT,
    FAMILY_SPECS,
    OPTIMISTIC_EXECUTION,
    REALISTIC_EXECUTION,
    SESSION_WINDOWS,
)
from configs.tick_config import TICK_SIZES
from engine.fast_engine import ExecutionOptions, FastConfig, run_backtest
from phoenix_live_pace_replay import _bar_timeline


def _daily_pnl_from_scaled(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float)
    out = trades.groupby("exit_date")["pnl_usd"].sum().sort_index()
    return out


def _session_minutes(instrument: str, session_mode: str) -> tuple[int, int]:
    return SESSION_WINDOWS[session_mode][instrument]


def _build_family_configs(
    instrument: str,
    family_name: str,
    session_mode: str,
    max_variants: int,
) -> list[tuple[str, FastConfig]]:
    base = get_config(instrument)
    spec = FAMILY_SPECS[family_name]
    keys = list(spec.grid.keys())
    combos = list(product(*(spec.grid[k] for k in keys)))
    variants: list[tuple[str, FastConfig]] = []
    t_start, t_end = _session_minutes(instrument, session_mode)
    for idx, values in enumerate(combos):
        if idx >= max_variants:
            break
        params = dict(zip(keys, values))
        cfg = FastConfig(**asdict(base))
        cfg.trade_start_minutes = t_start
        cfg.trade_end_minutes = t_end
        cfg.close_all_minutes = min(base.close_all_minutes, t_end + 60)
        cfg.max_entries_per_day = int(params.get("max_entries_per_day", cfg.max_entries_per_day))
        cfg.entry_tick_offset = int(params.get("entry_tick_offset", cfg.entry_tick_offset))
        cfg.bar_minutes = int(params.get("bar_minutes", cfg.bar_minutes))
        cfg.breakeven_on = bool(params.get("breakeven_on", cfg.breakeven_on))
        cfg.trail_on = bool(params.get("trail_on", cfg.trail_on))
        if family_name == "atr_volatility":
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
            cfg.profit_target_ticks = max(stop * rr, stop + 1.0)
            if family_name == "time_exit":
                # tighter "time-exit" behavior by exiting earlier in the day.
                close_buffer = int(params["close_buffer_minutes"])
                cfg.close_all_minutes = min(cfg.close_all_minutes, t_end + close_buffer)
                cfg.breakeven_on = True
                cfg.breakeven_after_ticks = max(8.0, stop * 0.5)
                cfg.trail_start_after_ticks = max(10.0, stop * 0.75)
        variant_id = f"{instrument}_{session_mode}_{family_name}_{idx:03d}"
        variants.append((variant_id, cfg))
    return variants


def _score_from_trades(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {
            "n_trades": 0.0,
            "total_pnl_usd": 0.0,
            "profit_factor": 0.0,
            "expectancy_usd": 0.0,
            "win_rate": 0.0,
            "max_dd_usd": 0.0,
            "recovery_factor": 0.0,
            "score": -1e9,
        }
    pn = trades["pnl_usd"].to_numpy(dtype=float)
    tm = trade_metrics(pn)
    equity = trades.sort_values("exit_ts")["pnl_usd"].cumsum()
    max_dd = max_drawdown(equity)
    total = float(pn.sum())
    rec = total / max_dd if max_dd > 1e-9 else 0.0
    # Weighted score that penalizes low sample and large drawdowns.
    sample_bonus = min(float(tm["n_trades"]) / 300.0, 1.0)
    score = (
        total * 0.001
        + tm["profit_factor"] * 2.0
        + tm["sharpe"] * 1.0
        + rec * 1.5
        + sample_bonus * 1.25
        - (max_dd * 0.0015)
    )
    return {
        "n_trades": float(tm["n_trades"]),
        "total_pnl_usd": total,
        "profit_factor": float(tm["profit_factor"]),
        "expectancy_usd": float(tm["expectancy"]),
        "win_rate": float(tm["win_rate"]),
        "max_dd_usd": float(max_dd),
        "recovery_factor": float(rec),
        "score": float(score),
    }


def _run_variant(
    instrument: str,
    cfg: FastConfig,
    bars: pd.DataFrame,
    contracts: int,
    execution: ExecutionOptions,
) -> tuple[pd.DataFrame, dict[str, float]]:
    result = run_backtest(cfg, bars, TICK_SIZES[instrument], return_trades=True, execution=execution)
    raw = raw_trades_frame(result)
    scaled = scaled_trades(raw, instrument, contracts)
    return scaled, _score_from_trades(scaled)


def _walk_forward_stability(daily: pd.Series, folds: int = 4) -> float:
    if daily.empty or len(daily) < folds * 20:
        return 0.0
    vals = daily.to_numpy(dtype=float)
    seg = len(vals) // folds
    if seg < 10:
        return 0.0
    fold_scores = []
    for i in range(folds):
        chunk = vals[i * seg : (i + 1) * seg]
        if len(chunk) < 2:
            continue
        mu = float(np.mean(chunk))
        sd = float(np.std(chunk, ddof=0))
        fold_scores.append(0.0 if sd <= 1e-9 else mu / sd)
    if not fold_scores:
        return 0.0
    penalty = float(np.std(np.array(fold_scores), ddof=0))
    return float(np.mean(fold_scores) - penalty)


def _perturb_and_score(
    instrument: str,
    base_cfg: FastConfig,
    bars: pd.DataFrame,
    contracts: int,
    execution: ExecutionOptions,
) -> float:
    vals = []
    for mult in DEFAULT_NEIGHBORHOOD_PERTURB:
        cfg = FastConfig(**asdict(base_cfg))
        if not cfg.atr_adaptive:
            cfg.stop_loss_ticks = max(2.0, cfg.stop_loss_ticks * mult)
            cfg.profit_target_ticks = max(3.0, cfg.profit_target_ticks * mult)
        else:
            cfg.sl_atr_mult = max(0.2, cfg.sl_atr_mult * mult)
            cfg.pt_atr_mult = max(0.5, cfg.pt_atr_mult * mult)
            cfg.trail_atr_mult = max(0.2, cfg.trail_atr_mult * mult)
        tr, sc = _run_variant(instrument, cfg, bars, contracts, execution)
        if tr.empty:
            vals.append(-2.0)
            continue
        daily = _daily_pnl_from_scaled(tr)
        vals.append(sc["score"] * 0.05 + _walk_forward_stability(daily))
    return float(np.mean(vals)) if vals else -999.0


def _mk_exec(mode: dict[str, Any]) -> ExecutionOptions:
    return ExecutionOptions(
        entry_fill_mode=str(mode["entry_fill_mode"]),
        stop_slippage_ticks=float(mode["stop_slippage_ticks"]),
        close_slippage_ticks=float(mode["close_slippage_ticks"]),
    )


def _allocation_assessment(df: pd.DataFrame, profile_name: str) -> pd.DataFrame:
    alloc = PORTFOLIO_PRESETS[profile_name]
    out = df.copy()
    out["contracts"] = out["instrument"].map(alloc).fillna(0).astype(int)
    out["alloc_score"] = out["score"] * np.sqrt(out["contracts"].clip(lower=0) + 1.0)
    out["profile"] = profile_name
    return out


def _go_live_gate(row: pd.Series) -> tuple[bool, list[str]]:
    reasons = []
    if float(row["n_trades"]) < 120:
        reasons.append("min_trade_count")
    if float(row["profit_factor"]) < 1.25:
        reasons.append("profit_factor")
    if float(row["max_dd_usd"]) > max(25000.0, float(row["total_pnl_usd"]) * 0.9):
        reasons.append("drawdown_cap")
    if float(row["robustness_score"]) < 0.25:
        reasons.append("robustness")
    if float(row["realism_degradation"]) > 0.35:
        reasons.append("realism_degradation")
    return (len(reasons) == 0, reasons)


def _write_go_live_files(
    out_dir: Path,
    finalists: pd.DataFrame,
) -> None:
    checklist_path = out_dir / "GO_LIVE_CHECKLIST.md"
    lines = [
        "# Go-Live Checklist",
        "",
        "## Must-pass gates",
        "",
        "- Performance: PF >= 1.25 and trade count >= 120",
        "- Drawdown: max drawdown <= max($25k, 90% of total pnl)",
        "- Stability: robustness_score >= 0.25",
        "- Reality: realism_degradation <= 35%",
        "- Operations: daily loss lock, kill switch, Telegram alerts configured",
        "- Shadow: at least 15 paper days in side-by-side mode",
        "",
        "## Candidate Signoff",
        "",
        "| Variant | Instrument | Pass | Failure Reasons |",
        "|---|---|---|---|",
    ]
    for _, row in finalists.iterrows():
        reasons = row["gate_fail_reasons"]
        lines.append(
            f"| {row['variant_id']} | {row['instrument']} | {'YES' if row['go_live_pass'] else 'NO'} | {reasons if reasons else '-'} |"
        )
    checklist_path.write_text("\n".join(lines), encoding="utf-8")


def _run_replay_smoke(
    data_dir: Path,
    out_dir: Path,
    start_date: str,
    end_date: str,
) -> Path:
    timeline = _bar_timeline(data_dir, INSTRUMENTS, f"{start_date} 00:00:00", f"{end_date} 23:59:59")
    payload = {
        "start_date": start_date,
        "end_date": end_date,
        "timeline_points": len(timeline),
        "replay_mode": "bar",
        "note": "Smoke-level replay proxy for finalists. Use phoenix_live_pace_replay.py for full pacing runs.",
    }
    out = out_dir / "replay_validation_summary.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Run CL/MGC/MNQ/YM strategy research pipeline.")
    p.add_argument("--data-dir", default=None)
    p.add_argument("--reports-dir", default=str(SCRIPT_DIR.parent / "reports" / "strategy_research"))
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2026-12-31")
    p.add_argument("--oos-start", default="2023-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--max-variants-per-family", type=int, default=36)
    p.add_argument("--top-n-per-instrument", type=int, default=DEFAULT_TOP_N_PER_INSTRUMENT)
    p.add_argument("--paper-days", type=int, default=15)
    p.add_argument("--mc-sims", type=int, default=2000)
    p.add_argument("--eval-days", type=int, default=60)
    p.add_argument("--mc-seed", type=int, default=42)
    args = p.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    out_dir = Path(args.reports_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    optimistic_exec = _mk_exec(OPTIMISTIC_EXECUTION)
    realistic_exec = _mk_exec(REALISTIC_EXECUTION)

    # Phase 1 baseline
    baseline_rows = []
    bars_oos: dict[str, pd.DataFrame] = {}
    for inst in INSTRUMENTS:
        _, bars = load_bars(inst, data_dir, args.oos_start, args.oos_end)
        bars_oos[inst] = bars
        baseline_cfg = get_config(inst)
        baseline_trades, baseline_score = _run_variant(
            inst,
            baseline_cfg,
            bars,
            contracts=1,
            execution=optimistic_exec,
        )
        baseline_rows.append(
            {
                "instrument": inst,
                "variant_id": f"{inst}_baseline_current",
                "family": "baseline_current",
                "session_mode": "current",
                **baseline_score,
            }
        )
        # data integrity companion
        pd.DataFrame({"bar_ts": bars.index}).to_csv(out_dir / f"{inst}_bars_coverage.csv", index=False)
        baseline_trades.to_csv(out_dir / f"{inst}_baseline_trades.csv", index=False)

    baseline_df = pd.DataFrame(baseline_rows)
    baseline_df.to_csv(out_dir / "baseline_metrics.csv", index=False)

    # Phase 2+3 sweeps
    sweep_rows: list[dict[str, Any]] = []
    candidate_cfgs: dict[str, FastConfig] = {}
    for inst in INSTRUMENTS:
        bars = bars_oos[inst]
        for family_name in FAMILY_SPECS:
            for session_mode in ("full_day", "after_1pm"):
                variants = _build_family_configs(
                    inst,
                    family_name,
                    session_mode,
                    args.max_variants_per_family,
                )
                for variant_id, cfg in variants:
                    trades, score = _run_variant(
                        inst,
                        cfg,
                        bars,
                        contracts=1,
                        execution=optimistic_exec,
                    )
                    row = {
                        "instrument": inst,
                        "variant_id": variant_id,
                        "family": family_name,
                        "session_mode": session_mode,
                        **score,
                    }
                    sweep_rows.append(row)
                    candidate_cfgs[variant_id] = cfg
                    if len(trades) > 0:
                        trades.head(10).to_csv(out_dir / "sample_trade_rows.csv", mode="a", index=False, header=not (out_dir / "sample_trade_rows.csv").exists())

    sweep_df = pd.DataFrame(sweep_rows).sort_values(["instrument", "score"], ascending=[True, False])
    sweep_df.to_csv(out_dir / "sweep_leaderboard.csv", index=False)

    # shortlist
    shortlist_parts = []
    for inst in INSTRUMENTS:
        shortlist_parts.append(sweep_df[sweep_df["instrument"] == inst].head(args.top_n_per_instrument))
    shortlist = pd.concat(shortlist_parts, ignore_index=True) if shortlist_parts else pd.DataFrame()
    shortlist.to_csv(out_dir / "shortlist.csv", index=False)

    # Phase 4 robustness
    robust_rows = []
    for _, row in shortlist.iterrows():
        inst = str(row["instrument"])
        vid = str(row["variant_id"])
        cfg = candidate_cfgs[vid]
        bars = bars_oos[inst]
        trades, score = _run_variant(inst, cfg, bars, contracts=1, execution=optimistic_exec)
        daily = _daily_pnl_from_scaled(trades)
        wf = _walk_forward_stability(daily)
        perturb = _perturb_and_score(inst, cfg, bars, contracts=1, execution=optimistic_exec)
        robust_score = 0.5 * wf + 0.5 * perturb
        robust_rows.append({**row.to_dict(), "walk_forward_score": wf, "perturb_score": perturb, "robustness_score": robust_score})
    robust_df = pd.DataFrame(robust_rows).sort_values("robustness_score", ascending=False)
    robust_df.to_csv(out_dir / "robustness_report.csv", index=False)

    # Phase 5 realism hardening + replay proxy
    realism_rows = []
    for _, row in robust_df.iterrows():
        inst = str(row["instrument"])
        vid = str(row["variant_id"])
        cfg = candidate_cfgs[vid]
        bars = bars_oos[inst]
        _, optimistic_sc = _run_variant(inst, cfg, bars, contracts=1, execution=optimistic_exec)
        _, realistic_sc = _run_variant(inst, cfg, bars, contracts=1, execution=realistic_exec)
        opt_pnl = float(optimistic_sc["total_pnl_usd"])
        real_pnl = float(realistic_sc["total_pnl_usd"])
        denom = abs(opt_pnl) if abs(opt_pnl) > 1e-9 else 1.0
        degradation = max(0.0, (opt_pnl - real_pnl) / denom)
        realism_rows.append(
            {
                **row.to_dict(),
                "optimistic_pnl_usd": opt_pnl,
                "realistic_pnl_usd": real_pnl,
                "realism_degradation": degradation,
            }
        )
    realism_df = pd.DataFrame(realism_rows).sort_values(["instrument", "realistic_pnl_usd"], ascending=[True, False])
    realism_df.to_csv(out_dir / "realism_hardening.csv", index=False)
    replay_file = _run_replay_smoke(data_dir, out_dir, args.oos_start, args.oos_end)

    # Phase 6 paper mode comparison vs current phoenix (baseline config proxy)
    paper_rows = []
    for inst in INSTRUMENTS:
        inst_rows = realism_df[realism_df["instrument"] == inst].head(2)
        base_cfg = get_config(inst)
        bars = bars_oos[inst]
        base_trades, base_sc = _run_variant(inst, base_cfg, bars, contracts=1, execution=realistic_exec)
        base_daily = _daily_pnl_from_scaled(base_trades)
        for _, row in inst_rows.iterrows():
            cfg = candidate_cfgs[str(row["variant_id"])]
            c_trades, c_sc = _run_variant(inst, cfg, bars, contracts=1, execution=realistic_exec)
            c_daily = _daily_pnl_from_scaled(c_trades)
            joined = pd.concat(
                [base_daily.rename("baseline"), c_daily.rename("candidate")],
                axis=1,
            ).fillna(0.0)
            joined = joined.tail(max(args.paper_days, 1))
            base_sum = float(joined["baseline"].sum()) if not joined.empty else 0.0
            cand_sum = float(joined["candidate"].sum()) if not joined.empty else 0.0
            paper_rows.append(
                {
                    "instrument": inst,
                    "variant_id": row["variant_id"],
                    "paper_days": int(len(joined)),
                    "baseline_pnl_usd": base_sum,
                    "candidate_pnl_usd": cand_sum,
                    "candidate_minus_baseline_usd": cand_sum - base_sum,
                    "baseline_pf": base_sc["profit_factor"],
                    "candidate_pf": c_sc["profit_factor"],
                }
            )
    paper_df = pd.DataFrame(paper_rows).sort_values("candidate_minus_baseline_usd", ascending=False)
    paper_df.to_csv(out_dir / "paper_shadow_comparison.csv", index=False)

    # Phase 7 capital allocation profiles
    alloc_rows = []
    top_for_alloc = realism_df.groupby("instrument", as_index=False).head(3)
    for profile in ("Balanced_50k_high", "Balanced_150k_high"):
        alloc_df = _allocation_assessment(top_for_alloc, profile)
        alloc_rows.append(alloc_df)
    allocation_df = pd.concat(alloc_rows, ignore_index=True) if alloc_rows else pd.DataFrame()
    allocation_df.to_csv(out_dir / "capital_allocation_rankings.csv", index=False)

    # Phase 8 go-live gates and checklist
    finalists = allocation_df.sort_values("alloc_score", ascending=False).groupby(["profile", "instrument"], as_index=False).head(1).copy()
    if finalists.empty:
        finalists = pd.DataFrame(columns=list(allocation_df.columns) + ["go_live_pass", "gate_fail_reasons"])
    pass_flags = []
    for _, row in finalists.iterrows():
        ok, reasons = _go_live_gate(row)
        pass_flags.append((ok, ",".join(reasons)))
    if pass_flags:
        finalists["go_live_pass"] = [x[0] for x in pass_flags]
        finalists["gate_fail_reasons"] = [x[1] for x in pass_flags]
    finalists.to_csv(out_dir / "finalists_with_gates.csv", index=False)
    _write_go_live_files(out_dir, finalists)

    # compact summary JSON
    summ = {
        "reports_dir": str(out_dir),
        "data_dir": str(data_dir),
        "baseline_rows": int(len(baseline_df)),
        "sweep_rows": int(len(sweep_df)),
        "shortlisted_rows": int(len(shortlist)),
        "robust_rows": int(len(robust_df)),
        "realism_rows": int(len(realism_df)),
        "paper_rows": int(len(paper_df)),
        "allocation_rows": int(len(allocation_df)),
        "finalists": int(len(finalists)),
        "replay_validation_summary": str(replay_file),
    }
    (out_dir / "pipeline_summary.json").write_text(json.dumps(summ, indent=2), encoding="utf-8")
    print(json.dumps(summ, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_telegram(main, script_name="run_strategy_research_plan"))
