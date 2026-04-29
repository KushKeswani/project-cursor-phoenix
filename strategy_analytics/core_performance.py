"""Section 1: core performance from trade-level PnL."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from ._utils import safe_div


def compute_core_performance(trades: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "expectancy_per_trade": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "risk_reward_ratio": 0.0,
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "median_trade": 0.0,
        "std_dev_trade_pnl": 0.0,
        "n_trades": 0,
        "n_winners": 0,
        "n_losers": 0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "net_profit": 0.0,
    }
    if trades is None or trades.empty or "pnl" not in trades.columns:
        return out

    pnl = trades["pnl"].astype(float).dropna()
    n = int(pnl.size)
    out["n_trades"] = n
    if n == 0:
        return out

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    out["n_winners"] = int(wins.size)
    out["n_losers"] = int(losses.size)
    out["win_rate"] = 100.0 * safe_div(float(wins.size), float(n))
    gp = float(wins.sum()) if not wins.empty else 0.0
    gl = float(-losses.sum()) if not losses.empty else 0.0
    out["gross_profit"] = gp
    out["gross_loss"] = gl
    out["net_profit"] = float(pnl.sum())
    out["profit_factor"] = safe_div(gp, gl, default=0.0) if gl > 1e-12 else (float("inf") if gp > 0 else 0.0)
    if out["profit_factor"] == float("inf"):
        out["profit_factor"] = None  # JSON-friendly; consumer can treat as "infinite"
    out["expectancy_per_trade"] = float(pnl.mean())
    out["avg_win"] = float(wins.mean()) if not wins.empty else 0.0
    out["avg_loss"] = float(losses.mean()) if not losses.empty else 0.0
    out["risk_reward_ratio"] = safe_div(out["avg_win"], abs(out["avg_loss"]), default=0.0) if out["avg_loss"] < -1e-12 else (float("inf") if out["avg_win"] > 0 else 0.0)
    if out["risk_reward_ratio"] == float("inf"):
        out["risk_reward_ratio"] = None
    out["best_trade"] = float(pnl.max())
    out["worst_trade"] = float(pnl.min())
    out["median_trade"] = float(pnl.median())
    out["std_dev_trade_pnl"] = float(pnl.std(ddof=1)) if n > 1 else 0.0
    return out
