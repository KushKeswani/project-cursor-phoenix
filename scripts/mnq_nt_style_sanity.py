#!/usr/bin/env python3
"""
MNQ-only backtest on local parquet using the same fast_engine as research, with optional
**slippage ticks** and **round-turn commission** to approximate harsher NinjaTrader-style economics.

Research defaults are touch fills with **0 slippage** (see run_portfolio_preset text). NT applies
bid/ask, simulator fills, and fees — so comparing "Python headline" to "NT Strategy Analyzer" without
adjusting assumptions will often look like a huge gap.

Usage (from repo root)::

  python3 scripts/mnq_nt_style_sanity.py --data-dir Data-DataBento \\
    --start 2020-01-01 --end 2026-12-31

Then run ``scripts/compare_cs_engine_vs_python.py`` on the same window to confirm C# matches Python
on identical bars (logic parity). Remaining gap vs NT is usually data session + NT simulator.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from backtester import load_bars, raw_trades_frame, scaled_trades  # noqa: E402
from configs.strategy_configs import get_config  # noqa: E402
from configs.tick_config import TICK_SIZES, TICK_VALUES  # noqa: E402
from engine.fast_engine import ExecutionOptions, run_backtest  # noqa: E402


def _run_profile(
    *,
    bars,
    slip_stop: float,
    slip_close: float,
    label: str,
    contracts: int,
    commission_rt: float,
) -> None:
    cfg = get_config("MNQ")
    tick = float(TICK_SIZES["MNQ"])
    ex = ExecutionOptions(
        entry_fill_mode="touch",
        stop_slippage_ticks=slip_stop,
        close_slippage_ticks=slip_close,
    )
    res = run_backtest(cfg, bars, tick, return_trades=True, execution=ex)
    raw = raw_trades_frame(res)
    if raw.empty:
        gross = 0.0
        n = 0
    else:
        merged = scaled_trades(raw, "MNQ", contracts)
        gross = float(merged["pnl_usd"].sum())
        n = len(merged)
    comm = commission_rt * n
    net = gross - comm
    print(
        f"{label:32}  trades={n:5d}  gross=${gross:12,.2f}  "
        f"comm@${comm:10,.2f}  net=${net:12,.2f}  "
        f"(slip stop/close={slip_stop}/{slip_close} ticks)"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument(
        "--contracts",
        type=int,
        default=1,
        help="Contract count for $ PnL (default 1)",
    )
    p.add_argument(
        "--commission-rt",
        type=float,
        default=1.24,
        help="Round-turn commission per contract in USD (default 1.24 ≈ typical MNQ all-in; set 0 to ignore)",
    )
    args = p.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    if not data_dir.is_dir():
        print(f"data-dir not found: {data_dir}", file=sys.stderr)
        return 1

    _, bars = load_bars("MNQ", data_dir, args.start, args.end)
    if len(bars) < 12:
        print("Not enough bars after load_bars.", file=sys.stderr)
        return 1

    bars_plain = bars.copy()
    if hasattr(bars_plain, "attrs"):
        bars_plain.attrs.clear()

    contracts = max(1, int(args.contracts))
    print(
        f"MNQ fast_engine — local parquet — {args.start} .. {args.end} — "
        f"{len(bars)} bars — {contracts} contract(s)\n"
    )
    comm_rt = float(args.commission_rt)

    _run_profile(
        bars=bars_plain,
        slip_stop=0.0,
        slip_close=0.0,
        label="Research baseline (0 slip)",
        contracts=contracts,
        commission_rt=comm_rt,
    )
    _run_profile(
        bars=bars_plain,
        slip_stop=1.0,
        slip_close=1.0,
        label="Stressed (+1 tick slip)",
        contracts=contracts,
        commission_rt=comm_rt,
    )
    _run_profile(
        bars=bars_plain,
        slip_stop=2.0,
        slip_close=2.0,
        label="Stressed (+2 tick slip)",
        contracts=contracts,
        commission_rt=comm_rt,
    )
    print(
        "\nIf C# matches Python on the same window, engine logic matches; "
        "NinjaTrader still differs if chart data, session template, or simulator fills differ."
    )
    print(
        "Parity: python3 scripts/compare_cs_engine_vs_python.py --instrument MNQ "
        f"--data-dir {data_dir} --start {args.start} --end {args.end}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
