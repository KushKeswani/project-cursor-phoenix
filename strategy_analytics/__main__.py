"""python -m strategy_analytics --help"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .dashboard import compute_performance_dashboard, dashboard_to_json


def main() -> int:
    p = argparse.ArgumentParser(description="Build performance + prop analytics JSON.")
    p.add_argument("--trades-csv", type=Path, help="Trade-level CSV")
    p.add_argument("--daily-csv", type=Path, help="Daily date, daily_pnl CSV")
    p.add_argument("--prop-json", type=Path, help="Prop parameters JSON object")
    p.add_argument("--out-json", type=Path, help="Write dashboard JSON here")
    p.add_argument("--mc-sims", type=int, default=1000)
    p.add_argument("--prop-sims", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    trades = pd.read_csv(args.trades_csv) if args.trades_csv else None
    daily = pd.read_csv(args.daily_csv) if args.daily_csv else None
    prop = None
    if args.prop_json:
        prop = json.loads(args.prop_json.read_text(encoding="utf-8"))

    dash = compute_performance_dashboard(
        trades=trades,
        daily=daily,
        prop_params=prop,
        monte_carlo_n=args.mc_sims,
        monte_carlo_seed=args.seed,
        prop_bootstrap_n=args.prop_sims,
    )
    s = dashboard_to_json(dash)
    if args.out_json:
        args.out_json.write_text(s, encoding="utf-8")
    else:
        print(s)
    return 0


if __name__ == "__main__":
    _sd = Path(__file__).resolve().parents[1] / "scripts"
    if str(_sd) not in sys.path:
        sys.path.insert(0, str(_sd))
    from telegram_script_done import run_with_telegram

    raise SystemExit(run_with_telegram(main, script_name="strategy_analytics"))
