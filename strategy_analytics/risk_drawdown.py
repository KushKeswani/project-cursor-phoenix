"""Section 2: drawdown and risk ratios from equity curve."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from ._utils import TRADING_DAYS_YEAR, safe_div


def _drawdown_series(equity: pd.Series) -> tuple[pd.Series, pd.Series, float]:
    """Running peak and drawdown (USD from peak)."""
    if equity.empty:
        return (
            pd.Series(dtype=float),
            pd.Series(dtype=float),
            0.0,
        )
    peak = equity.cummax()
    dd = peak - equity
    max_dd = float(dd.max()) if not dd.empty else 0.0
    return peak, dd, max_dd


def _drawdown_episodes(dd: pd.Series, peak: pd.Series, equity: pd.Series) -> tuple[list[int], list[float]]:
    """Durations (days) underwater until new equity high; depths as fraction of peak at start of DD."""
    durations: list[int] = []
    depths: list[float] = []
    if dd.empty:
        return durations, depths

    underwater = dd > 1e-9
    if not underwater.any():
        return durations, depths

    idx = dd.index
    in_dd = False
    start_i = 0
    for i in range(len(dd)):
        u = bool(underwater.iloc[i])
        if u and not in_dd:
            in_dd = True
            start_i = i
        elif not u and in_dd:
            in_dd = False
            durations.append(i - start_i)
            pk = float(peak.iloc[start_i])
            depths.append(safe_div(float(dd.iloc[start_i : i].max()), pk))
    if in_dd:
        durations.append(len(dd) - start_i)
        pk = float(peak.iloc[start_i])
        depths.append(safe_div(float(dd.iloc[start_i:].max()), pk))
    return durations, depths


def _recovery_times(dd: pd.Series) -> tuple[list[int], float, float]:
    """Lengths of drawdown episodes (days from first underwater until dd returns ~0)."""
    if dd.empty:
        return [], 0.0, 0.0
    lengths: list[int] = []
    in_dd = False
    start = 0
    for i in range(len(dd)):
        v = float(dd.iloc[i])
        if v > 1e-9 and not in_dd:
            in_dd = True
            start = i
        elif v <= 1e-9 and in_dd:
            in_dd = False
            lengths.append(max(1, i - start))
    if not lengths:
        return [], 0.0, 0.0
    return lengths, float(np.mean(lengths)), float(np.max(lengths))


def max_consecutive_losing_trades(trades: pd.DataFrame) -> tuple[int, float]:
    if trades is None or trades.empty or "pnl" not in trades.columns:
        return 0, 0.0
    pnl = trades["pnl"].astype(float)
    streak = max_streak = 0
    streaks: list[int] = []
    for v in pnl:
        if v < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            if streak > 0:
                streaks.append(streak)
            streak = 0
    if streak > 0:
        streaks.append(streak)
    avg = float(np.mean(streaks)) if streaks else 0.0
    return int(max_streak), avg


def compute_risk_metrics(
    daily_pnl: pd.Series,
    equity: pd.Series,
    *,
    trades: pd.DataFrame | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "max_drawdown_usd": 0.0,
        "max_drawdown_percent": 0.0,
        "avg_drawdown": 0.0,
        "drawdown_durations": [],
        "avg_time_to_recover_days": 0.0,
        "max_time_to_recover_days": 0.0,
        "max_consecutive_loss_days": 0,
        "avg_consecutive_loss_days": 0.0,
        "max_consecutive_losses": 0,
        "avg_consecutive_losses": 0.0,
        "worst_day": 0.0,
        "worst_week": 0.0,
        "worst_month": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "calmar_ratio": 0.0,
        "total_return_usd": 0.0,
    }
    if equity.empty:
        return out

    peak, dd_usd, max_dd_usd = _drawdown_series(equity)
    out["max_drawdown_usd"] = max_dd_usd
    pk_at_max = float(peak.loc[dd_usd.idxmax()]) if not dd_usd.empty and dd_usd.max() > 0 else float(peak.iloc[-1])
    out["max_drawdown_percent"] = 100.0 * safe_div(max_dd_usd, pk_at_max) if pk_at_max > 1e-9 else 0.0

    durations, _depths = _drawdown_episodes(dd_usd, peak, equity)
    out["drawdown_durations"] = [int(d) for d in durations]
    if dd_usd.size:
        underwater = dd_usd > 1e-9
        if underwater.any():
            out["avg_drawdown"] = float(dd_usd[underwater].mean())
        else:
            out["avg_drawdown"] = 0.0

    rec_list, rec_avg, rec_max = _recovery_times(dd_usd)
    out["avg_time_to_recover_days"] = rec_avg
    out["max_time_to_recover_days"] = rec_max

    if not daily_pnl.empty:
        neg = daily_pnl < 0
        streak = 0
        max_streak = 0
        streaks: list[int] = []
        for v in neg:
            if bool(v):
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                if streak > 0:
                    streaks.append(streak)
                streak = 0
        if streak > 0:
            streaks.append(streak)
        out["max_consecutive_loss_days"] = int(max_streak)
        out["avg_consecutive_loss_days"] = float(np.mean(streaks)) if streaks else 0.0
        out["worst_day"] = float(daily_pnl.min())

        if isinstance(daily_pnl.index, pd.DatetimeIndex):
            w = daily_pnl.resample("W").sum()
            m = daily_pnl.resample("ME").sum()
            out["worst_week"] = float(w.min()) if not w.empty else 0.0
            out["worst_month"] = float(m.min()) if not m.empty else 0.0

    # Returns: daily_pnl / prior equity (avoid div by zero)
    if not daily_pnl.empty and daily_pnl.index.equals(equity.index):
        prev = equity.shift(1)
        prev = prev.where(prev.abs() > 1e-9, other=np.nan)
        rets = (daily_pnl / prev).dropna()
    else:
        rets = equity.pct_change().dropna()
    if len(rets) > 2:
        mu = float(rets.mean())
        sig = float(rets.std(ddof=1))
        out["sharpe_ratio"] = safe_div(mu, sig, default=0.0) * math.sqrt(TRADING_DAYS_YEAR)
        neg_rets = rets[rets < 0]
        ds = float(neg_rets.std(ddof=1)) if len(neg_rets) > 1 else 0.0
        out["sortino_ratio"] = safe_div(mu, ds, default=0.0) * math.sqrt(TRADING_DAYS_YEAR)
    out["total_return_usd"] = float(equity.iloc[-1] - equity.iloc[0]) if len(equity) else 0.0
    # Calmar: annualized return / max DD (as decimal)
    years = len(equity) / TRADING_DAYS_YEAR if TRADING_DAYS_YEAR else 1.0
    ann = safe_div(float(equity.iloc[-1] - equity.iloc[0]), years, default=0.0) if years > 0 else 0.0
    out["calmar_ratio"] = safe_div(ann, max_dd_usd, default=0.0) if max_dd_usd > 1e-9 else 0.0

    if trades is not None:
        mxl, axl = max_consecutive_losing_trades(trades)
        out["max_consecutive_losses"] = mxl
        out["avg_consecutive_losses"] = axl
    return out
