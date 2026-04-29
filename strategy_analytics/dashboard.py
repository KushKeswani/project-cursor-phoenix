"""Assemble full performance + prop + MC dashboard."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from ._utils import nan_to_none, normalize_daily, normalize_trades
from .core_performance import compute_core_performance
from .monte_carlo import compute_monte_carlo
from .portfolio import compute_portfolio_metrics
from .prop_simulation import compute_prop_metrics
from .risk_drawdown import compute_risk_metrics
from .time_performance import compute_time_performance
from .trade_flow import compute_trade_flow


def compute_performance_dashboard(
    *,
    trades: pd.DataFrame | None = None,
    daily: pd.DataFrame | None = None,
    prop_params: dict[str, Any] | None = None,
    monte_carlo_n: int = 1000,
    monte_carlo_seed: int = 42,
    prop_bootstrap_n: int = 1000,
    strategies_daily: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    """
    Build nested dashboard dict.

    Parameters
    ----------
    trades : DataFrame with pnl (+ optional timestamp, direction, duration)
    daily : DataFrame with date + daily_pnl (+ optional cumulative_equity)
    prop_params : profit_target, trailing_drawdown, daily_loss_limit (optional),
        consistency_rule (optional), eval_window_days, eval_min_trading_days,
        starting_balance_usd, funded_trailing_drawdown, min_days_for_payout,
        min_profit_per_day_usd, withdraw_fraction
    strategies_daily : optional {name: daily_pnl series} for portfolio section
    """
    tdf = normalize_trades(trades)
    daily_pnl, equity = normalize_daily(daily)

    # Align daily pnl to equity index
    if not daily_pnl.empty and not equity.empty:
        daily_pnl = daily_pnl.reindex(equity.index).fillna(0.0)

    result: dict[str, Any] = {
        "performance": compute_core_performance(tdf),
        "risk": compute_risk_metrics(daily_pnl, equity, trades=tdf),
        "time": compute_time_performance(daily_pnl, equity),
        "trade_flow": compute_trade_flow(tdf),
        "prop_metrics": compute_prop_metrics(
            daily_pnl,
            prop_params,
            n_bootstrap=prop_bootstrap_n,
            seed=monte_carlo_seed,
        ),
        "monte_carlo": {},
        "portfolio": {},
    }

    trail = float(prop_params.get("trailing_drawdown", 2000.0)) if prop_params else 2000.0
    dll = prop_params.get("daily_loss_limit") if prop_params else None
    dll_f = float(dll) if dll is not None else None
    pt = float(prop_params.get("profit_target", 3000.0)) if prop_params else 3000.0

    if not daily_pnl.empty:
        result["monte_carlo"] = compute_monte_carlo(
            daily_pnl,
            n_sims=monte_carlo_n,
            seed=monte_carlo_seed,
            horizon_short=60,
            horizon_long=252,
            trailing_drawdown=trail,
            daily_loss_limit=dll_f,
            profit_target=pt,
        )

    if strategies_daily:
        result["portfolio"] = compute_portfolio_metrics(strategies_daily)
    else:
        result["portfolio"] = {"note": "No multi-strategy input provided."}

    return result


def dashboard_to_json(dashboard: dict[str, Any], *, indent: int = 2) -> str:
    safe = nan_to_none(dashboard)
    return json.dumps(safe, indent=indent, default=str)
