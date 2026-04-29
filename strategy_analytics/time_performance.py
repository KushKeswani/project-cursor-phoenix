"""Section 3: time-aggregated performance from daily PnL."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._utils import TRADING_DAYS_MONTH, TRADING_DAYS_YEAR, safe_div


def compute_time_performance(daily_pnl: pd.Series, equity: pd.Series) -> dict[str, Any]:
    out: dict[str, Any] = {
        "avg_day": 0.0,
        "avg_week": 0.0,
        "avg_month": 0.0,
        "avg_quarter": 0.0,
        "avg_year": 0.0,
        "pct_winning_days": 0.0,
        "pct_winning_weeks": 0.0,
        "pct_winning_months": 0.0,
        "largest_winning_day": 0.0,
        "largest_winning_day_pct_of_total_profit": 0.0,
        "pct_profit_from_top_5_days": 0.0,
        "n_trading_days": 0,
    }
    if daily_pnl.empty:
        return out

    pnl = daily_pnl.astype(float)
    out["n_trading_days"] = int(pnl.size)
    out["avg_day"] = float(pnl.mean())
    out["pct_winning_days"] = 100.0 * safe_div(float((pnl > 0).sum()), float(pnl.size))

    total_profit = float(pnl[pnl > 0].sum())
    net = float(pnl.sum())
    pos_days = pnl[pnl > 0]
    if not pos_days.empty:
        out["largest_winning_day"] = float(pos_days.max())
        out["largest_winning_day_pct_of_total_profit"] = (
            100.0 * safe_div(out["largest_winning_day"], total_profit) if total_profit > 1e-9 else 0.0
        )
        top5 = pos_days.nlargest(min(5, len(pos_days)))
        out["pct_profit_from_top_5_days"] = (
            100.0 * safe_div(float(top5.sum()), net) if abs(net) > 1e-9 else 0.0
        )

    if isinstance(pnl.index, pd.DatetimeIndex):
        w = pnl.resample("W").sum()
        m = pnl.resample("M").sum()
        q = pnl.resample("Q").sum()
        out["avg_week"] = float(w.mean()) if not w.empty else 0.0
        out["avg_month"] = float(m.mean()) if not m.empty else 0.0
        out["avg_quarter"] = float(q.mean()) if not q.empty else 0.0
        if not w.empty:
            out["pct_winning_weeks"] = 100.0 * safe_div(float((w > 0).sum()), float(len(w)))
        if not m.empty:
            out["pct_winning_months"] = 100.0 * safe_div(float((m > 0).sum()), float(len(m)))
    else:
        # approximate from day count
        n = len(pnl)
        out["avg_month"] = float(pnl.sum()) / max(1.0, n / TRADING_DAYS_MONTH)
        out["avg_year"] = float(pnl.sum()) / max(1.0, n / TRADING_DAYS_YEAR)

    if isinstance(pnl.index, pd.DatetimeIndex) and len(pnl) > 1:
        span_days = (pnl.index[-1] - pnl.index[0]).days + 1
        years = max(span_days / 365.25, 1e-9)
        out["avg_year"] = float(pnl.sum()) / years
    elif out.get("avg_year") == 0.0 and len(pnl) > 0:
        out["avg_year"] = float(pnl.sum()) / max(1.0, len(pnl) / TRADING_DAYS_YEAR)

    return out
