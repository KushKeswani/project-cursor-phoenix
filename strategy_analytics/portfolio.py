"""Section 7: multi-strategy portfolio metrics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._utils import safe_div

from .risk_drawdown import _drawdown_series


def compute_portfolio_metrics(
    strategies: dict[str, pd.Series],
) -> dict[str, Any]:
    """
    strategies: name -> daily PnL series (DatetimeIndex aligned or reindexed to union).
    """
    out: dict[str, Any] = {
        "correlation_matrix": {},
        "portfolio_drawdown": {},
        "combined_return_usd": 0.0,
        "capital_efficiency": 0.0,
        "n_strategies": 0,
    }
    if not strategies or len(strategies) < 2:
        out["note"] = "Provide at least two strategy daily PnL series."
        return out

    # Union index, fill 0
    dfs = []
    for name, s in strategies.items():
        if s is None or s.empty:
            continue
        dfs.append(pd.to_numeric(s, errors="coerce").fillna(0.0).rename(name))
    if len(dfs) < 2:
        out["note"] = "Need two non-empty series."
        return out

    joined = pd.concat(dfs, axis=1).fillna(0.0)
    joined = joined.sort_index()
    out["n_strategies"] = joined.shape[1]
    corr = joined.corr()
    out["correlation_matrix"] = {c: corr[c].to_dict() for c in corr.columns}

    combined = joined.sum(axis=1)
    equity = combined.cumsum()
    out["combined_return_usd"] = float(combined.sum())
    _peak, dd, max_dd = _drawdown_series(equity)
    pk_at = 1.0
    if not dd.empty and float(dd.max()) > 0:
        pk_at = float(_peak.loc[dd.idxmax()])
    out["portfolio_drawdown"] = {
        "max_drawdown_usd": float(max_dd),
        "max_drawdown_pct": 100.0 * safe_div(max_dd, pk_at),
    }
    out["capital_efficiency"] = safe_div(
        float(combined.sum()),
        max_dd if max_dd > 1e-9 else 1.0,
    )
    return out
