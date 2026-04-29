"""
Strategy performance + prop-firm analytics dashboard.

Example
-------
>>> import pandas as pd
>>> from strategy_analytics import compute_performance_dashboard, dashboard_to_json
>>> daily = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="B"), "daily_pnl": ...})
>>> prop = {"profit_target": 3000, "trailing_drawdown": 2000, "daily_loss_limit": 1000, "consistency_rule": 0.5}
>>> d = compute_performance_dashboard(daily=daily, prop_params=prop)
>>> print(dashboard_to_json(d)[:500])
"""

from .dashboard import compute_performance_dashboard, dashboard_to_json

__all__ = ["compute_performance_dashboard", "dashboard_to_json"]
