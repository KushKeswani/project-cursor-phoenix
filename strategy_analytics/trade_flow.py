"""Section 4: trade flow and session tagging."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._utils import safe_div


def _session_label(ts: pd.Timestamp) -> str:
    """Rough futures session bucket in UTC (simplified)."""
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    h = ts.hour
    # Asia ~ 00–08 UTC, London ~ 08–16, NY ~ 13–21 (overlap intentional)
    if 0 <= h < 8:
        return "asia"
    if 8 <= h < 13:
        return "london"
    if 13 <= h < 21:
        return "ny"
    return "other"


def compute_trade_flow(trades: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {
        "trades_per_day": 0.0,
        "trades_per_week": 0.0,
        "avg_trade_duration": None,
        "time_in_market_pct": None,
        "pnl_by_session": {},
        "first_trade": None,
        "last_trade": None,
        "span_calendar_days": 0,
    }
    if trades is None or trades.empty or "pnl" not in trades.columns:
        return out

    n = len(trades)
    if "timestamp" not in trades.columns:
        out["trades_per_day"] = float(n)
        return out

    ts = pd.to_datetime(trades["timestamp"])
    span = (ts.max() - ts.min()).days + 1
    out["span_calendar_days"] = int(max(span, 1))
    out["first_trade"] = ts.min().isoformat()
    out["last_trade"] = ts.max().isoformat()
    out["trades_per_day"] = safe_div(float(n), float(out["span_calendar_days"]))
    out["trades_per_week"] = out["trades_per_day"] * 7.0

    if "duration" in trades.columns:
        dur = pd.to_numeric(trades["duration"], errors="coerce").dropna()
        if not dur.empty:
            out["avg_trade_duration"] = float(dur.mean())
            # if duration in seconds, estimate time in market vs span
            span_sec = max((ts.max() - ts.min()).total_seconds(), 1.0)
            out["time_in_market_pct"] = 100.0 * safe_div(float(dur.sum()), span_sec)

    sessions: dict[str, list[float]] = {"asia": [], "london": [], "ny": [], "other": []}
    for t, pnl in zip(ts, trades["pnl"].astype(float)):
        sessions[_session_label(pd.Timestamp(t))].append(float(pnl))
    out["pnl_by_session"] = {
        k: {"n": len(v), "total_pnl": float(sum(v)), "avg_pnl": float(np.mean(v)) if v else 0.0}
        for k, v in sessions.items()
        if v
    }
    return out
