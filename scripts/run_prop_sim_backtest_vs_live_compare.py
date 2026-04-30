#!/usr/bin/env python3
"""
Export OOS trade_executions from (1) regular backtests for all four portfolio presets and
(2) existing live-replay trade CSVs; run prop_farming_calculator CLI on each; write a
comparison table (prop-firm KPIs: rolling eval pass %, horizon pass %, net/ROI).

Execution roots look like::
    <base>/<source>/<slug>/trade_executions/oos/instruments/<INST>_trade_executions.csv

Prop sim outputs go to::
    <base>/runs/<source>_<slug>/
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from telegram_script_done import run_with_telegram

from backtester import INSTRUMENTS, load_bars, raw_trades_frame, resolve_data_dir
from configs.oos_defaults import DEFAULT_OOS_END, DEFAULT_OOS_START
from configs.portfolio_presets import PORTFOLIO_PRESETS
from configs.strategy_configs import get_config
from configs.tick_config import TICK_SIZES, TICK_VALUES
from engine.fast_engine import run_backtest

ET = ZoneInfo("America/New_York")

# (preset_key, CLI --portfolio, --firm-preset for Topstep-style rules)
PRESET_RUNS: list[tuple[str, str, str]] = [
    ("Balanced_50k_survival", "50k-survival", "phoenix_topstep_50k"),
    ("Balanced_50k_high", "50k-high", "phoenix_topstep_50k"),
    ("Balanced_150k_survival", "150k-survival", "phoenix_topstep_150k"),
    ("Balanced_150k_high", "150k-high", "phoenix_topstep_150k"),
]

EXPORT_COLS = ["entry_ts", "exit_ts", "direction", "pnl_ticks"]


def _preset_slug(name: str) -> str:
    return name.lower()


def _write_instrument_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        pd.DataFrame(columns=EXPORT_COLS).to_csv(path, index=False)
        return
    out = df[[c for c in EXPORT_COLS if c in df.columns]].copy()
    for col in ("entry_ts", "exit_ts"):
        if col in out.columns:
            t = pd.to_datetime(out[col], utc=True)
            out[col] = t.dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    out.to_csv(path, index=False)


def export_backtest_oos(
    *,
    base: Path,
    data_dir: Path,
    oos_start: str,
    oos_end: str,
) -> None:
    for preset_key, _, _ in PRESET_RUNS:
        contracts = PORTFOLIO_PRESETS[preset_key]
        raw_oos_by_inst: dict[str, pd.DataFrame] = {}
        for instrument in INSTRUMENTS:
            _, bars_oos = load_bars(instrument, data_dir, oos_start, oos_end)
            cfg = get_config(instrument)
            raw_oos_by_inst[instrument] = raw_trades_frame(
                run_backtest(cfg, bars_oos, TICK_SIZES[instrument], return_trades=True)
            )

        root = base / "backtest" / _preset_slug(preset_key)
        inst_dir = root / "trade_executions" / "oos" / "instruments"
        for instrument in INSTRUMENTS:
            raw = raw_oos_by_inst[instrument]
            if contracts.get(instrument, 0) == 0:
                _write_instrument_csv(inst_dir / f"{instrument}_trade_executions.csv", pd.DataFrame())
                continue
            _write_instrument_csv(inst_dir / f"{instrument}_trade_executions.csv", raw)


def live_replay_csv_to_executions(
    csv_path: Path,
    preset_key: str,
    out_root: Path,
) -> None:
    """Convert *_live_replay_trades.csv (ET-naive timestamps) to loader-ready CSVs."""
    contracts = PORTFOLIO_PRESETS[preset_key]
    df = pd.read_csv(csv_path)
    if df.empty:
        for instrument in INSTRUMENTS:
            _write_instrument_csv(
                out_root / "trade_executions" / "oos" / "instruments" / f"{instrument}_trade_executions.csv",
                pd.DataFrame(),
            )
        return

    if "entry_ts_et" in df.columns:
        ent = pd.to_datetime(df["entry_ts_et"])
        exi = pd.to_datetime(df["exit_ts_et"])
        if ent.dt.tz is None:
            ent = ent.dt.tz_localize(ET, ambiguous="infer", nonexistent="shift_forward")
        else:
            ent = ent.dt.tz_convert(ET)
        if exi.dt.tz is None:
            exi = exi.dt.tz_localize(ET, ambiguous="infer", nonexistent="shift_forward")
        else:
            exi = exi.dt.tz_convert(ET)
        df = df.copy()
        df["entry_ts"] = ent.dt.tz_convert(timezone.utc)
        df["exit_ts"] = exi.dt.tz_convert(timezone.utc)
    elif "entry_ts" in df.columns:
        df = df.copy()
        df["entry_ts"] = pd.to_datetime(df["entry_ts"], utc=True)
        df["exit_ts"] = pd.to_datetime(df["exit_ts"], utc=True)
    else:
        raise ValueError(f"{csv_path}: need entry_ts_et/exit_ts_et or entry_ts/exit_ts")

    df["direction"] = df.get("direction", "flat")
    preset_c = {i: int(contracts[i]) for i in INSTRUMENTS}
    df["instrument"] = df["instrument"].astype(str)
    df = df[df["instrument"].map(lambda i: preset_c.get(i, 0) > 0)].copy()

    def ticks_row(row: pd.Series) -> float:
        inst = str(row["instrument"])
        tick = float(TICK_VALUES[inst])
        c = int(preset_c[inst])
        usd = float(row["pnl_usd"])
        return usd / (tick * c)

    df["pnl_ticks"] = df.apply(ticks_row, axis=1)

    inst_dir = out_root / "trade_executions" / "oos" / "instruments"
    for instrument in INSTRUMENTS:
        sub = df[df["instrument"] == instrument]
        if preset_c[instrument] == 0:
            _write_instrument_csv(inst_dir / f"{instrument}_trade_executions.csv", pd.DataFrame())
        else:
            _write_instrument_csv(inst_dir / f"{instrument}_trade_executions.csv", sub)


def export_live_replay_folder(*, base: Path, live_dir: Path) -> None:
    live_dir = live_dir.expanduser().resolve()
    for preset_key, _, _ in PRESET_RUNS:
        name = f"{preset_key}_live_replay_trades.csv"
        path = live_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Missing live replay CSV: {path}")
        out_root = base / "live_replay" / _preset_slug(preset_key)
        live_replay_csv_to_executions(path, preset_key, out_root)


def run_prop_cli(
    *,
    python: str,
    exec_root: Path,
    out_dir: Path,
    firm_name: str,
    portfolio: str,
    firm_preset: str,
    n_sims: int,
    cohort_horizon: str,
) -> None:
    cli = REPO_ROOT / "prop_farming_calculator" / "cli.py"
    cmd = [
        python,
        str(cli),
        "--firm-name",
        firm_name,
        "--execution-reports-dir",
        str(exec_root.resolve()),
        "--scope",
        "oos",
        "--portfolio",
        portfolio,
        "--firm-preset",
        firm_preset,
        "--n-sims",
        str(n_sims),
        "--out",
        str(out_dir.resolve()),
        "--cohort-horizon",
        cohort_horizon,
    ]
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))


def _pool_trading_days_from_summary(run_dir: Path) -> str:
    sm = run_dir / "SUMMARY.md"
    if not sm.exists():
        return ""
    text = sm.read_text(encoding="utf-8")
    m = re.search(r"Trading days:\s*\*\*(\d+)\*\*", text)
    return m.group(1) if m else ""


def _read_compare_row(run_dir: Path, *, cohort_horizon: str) -> dict[str, float | str]:
    meta_path = run_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    hs = run_dir / "horizons_summary.csv"
    pool = run_dir / "pool_diagnostics.csv"
    row: dict[str, float | str] = {
        "firm_name": str(meta.get("firm_name", "")),
        "portfolio_tier": str(meta.get("portfolio_tier", "")),
        "n_days": "",
        "rolling_pass_pct": "",
        "h_label": cohort_horizon,
        "audition_pass_pct": "",
        "avg_net_per_trader": "",
        "pct_positive_roi": "",
        "avg_roi_pct": "",
    }
    if pool.exists():
        ps = pd.read_csv(pool, header=None)
        if len(ps.columns) >= 2:
            m = dict(zip(ps.iloc[:, 0].astype(str), ps.iloc[:, 1].astype(float)))
            row["rolling_pass_pct"] = float(
                m.get("mc_eval_pass_pct", m.get("roll_rolling_pass_pct", 0.0))
            )
    if hs.exists():
        hdf = pd.read_csv(hs)
        if not hdf.empty and "horizon_label" in hdf.columns:
            sub = hdf[hdf["horizon_label"].astype(str) == str(cohort_horizon)]
            if sub.empty and len(hdf):
                sub = hdf[hdf["horizon_label"].astype(str).str.contains("6 Month", na=False)]
            if sub.empty and len(hdf):
                sub = hdf.iloc[[0]]
            if len(sub):
                r = sub.iloc[0]
                row["h_label"] = str(r.get("horizon_label", ""))
                row["audition_pass_pct"] = float(r.get("audition_pass_pct", 0.0))
                row["avg_net_per_trader"] = float(r.get("avg_net_profit_per_trader", 0.0))
                row["pct_positive_roi"] = float(r.get("pct_positive_roi", 0.0))
                row["avg_roi_pct"] = float(r.get("avg_roi_pct", 0.0))
    row["n_days"] = _pool_trading_days_from_summary(run_dir)
    return row


FUNNEL_HORIZON_ORDER: list[str] = [
    "1 Week",
    "1 Month",
    "1 Quarter",
    "6 Months",
    "12 Months",
    "18 Months",
    "24 Months",
]


def _read_funnel_by_horizon(run_dir: Path) -> dict[str, dict[str, float]]:
    p = run_dir / "funnel_by_horizon.csv"
    if not p.is_file():
        return {}
    df = pd.read_csv(p)
    if df.empty or "horizon_label" not in df.columns:
        return {}
    out: dict[str, dict[str, float]] = {}
    for hl, g in df.groupby("horizon_label"):
        out[str(hl)] = dict(
            zip(g["bucket_key"].astype(str), g["pct_of_simulations"].astype(float))
        )
    return out


def _fmt_funnel_pct(x: float) -> str:
    return f"{float(x):.2f}%"


def _funded_funnel_subsection(source: str, preset: str, run_dir: Path) -> list[str]:
    data = _read_funnel_by_horizon(run_dir)
    title = f"{source} — {preset}"
    if not data:
        return [f"#### {title}", "", "*Missing or empty `funnel_by_horizon.csv` — re-run sims.*", ""]
    lines = [
        f"#### {title}",
        "",
        "| Horizon | % funded fail: before 1st payout | % after ≥1 payout | % zero-payout edge | **% any funded fail** | % survived funded | % insufficient history (eval) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for hl in FUNNEL_HORIZON_ORDER:
        d = data.get(hl)
        if not d:
            continue
        b1 = float(d.get("funded_breach_before_first_payout", 0.0))
        b2 = float(d.get("funded_breach_after_payouts", 0.0))
        b0 = float(d.get("funded_breach_zero_payouts", 0.0))
        any_br = b1 + b2 + b0
        surv = float(d.get("funded_survived_segment", 0.0))
        ins = float(d.get("eval_insufficient_history", 0.0))
        lines.append(
            f"| {hl} | {_fmt_funnel_pct(b1)} | {_fmt_funnel_pct(b2)} | {_fmt_funnel_pct(b0)} | "
            f"{_fmt_funnel_pct(any_br)} | {_fmt_funnel_pct(surv)} | {_fmt_funnel_pct(ins)} |"
        )
    lines.append("")
    return lines


def write_comparison_md(base: Path, cohort_horizon: str) -> None:
    runs_dir = base / "runs"
    rows: list[dict[str, object]] = []
    for source in ("backtest", "live_replay"):
        for preset_key, portfolio, _ in PRESET_RUNS:
            slug = _preset_slug(preset_key)
            tag = f"{source}_{slug}"
            rd = runs_dir / tag
            if not rd.is_dir():
                continue
            r = _read_compare_row(rd, cohort_horizon=cohort_horizon)
            r["source"] = source
            r["preset"] = preset_key
            rows.append(r)

    lines = [
        "# Prop firm sim: backtest OOS vs live replay",
        "",
        f"Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`",
        "",
        f"Cohort horizon label for summary table: **{cohort_horizon}** (match `horizons_summary.csv` row). "
        f"Backtest OOS exports default to **`{DEFAULT_OOS_START}` → `{DEFAULT_OOS_END}`** "
        "(override with `--oos-start` / `--oos-end`). Re-run this script **without** `--skip-export-backtest` "
        "to refresh `trade_executions` and grow **pool days** when new bar data exists.",
        "",
        "| Source | Preset | Pool days | Rolling eval pass % | Horizon | Audition pass % | Avg net $/trader | % positive ROI | Avg ROI % |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    def _fmt_pct(v: object) -> str:
        if v == "" or v is None:
            return "—"
        return f"{float(v):.2f}%"

    def _fmt_money(v: object) -> str:
        if v == "" or v is None:
            return "—"
        return f"{float(v):,.2f}"

    def _fmt_float(v: object) -> str:
        if v == "" or v is None:
            return "—"
        return f"{float(v):.2f}"

    for r in sorted(rows, key=lambda x: (x["preset"], x["source"])):
        lines.append(
            f"| {r['source']} | {r['preset']} | {r['n_days'] or '—'} | "
            f"{_fmt_pct(r['rolling_pass_pct'])} | "
            f"{r.get('h_label', '—')} | "
            f"{_fmt_pct(r['audition_pass_pct'])} | "
            f"{_fmt_money(r['avg_net_per_trader'])} | "
            f"{_fmt_pct(r['pct_positive_roi'])} | "
            f"{_fmt_float(r['avg_roi_pct'])} |"
        )
    lines.extend(
        [
            "",
            "**Note:** Backtest rows use the OOS window from `--oos-start` / `--oos-end` (see each run’s `SUMMARY.md`). "
            "Live replay rows use whatever calendar span is in `reports/live_replay_by_profile/*_live_replay_trades.csv` "
            "— pool days often differ, so compare pass rates and ROI as distributions on each pool, not as identical samples.",
            "",
            "## Funded outcomes by horizon",
            "",
            "Monte Carlo **single-lifecycle** end states from `funnel_by_horizon.csv` (same runs as above). "
            "**Any funded fail** sums the three funded breach buckets. **Insufficient history** means the daily pool was "
            "shorter than the eval window (no funded leg). Horizons: **week → month → quarter → 6m → year (12m) → 18m → 24m**.",
            "",
        ]
    )

    for source in ("backtest", "live_replay"):
        for preset_key, _, _ in PRESET_RUNS:
            slug = _preset_slug(preset_key)
            rd = runs_dir / f"{source}_{slug}"
            if not rd.is_dir():
                continue
            lines.extend(_funded_funnel_subsection(source, preset_key, rd))

    lines.extend(
        [
            "## Run directories",
            "",
            f"Exports: `{base / 'backtest'}`, `{base / 'live_replay'}`.",
            f"Sim outputs: `{runs_dir}/<source>_<preset_slug>/`.",
            f"Regenerate everything: `python3 scripts/run_prop_sim_backtest_vs_live_compare.py` "
            f"(add `--skip-export-live` if live CSVs unchanged).",
        ]
    )
    out_md = base / "COMPARE_PROP_SIM.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, default=REPO_ROOT / "reports" / "prop_sim_compare")
    p.add_argument("--data-dir", type=Path, default=None, help="Parquet root (default: Data-DataBento)")
    p.add_argument("--oos-start", default=DEFAULT_OOS_START)
    p.add_argument("--oos-end", default=DEFAULT_OOS_END)
    p.add_argument(
        "--live-dir",
        type=Path,
        default=REPO_ROOT / "reports" / "live_replay_by_profile",
    )
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--n-sims", type=int, default=1500)
    p.add_argument("--cohort-horizon", default="6 Months")
    p.add_argument("--skip-export-backtest", action="store_true")
    p.add_argument("--skip-export-live", action="store_true")
    p.add_argument(
        "--skip-live-replay-path",
        action="store_true",
        help="Skip live replay CSV export and prop MC for live_replay (use until reports/live_replay_by_profile trades exist).",
    )
    p.add_argument("--skip-sims", action="store_true")
    args = p.parse_args()

    base = args.base.expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)

    if not args.skip_export_backtest:
        data_dir = resolve_data_dir(str(args.data_dir) if args.data_dir else None)
        export_backtest_oos(
            base=base,
            data_dir=data_dir,
            oos_start=args.oos_start,
            oos_end=args.oos_end,
        )
        print(f"Wrote backtest execution exports under {base / 'backtest'}", flush=True)

    if not args.skip_export_live and not args.skip_live_replay_path:
        export_live_replay_folder(base=base, live_dir=args.live_dir)
        print(f"Wrote live replay execution exports under {base / 'live_replay'}", flush=True)

    if not args.skip_sims:
        runs = base / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        sources = ("backtest", "live_replay")
        for source in sources:
            if source == "live_replay" and args.skip_live_replay_path:
                continue
            for preset_key, portfolio, firm_preset in PRESET_RUNS:
                slug = _preset_slug(preset_key)
                exec_root = base / source / slug
                out_dir = runs / f"{source}_{slug}"
                firm_name = f"compare_{source}_{preset_key}"
                run_prop_cli(
                    python=args.python,
                    exec_root=exec_root,
                    out_dir=out_dir,
                    firm_name=firm_name,
                    portfolio=portfolio,
                    firm_preset=firm_preset,
                    n_sims=args.n_sims,
                    cohort_horizon=args.cohort_horizon,
                )
                print(f"Sim OK -> {out_dir}")

    write_comparison_md(base, args.cohort_horizon)
    print(f"Wrote {base / 'COMPARE_PROP_SIM.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_telegram(main, script_name="run_prop_sim_backtest_vs_live_compare"))
