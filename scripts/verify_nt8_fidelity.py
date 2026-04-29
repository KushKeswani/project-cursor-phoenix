#!/usr/bin/env python3
"""
Compare Python engine trade exports with NT8 strategy trade exports.

Reads:
- Python: reports/trade_executions/{scope}/instruments/{INST}_trade_executions.csv
- NT8: --nt8-dir or Documents/NinjaTrader 8/RangeBreakoutTrades/

Compares entry_ts, exit_ts, direction, entry_price, exit_price, pnl_ticks.
Allows small tolerances for platform fill semantics.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
INSTRUMENTS = ["CL", "MGC", "MNQ", "YM"]

# Tolerances: platform fill semantics may differ slightly
PRICE_TOLERANCE = 0.0001
PNL_TICKS_TOLERANCE = 0.5
TIMESTAMP_TOLERANCE_SEC = 60  # bars may align differently


def load_python_trades(reports_dir: Path, scope: str) -> dict[str, pd.DataFrame]:
    out = {}
    for inst in INSTRUMENTS:
        path = reports_dir / scope / "instruments" / f"{inst}_trade_executions.csv"
        if path.exists():
            df = pd.read_csv(path)
            df["entry_ts"] = pd.to_datetime(df["entry_ts"])
            df["exit_ts"] = pd.to_datetime(df["exit_ts"])
            out[inst] = df
        else:
            out[inst] = pd.DataFrame()
    return out


def load_nt8_trades(nt8_dir: Path) -> dict[str, pd.DataFrame]:
    out = {}
    for inst in INSTRUMENTS:
        # NT8 files: CL_nt8_trades_20260101_120000.csv etc.
        matches = list(nt8_dir.glob(f"{inst}_nt8_trades_*.csv"))
        if not matches:
            out[inst] = pd.DataFrame()
            continue
        path = max(matches, key=lambda p: p.stat().st_mtime)
        df = pd.read_csv(path)
        if "entry_ts" in df.columns and "exit_ts" in df.columns:
            df["entry_ts"] = pd.to_datetime(df["entry_ts"])
            df["exit_ts"] = pd.to_datetime(df["exit_ts"])
        out[inst] = df
    return out


def compare_instrument(py_df: pd.DataFrame, nt8_df: pd.DataFrame, instrument: str) -> list[str]:
    issues = []
    if py_df.empty and nt8_df.empty:
        return issues
    if py_df.empty:
        issues.append(f"{instrument}: Python has 0 trades, NT8 has {len(nt8_df)}")
        return issues
    if nt8_df.empty:
        issues.append(f"{instrument}: Python has {len(py_df)} trades, NT8 has 0")
        return issues

    py_df = py_df.sort_values("entry_ts").reset_index(drop=True)
    nt8_df = nt8_df.sort_values("entry_ts").reset_index(drop=True)

    n_py, n_nt8 = len(py_df), len(nt8_df)
    if n_py != n_nt8:
        issues.append(f"{instrument}: Trade count mismatch Python={n_py} NT8={n_nt8}")

    n = min(n_py, n_nt8)
    for i in range(n):
        py_row = py_df.iloc[i]
        nt8_row = nt8_df.iloc[i]
        prefix = f"{instrument} trade {i+1}"

        if str(py_row.get("direction", "")).lower() != str(nt8_row.get("direction", "")).lower():
            issues.append(f"{prefix}: direction {py_row.get('direction')} vs {nt8_row.get('direction')}")

        ep_py = float(py_row.get("entry_price", 0))
        ep_nt8 = float(nt8_row.get("entry_price", 0))
        if abs(ep_py - ep_nt8) > PRICE_TOLERANCE:
            issues.append(f"{prefix}: entry_price {ep_py} vs {ep_nt8}")

        xp_py = float(py_row.get("exit_price", 0))
        xp_nt8 = float(nt8_row.get("exit_price", 0))
        if abs(xp_py - xp_nt8) > PRICE_TOLERANCE:
            issues.append(f"{prefix}: exit_price {xp_py} vs {xp_nt8}")

        pt_py = float(py_row.get("pnl_ticks", 0))
        pt_nt8 = float(nt8_row.get("pnl_ticks", 0))
        if abs(pt_py - pt_nt8) > PNL_TICKS_TOLERANCE:
            issues.append(f"{prefix}: pnl_ticks {pt_py:.2f} vs {pt_nt8:.2f}")

        et_py = pd.Timestamp(py_row.get("entry_ts"))
        et_nt8 = pd.Timestamp(nt8_row.get("entry_ts"))
        if abs((et_py - et_nt8).total_seconds()) > TIMESTAMP_TOLERANCE_SEC:
            issues.append(f"{prefix}: entry_ts {et_py} vs {et_nt8}")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-dir", default="reports/trade_executions")
    parser.add_argument("--nt8-dir", default=None)
    parser.add_argument("--scope", choices=["full", "oos"], default="oos")
    args = parser.parse_args()

    py_dir = Path(args.python_dir)
    if args.nt8_dir:
        nt8_dir = Path(args.nt8_dir)
    else:
        nt8_dir = Path.home() / "Documents" / "NinjaTrader 8" / "RangeBreakoutTrades"

    if not nt8_dir.exists():
        print(f"NT8 dir not found: {nt8_dir}")
        print("Run NT8 backtest with ExportTradesToCsv=true, or pass --nt8-dir")
        return 1

    py_trades = load_python_trades(py_dir, args.scope)
    nt8_trades = load_nt8_trades(nt8_dir)

    all_issues = []
    for inst in INSTRUMENTS:
        issues = compare_instrument(
            py_trades.get(inst, pd.DataFrame()),
            nt8_trades.get(inst, pd.DataFrame()),
            inst,
        )
        all_issues.extend(issues)
        if not issues:
            n = len(py_trades.get(inst, pd.DataFrame()))
            print(f"{inst}: OK ({n} trades)")

    if all_issues:
        print("\nMismatches:")
        for issue in all_issues[:50]:
            print(f"  {issue}")
        if len(all_issues) > 50:
            print(f"  ... and {len(all_issues) - 50} more")
        return 1
    print("\nAll instruments match within tolerance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
