"""Section 6: bootstrap Monte Carlo on daily PnL."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._utils import safe_div


def _bust_or_target_path(
    pnls: np.ndarray,
    *,
    trailing_drawdown: float,
    daily_loss_limit: float | None,
    profit_target: float | None,
    horizon: int,
) -> tuple[bool, bool, float]:
    """
    Walk forward `horizon` days with pnls (wrapped). Returns (busted, hit_target, final_cum_pnl).
    Bust: trail from peak cum profit OR dll breach.
    """
    cum = 0.0
    peak = 0.0
    busted = False
    hit = False
    h = min(horizon, len(pnls) * 2)  # allow wrap
    for i in range(h):
        pnl = float(pnls[i % len(pnls)])
        if daily_loss_limit is not None and pnl <= -float(daily_loss_limit) + 1e-12:
            busted = True
            cum += pnl
            break
        cum += pnl
        peak = max(peak, cum)
        if peak - cum > float(trailing_drawdown) + 1e-9:
            busted = True
            break
        if profit_target is not None and cum >= float(profit_target) - 1e-9:
            hit = True
    return busted, hit, float(cum)


def compute_monte_carlo(
    daily_pnl: pd.Series,
    *,
    n_sims: int = 1000,
    seed: int = 42,
    horizon_short: int = 60,
    horizon_long: int = 252,
    trailing_drawdown: float = 2000.0,
    daily_loss_limit: float | None = None,
    profit_target: float | None = 3000.0,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "n_sims": n_sims,
        "probability_of_bust_60d_pct": 0.0,
        "probability_of_bust_252d_pct": 0.0,
        "probability_of_hitting_profit_target_60d_pct": 0.0,
        "probability_of_hitting_profit_target_252d_pct": 0.0,
        "median_equity_curve": [],
        "worst_case_curve_p10": [],
        "best_case_curve_p90": [],
        "distribution_final_pnl_60d": {},
        "distribution_final_pnl_252d": {},
    }
    if daily_pnl.empty:
        return out

    pool = daily_pnl.astype(float).dropna().to_numpy()
    if pool.size < 5:
        return out

    rng = np.random.default_rng(seed)
    Hmax = max(horizon_short, horizon_long)
    paths = np.zeros((n_sims, Hmax), dtype=float)
    final60 = np.zeros(n_sims, dtype=float)
    final252 = np.zeros(n_sims, dtype=float)
    bust60 = bust252 = 0
    hit60 = hit252 = 0

    for s in range(n_sims):
        idx = rng.integers(0, pool.size, size=Hmax)
        sample = pool[idx]
        eq = np.cumsum(sample)
        paths[s, :] = eq
        b60, h60, f60 = _bust_or_target_path(
            sample,
            trailing_drawdown=trailing_drawdown,
            daily_loss_limit=daily_loss_limit,
            profit_target=profit_target,
            horizon=horizon_short,
        )
        b252, h252, f252 = _bust_or_target_path(
            sample,
            trailing_drawdown=trailing_drawdown,
            daily_loss_limit=daily_loss_limit,
            profit_target=profit_target,
            horizon=horizon_long,
        )
        if b60:
            bust60 += 1
        if b252:
            bust252 += 1
        if h60:
            hit60 += 1
        if h252:
            hit252 += 1
        # final pnl at horizon even if bust mid-path (cum at bust)
        eq60 = np.cumsum(sample[:horizon_short])
        eq252 = np.cumsum(sample[:horizon_long])
        final60[s] = eq60[-1] if len(eq60) else 0.0
        final252[s] = eq252[-1] if len(eq252) else 0.0

    nf = float(n_sims)
    out["probability_of_bust_60d_pct"] = 100.0 * bust60 / nf
    out["probability_of_bust_252d_pct"] = 100.0 * bust252 / nf
    out["probability_of_hitting_profit_target_60d_pct"] = 100.0 * hit60 / nf
    out["probability_of_hitting_profit_target_252d_pct"] = 100.0 * hit252 / nf

    p50 = np.percentile(paths, 50, axis=0)
    p10 = np.percentile(paths, 10, axis=0)
    p90 = np.percentile(paths, 90, axis=0)
    out["median_equity_curve"] = [float(x) for x in p50.tolist()]
    out["worst_case_curve_p10"] = [float(x) for x in p10.tolist()]
    out["best_case_curve_p90"] = [float(x) for x in p90.tolist()]

    def _dist(arr: np.ndarray) -> dict[str, float]:
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            "p10": float(np.percentile(arr, 10)),
            "p50": float(np.percentile(arr, 50)),
            "p90": float(np.percentile(arr, 90)),
        }

    out["distribution_final_pnl_60d"] = _dist(final60)
    out["distribution_final_pnl_252d"] = _dist(final252)
    return out
