#!/usr/bin/env python3
"""Export raw per-instrument trade CSVs for prop_farming_calculator (goals.md §5).

Writes::
  <reports-root>/trade_executions/<scope>/instruments/<INST>_trade_executions.csv

Columns match ``prop_farming_calculator`` expectations (entry_ts, exit_ts, direction, pnl_ticks).
Raw trades are **not** scaled by portfolio preset — scaling happens in the calculator via contracts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from backtester import INSTRUMENTS, load_bars, raw_trades_frame, resolve_data_dir  # noqa: E402
from configs.strategy_configs import get_config  # noqa: E402
from configs.tick_config import TICK_SIZES  # noqa: E402
from engine.fast_engine import run_backtest  # noqa: E402


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        path.write_text("entry_ts,exit_ts,direction,pnl_ticks\n", encoding="utf-8")
        return
    out = df[["entry_ts", "exit_ts", "direction", "pnl_ticks"]].copy()
    for col in ("entry_ts", "exit_ts"):
        t = pd.to_datetime(out[col], utc=True)
        out[col] = t.dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    out.to_csv(path, index=False)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", default=None, help="Parquet root (default: Data-DataBento)")
    p.add_argument(
        "--reports-root",
        type=Path,
        default=REPO_ROOT / "reports",
        help="Folder that will contain trade_executions/…",
    )
    p.add_argument("--scope", choices=("oos", "full"), default="oos")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    args = p.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    root = args.reports_root.expanduser().resolve()
    inst_dir = root / "trade_executions" / args.scope / "instruments"

    start_s = f"{args.start} 00:00:00"
    end_s = f"{args.end} 23:59:59"

    for instrument in INSTRUMENTS:
        _, bars = load_bars(instrument, data_dir, start_s, end_s)
        cfg = get_config(instrument)
        raw = raw_trades_frame(
            run_backtest(cfg, bars, TICK_SIZES[instrument], return_trades=True)
        )
        _write_csv(inst_dir / f"{instrument}_trade_executions.csv", raw)
        print(f"Wrote {inst_dir / (instrument + '_trade_executions.csv')}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
