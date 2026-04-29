#!/usr/bin/env python3
"""
Parity check: C# rb-backtest engine vs Python fast_engine.run_backtest.

Uses the same resampled OHLC as the backtester, writes a temp CSV, clears
``bars.attrs`` on the Python side so flatten lookup matches the C# bar-only
path (what you get when feeding NinjaTrader / CSV without embedded 1m data).

Example::

  python3 scripts/compare_cs_engine_vs_python.py --instrument MNQ \\
    --data-dir Data-DataBento --start 2024-06-01 --end 2024-06-30
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO / "scripts"
# One frozen executable per instrument (touch fills only). Keys must match --instrument.
CS_PROJ_BY_INSTRUMENT = {
    "CL": REPO / "csharp" / "Cl.Backtest" / "Cl.Backtest.csproj",
    "MGC": REPO / "csharp" / "Mgc.Backtest" / "Mgc.Backtest.csproj",
    "MNQ": REPO / "csharp" / "Mnq.Backtest" / "Mnq.Backtest.csproj",
    "YM": REPO / "csharp" / "Ym.Backtest" / "Ym.Backtest.csproj",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument", required=True, choices=["CL", "MGC", "MNQ", "YM"])
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--fills", choices=["touch", "stop-market"], default="touch")
    parser.add_argument("--dotnet", default="dotnet", help="dotnet executable")
    parser.add_argument("--price-eps", type=float, default=1e-4)
    parser.add_argument("--tick-eps", type=float, default=1e-3)
    args = parser.parse_args()

    cs_proj = CS_PROJ_BY_INSTRUMENT.get(args.instrument.upper())
    if cs_proj is None or not cs_proj.is_file():
        print(f"Missing C# project for instrument {args.instrument}: {cs_proj}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(SCRIPT_DIR))
    from backtester import load_bars  # noqa: E402
    from configs.strategy_configs import get_config  # noqa: E402
    from configs.tick_config import TICK_SIZES  # noqa: E402
    from engine.fast_engine import ExecutionOptions, run_backtest  # noqa: E402

    inst = args.instrument.upper()
    if args.fills != "touch":
        print(
            "C# instrument runners are hardcoded to touch fills; use --fills touch for parity.",
            file=sys.stderr,
        )
        return 2

    _, bars = load_bars(inst, args.data_dir, args.start, args.end)
    if len(bars) < 12:
        print("Not enough bars after load.", file=sys.stderr)
        return 1

    bars_plain = bars.copy()
    bars_plain.attrs.clear()

    cfg = get_config(inst)
    tick = float(TICK_SIZES[inst])
    mode = "stop_market" if args.fills == "stop-market" else "touch"
    ex = ExecutionOptions(entry_fill_mode=mode)
    py_res = run_backtest(cfg, bars_plain, tick, return_trades=True, execution=ex)
    py_trades = py_res.get("trades") or []

    out = bars_plain.reset_index()
    first = out.columns[0]
    if first != "datetime":
        out = out.rename(columns={first: "datetime"})
    cols = ["datetime", "open", "high", "low", "close"]
    out = out[[c for c in cols if c in out.columns]]

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "bars.csv"
        cs_trades_path = Path(tmp) / "cs_trades.csv"
        out.to_csv(csv_path, index=False)

        cmd = [
            args.dotnet,
            "run",
            "--project",
            str(cs_proj),
            "--no-build",
            "-c",
            "Release",
            "--",
            "--bars",
            str(csv_path),
            "--out",
            str(cs_trades_path),
        ]
        r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout, r.stderr, sep="\n", file=sys.stderr)
            return r.returncode

        if not cs_trades_path.is_file():
            print("C# did not write trades CSV.", file=sys.stderr)
            return 1

        cs_df = pd.read_csv(cs_trades_path)
        cs_df["entry_ts"] = pd.to_datetime(cs_df["entry_ts"])
        cs_df["exit_ts"] = pd.to_datetime(cs_df["exit_ts"])

    py_df = pd.DataFrame(py_trades)
    if py_df.empty and cs_df.empty:
        print("OK: both 0 trades")
        return 0
    if py_df.empty or cs_df.empty:
        print(f"Mismatch trade count Python={len(py_df)} C#={len(cs_df)}", file=sys.stderr)
        return 1

    py_df = py_df.sort_values("entry_ts").reset_index(drop=True)
    cs_df = cs_df.sort_values("entry_ts").reset_index(drop=True)
    if len(py_df) != len(cs_df):
        print(f"Mismatch trade count Python={len(py_df)} C#={len(cs_df)}", file=sys.stderr)
        return 1

    issues: list[str] = []
    for i in range(len(py_df)):
        pr, cr = py_df.iloc[i], cs_df.iloc[i]
        if str(pr["direction"]).lower() != str(cr["direction"]).lower():
            issues.append(f"trade {i+1} direction {pr['direction']} vs {cr['direction']}")
        if abs(float(pr["entry_price"]) - float(cr["entry_price"])) > args.price_eps:
            issues.append(
                f"trade {i+1} entry_price py={pr['entry_price']} cs={cr['entry_price']}"
            )
        if abs(float(pr["exit_price"]) - float(cr["exit_price"])) > args.price_eps:
            issues.append(
                f"trade {i+1} exit_price py={pr['exit_price']} cs={cr['exit_price']}"
            )
        if abs(float(pr["pnl_ticks"]) - float(cr["pnl_ticks"])) > args.tick_eps:
            issues.append(
                f"trade {i+1} pnl_ticks py={pr['pnl_ticks']} cs={cr['pnl_ticks']}"
            )
        etp = pd.Timestamp(pr["entry_ts"])
        etc = pd.Timestamp(cr["entry_ts"])
        if etp != etc:
            issues.append(f"trade {i+1} entry_ts py={etp} cs={etc}")
        xtp = pd.Timestamp(pr["exit_ts"])
        xtc = pd.Timestamp(cr["exit_ts"])
        if xtp != xtc:
            issues.append(f"trade {i+1} exit_ts py={xtp} cs={xtc}")

    if issues:
        print("Parity issues:", file=sys.stderr)
        for line in issues[:40]:
            print(f"  {line}", file=sys.stderr)
        if len(issues) > 40:
            print(f"  ... and {len(issues) - 40} more", file=sys.stderr)
        return 1

    print(f"OK: {len(py_df)} trades match (fills={args.fills}, bar-only flatten path).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
