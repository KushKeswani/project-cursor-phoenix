#!/usr/bin/env python3
"""Run a saved portfolio preset and write a combined backtest report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT))

from telegram_script_done import run_with_telegram

from backtester import (
    DLL,
    EOD_DD,
    EVAL_DAYS,
    INSTRUMENTS,
    bust_probability,
    daily_pnl,
    daily_sharpe,
    load_bars,
    max_drawdown,
    merged_scaled_trades,
    monthly_pnl,
    plot_daily_equity,
    plot_monthly_bars,
    profile_backtest_stats,
    raw_trades_frame,
    resolve_data_dir,
    scaled_trades,
    trade_metrics,
)
from configs.oos_defaults import DEFAULT_OOS_END, DEFAULT_OOS_START
from configs.portfolio_presets import PORTFOLIO_PRESETS, PRESET_DISPLAY_TITLES, PRESET_NOTES
from configs.strategy_configs import get_config
from configs.tick_config import TICK_SIZES
from engine.fast_engine import run_backtest
from evidence_utils import build_data_manifest, git_provenance, runtime_provenance
from strategy_analytics.risk_drawdown import compute_risk_metrics


def summarize_trades_frame(trades: pd.DataFrame, instrument: str, contracts: int) -> dict[str, float | int | str]:
    """Metrics from a scaled trades frame (same columns as `scaled_trades` output)."""
    if trades.empty:
        return {
            "instrument": instrument,
            "contracts": contracts,
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_usd": 0.0,
            "trade_sharpe": 0.0,
            "daily_sharpe": 0.0,
            "total_pnl_usd": 0.0,
            "max_drawdown_usd": 0.0,
            "best_month_usd": 0.0,
            "worst_month_usd": 0.0,
            "positive_month_pct": 0.0,
            "worst_trade_usd": 0.0,
            "worst_day_usd": 0.0,
            "max_loss_streak_trades": 0,
            "max_loss_streak_days": 0,
            "max_drawdown_pct": 0.0,
        }
    t = trades.sort_values("exit_ts", kind="mergesort").reset_index(drop=True)
    pnls = t["pnl_usd"].to_numpy(dtype=float)
    metrics = trade_metrics(pnls)
    daily = daily_pnl(t)
    monthly = monthly_pnl(t)
    equity = daily.cumsum() if not daily.empty else pd.Series(dtype=float)
    risk = compute_risk_metrics(
        daily,
        equity,
        trades=t[["pnl_usd"]].rename(columns={"pnl_usd": "pnl"}),
    )
    worst_trade = float(t["pnl_usd"].min()) if not t.empty else 0.0
    return {
        "instrument": instrument,
        "contracts": contracts,
        "trades": int(metrics["n_trades"]),
        "win_rate": float(metrics["win_rate"]),
        "profit_factor": float(metrics["profit_factor"]),
        "expectancy_usd": float(metrics["expectancy"]),
        "trade_sharpe": float(metrics["sharpe"]),
        "daily_sharpe": float(daily_sharpe(daily, 0.0)),
        "total_pnl_usd": float(t["pnl_usd"].sum()),
        "max_drawdown_usd": float(max_drawdown(daily.cumsum())) if not daily.empty else 0.0,
        "best_month_usd": float(monthly.max()) if not monthly.empty else 0.0,
        "worst_month_usd": float(monthly.min()) if not monthly.empty else 0.0,
        "positive_month_pct": float((monthly > 0).mean() * 100.0) if not monthly.empty else 0.0,
        "worst_trade_usd": worst_trade,
        "worst_day_usd": float(risk["worst_day"]),
        "max_loss_streak_trades": int(risk["max_consecutive_losses"]),
        "max_loss_streak_days": int(risk["max_consecutive_loss_days"]),
        "max_drawdown_pct": float(risk["max_drawdown_percent"]),
    }


def summarize_instrument_scope(raw_trades: pd.DataFrame, instrument: str, contracts: int) -> dict[str, float | int | str]:
    trades = scaled_trades(raw_trades, instrument, contracts)
    return summarize_trades_frame(trades, instrument, contracts)


def summarize_portfolio_scope(
    stats: dict[str, object],
    period: str,
    *,
    merged_trades: pd.DataFrame,
) -> dict[str, float | int | str]:
    daily = stats[f"{period}_daily"]
    monthly = stats[f"{period}_monthly"]
    trade_stats = stats[f"{period}_trade_metrics"]
    row: dict[str, float | int | str] = {
        "period": period.upper(),
        "total_pnl_usd": float(stats[f"{period}_total_pnl"]),
        "avg_monthly_usd": float(stats[f"{period}_monthly_avg"]),
        "max_drawdown_usd": float(stats[f"{period}_max_dd"]),
        "trades": int(trade_stats["n_trades"]),
        "win_rate": float(trade_stats["win_rate"]),
        "profit_factor": float(trade_stats["profit_factor"]),
        "expectancy_usd": float(trade_stats["expectancy"]),
        "trade_sharpe": float(trade_stats["sharpe"]),
        "daily_sharpe": float(daily_sharpe(daily, 0.0)),
        "best_month_usd": float(monthly.max()) if not monthly.empty else 0.0,
        "worst_month_usd": float(monthly.min()) if not monthly.empty else 0.0,
        "positive_month_pct": float((monthly > 0).mean() * 100.0) if not monthly.empty else 0.0,
        "median_month_usd": float(monthly.median()) if not monthly.empty else 0.0,
        "worst_trade_usd": 0.0,
        "worst_day_usd": 0.0,
        "max_loss_streak_trades": 0,
        "max_loss_streak_days": 0,
        "max_drawdown_pct": 0.0,
        "max_dd_duration_days": 0,
    }
    if daily.empty:
        return row
    equity = daily.cumsum()
    tdf = None
    if not merged_trades.empty and "pnl_usd" in merged_trades.columns:
        tdf = merged_trades[["pnl_usd"]].rename(columns={"pnl_usd": "pnl"})
        row["worst_trade_usd"] = float(merged_trades["pnl_usd"].min())
    risk = compute_risk_metrics(daily, equity, trades=tdf)
    durs = risk["drawdown_durations"]
    row["worst_day_usd"] = float(risk["worst_day"])
    row["max_loss_streak_trades"] = int(risk["max_consecutive_losses"])
    row["max_loss_streak_days"] = int(risk["max_consecutive_loss_days"])
    row["max_drawdown_pct"] = float(risk["max_drawdown_percent"])
    row["max_dd_duration_days"] = int(max(durs)) if durs else 0
    return row


def summarize_risk_scope(
    daily: pd.Series,
    *,
    mc_sims: int,
    eval_days: int,
    mc_seed: int,
    eod_dd: float,
    dll: float,
) -> dict[str, float]:
    mc = bust_probability(
        daily,
        n_sims=mc_sims,
        eval_days=eval_days,
        eod_dd=eod_dd,
        dll=dll,
        seed=mc_seed,
    )
    return {
        "bust_pct": float(mc["bust_pct"]),
        "p10": float(mc["p10"]),
        "p25": float(mc["p25"]),
        "p50": float(mc["p50"]),
        "p75": float(mc["p75"]),
        "p90": float(mc["p90"]),
        "avg_monthly": float(mc["avg_monthly"]),
        "reach_7k_pct": float(mc["reach_7k_pct"]),
    }


def write_report(
    out_path: Path,
    *,
    profile_name: str,
    contracts: dict[str, int],
    note: str | None,
    data_dir: Path,
    full_start: str,
    full_end: str,
    oos_start: str,
    oos_end: str,
    combined_rows: list[dict[str, float | int | str]],
    risk_rows: list[dict[str, float | int | str]],
    instrument_rows: list[dict[str, float | int | str]],
    equity_chart: Path,
    monthly_chart: Path,
    eod_dd: float,
    dll: float,
    eval_days: int,
    daily_profit_lock: float | None,
    daily_loss_lock: float | None,
    lockout_note_full: str | None,
    lockout_note_oos: str | None,
) -> None:
    lines = [
        f"# {profile_name} Portfolio Backtest",
        "",
        "## Profile",
        "",
        f"- Data dir: `{data_dir}`",
        f"- Contracts: CL {contracts['CL']}, MGC {contracts['MGC']}, MNQ {contracts['MNQ']}, YM {contracts['YM']}",
        f"- Full window: {full_start} to {full_end}",
        f"- OOS window: {oos_start} to {oos_end}",
        f"- Execution model: zero-slippage stop-trigger baseline",
        f"- EOD trailing DD (MC): ${eod_dd:,.0f}",
        f"- DLL (MC): ${dll:,.0f}",
        f"- Monte Carlo eval length: {eval_days} trading days",
    ]
    if daily_profit_lock is not None:
        lines.append(f"- Daily profit lockout: stop further trades same day after +${daily_profit_lock:,.0f} realized")
    if daily_loss_lock is not None:
        lines.append(f"- Daily loss lockout: stop further trades same day after −${daily_loss_lock:,.0f} realized")
    if lockout_note_full:
        lines.append(f"- Lockout stats FULL: {lockout_note_full}")
    if lockout_note_oos:
        lines.append(f"- Lockout stats OOS: {lockout_note_oos}")
    if note:
        lines.append(f"- Note: {note}")

    lines.extend(
        [
            "",
            "## Combined Portfolio",
            "",
            "| Period | Total PnL | Avg Monthly | Max DD | Trades | WR | PF | Expectancy | Trade Sharpe | Daily Sharpe | Best Month | Worst Month | Positive Months |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in combined_rows:
        lines.append(
            f"| {row['period']} | ${row['total_pnl_usd']:,.2f} | ${row['avg_monthly_usd']:,.2f} | ${row['max_drawdown_usd']:,.2f} | "
            f"{int(row['trades'])} | {row['win_rate']:.2f}% | {row['profit_factor']:.2f} | ${row['expectancy_usd']:,.2f} | "
            f"{row['trade_sharpe']:.2f} | {row['daily_sharpe']:.2f} | ${row['best_month_usd']:,.2f} | "
            f"${row['worst_month_usd']:,.2f} | {row['positive_month_pct']:.1f}% |"
        )

    lines.extend(
        [
            "",
            "## goals.md §3 — Drawdown, streaks, tails",
            "",
            "| Period | Max DD $ | Max DD % | Max DD dur (d) | Worst day | Worst trade | "
            "Max loss streak (trades) | Max loss streak (days) | Median month |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in combined_rows:
        lines.append(
            f"| {row['period']} | ${row['max_drawdown_usd']:,.2f} | {row['max_drawdown_pct']:.2f}% | "
            f"{int(row['max_dd_duration_days'])} | ${row['worst_day_usd']:,.2f} | ${row['worst_trade_usd']:,.2f} | "
            f"{int(row['max_loss_streak_trades'])} | {int(row['max_loss_streak_days'])} | "
            f"${row['median_month_usd']:,.2f} |"
        )

    lines.extend(
        [
            "",
            "## Monte Carlo Risk",
            "",
            "| Period | Bust % | P10 | P25 | P50 | P75 | P90 | Avg/mo | Reach $7K % |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in risk_rows:
        lines.append(
            f"| {row['period']} | {row['bust_pct']:.2f}% | ${row['p10']:,.0f} | ${row['p25']:,.0f} | ${row['p50']:,.0f} | "
            f"${row['p75']:,.0f} | ${row['p90']:,.0f} | ${row['avg_monthly']:,.0f} | {row['reach_7k_pct']:.1f}% |"
        )

    lines.extend(
        [
            "",
            "## Instrument Breakdown",
            "",
            "| Period | Instrument | Contracts | Trades | WR | PF | Total PnL | Expectancy | Trade Sharpe | Daily Sharpe | "
            "Max DD | Worst trade | Mx L streak | Best Month | Worst Month | Pos mo % |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in instrument_rows:
        lines.append(
            f"| {row['period']} | {row['instrument']} | {int(row['contracts'])} | {int(row['trades'])} | {row['win_rate']:.2f}% | "
            f"{row['profit_factor']:.2f} | ${row['total_pnl_usd']:,.2f} | ${row['expectancy_usd']:,.2f} | "
            f"{row['trade_sharpe']:.2f} | {row['daily_sharpe']:.2f} | ${row['max_drawdown_usd']:,.2f} | "
            f"${row['worst_trade_usd']:,.2f} | {int(row['max_loss_streak_trades'])} | "
            f"${row['best_month_usd']:,.2f} | ${row['worst_month_usd']:,.2f} | {row['positive_month_pct']:.1f}% |"
        )

    lines.extend(
        [
            "",
            "## Visuals",
            "",
            f"- Equity curve: `{equity_chart}`",
            f"- Monthly PnL: `{monthly_chart}`",
        ]
    )

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="Balanced_150k_high")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--reports-dir", default=str(SCRIPT_DIR.parent / "reports"))
    parser.add_argument("--full-start", default="2020-01-01")
    parser.add_argument("--full-end", default="2026-12-31")
    parser.add_argument("--oos-start", default=DEFAULT_OOS_START)
    parser.add_argument("--oos-end", default=DEFAULT_OOS_END)
    parser.add_argument("--mc-sims", type=int, default=5000)
    parser.add_argument("--eval-days", type=int, default=EVAL_DAYS)
    parser.add_argument("--mc-seed", type=int, default=42)
    parser.add_argument(
        "--eod-dd",
        type=float,
        default=None,
        help=f"Monte Carlo trailing drawdown limit (default: {EOD_DD:g} from backtester)",
    )
    parser.add_argument(
        "--dll",
        type=float,
        dest="dll_mc",
        default=None,
        help=f"Monte Carlo daily loss limit (default: {DLL:g} from backtester)",
    )
    parser.add_argument(
        "--daily-profit-lock",
        type=float,
        default=None,
        help="Portfolio: after +$X realized in a calendar day (exit_ts order), drop later trades that day",
    )
    parser.add_argument(
        "--daily-loss-lock",
        type=float,
        default=None,
        help="Portfolio: after -$X realized in a day, drop later trades that day",
    )
    args = parser.parse_args()
    eod_dd = float(EOD_DD if args.eod_dd is None else args.eod_dd)
    dll_mc = float(DLL if args.dll_mc is None else args.dll_mc)

    if args.profile not in PORTFOLIO_PRESETS:
        valid = ", ".join(sorted(PORTFOLIO_PRESETS))
        raise SystemExit(f"Unknown profile '{args.profile}'. Valid presets: {valid}")

    profile_name = args.profile
    contracts = {instrument: int(PORTFOLIO_PRESETS[profile_name][instrument]) for instrument in INSTRUMENTS}
    note = PRESET_NOTES.get(profile_name)
    display_title = PRESET_DISPLAY_TITLES.get(
        profile_name, profile_name.replace("_", " ").title()
    )
    data_dir = resolve_data_dir(args.data_dir)
    reports_dir = Path(args.reports_dir).expanduser().resolve()
    visuals_dir = reports_dir / "visuals" / "portfolio_risk_profiles"
    visuals_dir.mkdir(parents=True, exist_ok=True)

    raw_full_by_inst: dict[str, pd.DataFrame] = {}
    raw_oos_by_inst: dict[str, pd.DataFrame] = {}

    for instrument in INSTRUMENTS:
        _, bars_full = load_bars(instrument, data_dir, args.full_start, args.full_end)
        _, bars_oos = load_bars(instrument, data_dir, args.oos_start, args.oos_end)
        cfg = get_config(instrument)
        raw_full_by_inst[instrument] = raw_trades_frame(
            run_backtest(cfg, bars_full, TICK_SIZES[instrument], return_trades=True)
        )
        raw_oos_by_inst[instrument] = raw_trades_frame(
            run_backtest(cfg, bars_oos, TICK_SIZES[instrument], return_trades=True)
        )

    stats = profile_backtest_stats(
        raw_full_by_inst,
        raw_oos_by_inst,
        contracts,
        daily_profit_lock_usd=args.daily_profit_lock,
        daily_loss_lock_usd=args.daily_loss_lock,
    )
    merged_full_eff = stats.get("merged_full_filtered")
    merged_oos_eff = stats.get("merged_oos_filtered")
    merged_full_base = merged_scaled_trades(raw_full_by_inst, contracts)
    merged_oos_base = merged_scaled_trades(raw_oos_by_inst, contracts)
    if merged_full_eff is None:
        merged_full_eff = merged_full_base
    if merged_oos_eff is None:
        merged_oos_eff = merged_oos_base
    combined_rows = [
        summarize_portfolio_scope(stats, "full", merged_trades=merged_full_eff),
        summarize_portfolio_scope(stats, "oos", merged_trades=merged_oos_eff),
    ]
    risk_rows = [
        {
            "period": "FULL",
            **summarize_risk_scope(
                stats["full_daily"],
                mc_sims=args.mc_sims,
                eval_days=args.eval_days,
                mc_seed=args.mc_seed,
                eod_dd=eod_dd,
                dll=dll_mc,
            ),
        },
        {
            "period": "OOS",
            **summarize_risk_scope(
                stats["oos_daily"],
                mc_sims=args.mc_sims,
                eval_days=args.eval_days,
                mc_seed=args.mc_seed,
                eod_dd=eod_dd,
                dll=dll_mc,
            ),
        },
    ]

    def _lock_note(d: object) -> str | None:
        if not isinstance(d, dict) or not d:
            return None
        return (
            f"kept={int(d.get('n_trades_kept', 0))}, dropped={int(d.get('n_trades_dropped', 0))}, "
            f"profit_lock_days={int(d.get('days_profit_locked', 0))}, loss_lock_days={int(d.get('days_loss_locked', 0))}"
        )

    lock_nf = _lock_note(stats.get("lockout_stats_full"))
    lock_no = _lock_note(stats.get("lockout_stats_oos"))

    instrument_rows: list[dict[str, float | int | str]] = []
    for period_name, raw_map, merged_f in [
        ("FULL", raw_full_by_inst, merged_full_eff),
        ("OOS", raw_oos_by_inst, merged_oos_eff),
    ]:
        for instrument in INSTRUMENTS:
            if merged_f is not None and isinstance(merged_f, pd.DataFrame) and not merged_f.empty:
                sub = merged_f[merged_f["instrument"] == instrument]
                instrument_rows.append(
                    {
                        "period": period_name,
                        **summarize_trades_frame(sub, instrument, contracts[instrument]),
                    }
                )
            else:
                instrument_rows.append(
                    {
                        "period": period_name,
                        **summarize_instrument_scope(raw_map[instrument], instrument, contracts[instrument]),
                    }
                )

    slug = profile_name.lower().replace(" ", "_")
    equity_chart = visuals_dir / f"{slug}_combined_equity_curve.png"
    monthly_chart = visuals_dir / f"{slug}_combined_monthly_pnl.png"
    plot_daily_equity(stats["full_daily"], f"{display_title} — Equity Curve", equity_chart)
    plot_monthly_bars(stats["full_monthly"], f"{display_title} — Monthly PnL", monthly_chart)

    combined_csv = reports_dir / f"{slug}_backtest_summary.csv"
    instrument_csv = reports_dir / f"{slug}_instrument_breakdown.csv"
    report_md = reports_dir / f"{slug.upper()}_BACKTEST_REPORT.md"

    pd.DataFrame(combined_rows).to_csv(combined_csv, index=False)
    pd.DataFrame(instrument_rows).to_csv(instrument_csv, index=False)
    write_report(
        report_md,
        profile_name=display_title,
        contracts=contracts,
        note=note,
        data_dir=data_dir,
        full_start=args.full_start,
        full_end=args.full_end,
        oos_start=args.oos_start,
        oos_end=args.oos_end,
        combined_rows=combined_rows,
        risk_rows=risk_rows,
        instrument_rows=instrument_rows,
        equity_chart=equity_chart,
        monthly_chart=monthly_chart,
        eod_dd=eod_dd,
        dll=dll_mc,
        eval_days=args.eval_days,
        daily_profit_lock=args.daily_profit_lock,
        daily_loss_lock=args.daily_loss_lock,
        lockout_note_full=lock_nf,
        lockout_note_oos=lock_no,
    )

    print(f"Saved: {combined_csv}")
    print(f"Saved: {instrument_csv}")
    print(f"Saved: {report_md}")
    print(f"Saved: {equity_chart}")
    print(f"Saved: {monthly_chart}")

    data_files: list[Path] = []
    for inst in INSTRUMENTS:
        p = data_dir / f"{inst}.parquet"
        if p.exists():
            data_files.append(p)
    data_manifest = build_data_manifest(data_files)
    (reports_dir / f"{slug}_data_manifest.json").write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "profile": profile_name,
                "full_window": {"start": args.full_start, "end": args.full_end},
                "oos_window": {"start": args.oos_start, "end": args.oos_end},
                "data_dir": str(data_dir),
                **data_manifest,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    run_meta = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_portfolio_preset.py",
        "profile": profile_name,
        "display_title": display_title,
        "args": vars(args),
        "contracts": contracts,
        "report_paths": {
            "summary_csv": str(combined_csv),
            "instrument_csv": str(instrument_csv),
            "markdown_report": str(report_md),
            "equity_chart": str(equity_chart),
            "monthly_chart": str(monthly_chart),
            "data_manifest": str(reports_dir / f"{slug}_data_manifest.json"),
        },
        "provenance": {
            **git_provenance(REPO_ROOT),
            **runtime_provenance(),
        },
    }
    (reports_dir / f"{slug}_run_meta.json").write_text(
        json.dumps(run_meta, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Saved: {reports_dir / f'{slug}_run_meta.json'}")
    print(f"Saved: {reports_dir / f'{slug}_data_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_telegram(main, script_name="run_portfolio_preset"))
