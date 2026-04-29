#!/usr/bin/env python3
"""
Run the same ``fast_engine.run_backtest`` MNQ preset on a **5-minute OHLC CSV** (e.g. exported
from TradingView) to see what Python would do on **identical bars** as the chart.

If this output still does not match the Strategy Tester list, the gap is Pine/broker semantics.
If it **does** match TV OHLC but not your DataBento parquet backtest, the gap is **data** (feed,
roll, session), not strategy math.

Expected columns (case-insensitive; extra columns ignored):
  - time column: ``time``, ``datetime``, ``date``, or first column if parseable as datetime
  - ``open``, ``high``, ``low``, ``close`` (or ``Open``, ``High``, …)

Bars must already be **5m** and aligned to the same clock you use in Pine (usually America/New_York).

Example::

  python3 scripts/run_mnq_backtest_on_5m_ohlc_csv.py \\
    --input ~/Downloads/MNQ_5m_export.csv \\
    --output reports/mnq_from_tv_bars_trades.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from configs.strategy_configs import get_config
from configs.tick_config import TICK_SIZES
from engine.fast_engine import ExecutionOptions, run_backtest


def _normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    colmap = {c.lower(): c for c in df.columns}
    need = ("open", "high", "low", "close")
    for n in need:
        if n not in colmap:
            raise SystemExit(f"Missing column matching '{n}'. Got: {list(df.columns)}")
    out = pd.DataFrame(
        {
            "open": pd.to_numeric(df[colmap["open"]], errors="coerce"),
            "high": pd.to_numeric(df[colmap["high"]], errors="coerce"),
            "low": pd.to_numeric(df[colmap["low"]], errors="coerce"),
            "close": pd.to_numeric(df[colmap["close"]], errors="coerce"),
        },
        index=df.index,
    )
    out = out.dropna(how="any")
    return out


def _parse_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    time_keys = ("datetime", "time", "date", "timestamp")
    lower_cols = {str(c).lower(): c for c in df.columns}
    for k in time_keys:
        if k in lower_cols:
            col = lower_cols[k]
            idx = pd.to_datetime(df[col], utc=False, errors="coerce")
            return pd.DatetimeIndex(idx)
    # first column
    idx = pd.to_datetime(df.iloc[:, 0], utc=False, errors="coerce")
    if idx.notna().mean() < 0.9:
        raise SystemExit("Could not parse a datetime index; add a time/datetime column.")
    return pd.DatetimeIndex(idx)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, required=True, help="5m OHLC CSV (TV export or similar)")
    ap.add_argument("--output", type=Path, default=None, help="Write trades CSV (default: stdout summary only)")
    ap.add_argument(
        "--fill-mode",
        default="touch",
        choices=("touch", "touch_strict", "stop_market", "next_bar_open"),
        help="ExecutionOptions.entry_fill_mode (default touch, same as Pine default)",
    )
    args = ap.parse_args()

    raw = pd.read_csv(args.input)
    idx = _parse_index(raw)
    raw = raw.copy()
    raw.index = idx
    raw = raw[~raw.index.isna()].sort_index()
    bars = _normalize_ohlc(raw)
    bars = bars[~bars.index.duplicated(keep="last")]

    cfg = get_config("MNQ")
    tick = float(TICK_SIZES["MNQ"])
    ex = ExecutionOptions(entry_fill_mode=args.fill_mode)
    res = run_backtest(cfg, bars, tick, return_trades=True, execution=ex)
    trades = res.get("trades") or []

    print(f"Bars: {len(bars)}  from {bars.index.min()} -> {bars.index.max()}")
    print(f"Trades: {len(trades)}  fill_mode={args.fill_mode}")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for t in trades:
            rows.append(
                {
                    "entry_ts": t.get("entry_ts"),
                    "exit_ts": t.get("exit_ts"),
                    "direction": t.get("direction"),
                    "entry_price": t.get("entry_price"),
                    "exit_price": t.get("exit_price"),
                    "pnl_ticks": t.get("pnl_ticks"),
                    "exit_reason": t.get("exit_reason"),
                }
            )
        pd.DataFrame(rows).to_csv(args.output, index=False)
        print(f"Wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
