"""Prop evaluation path simulator + pool diagnostics (bootstrap MC, rolling windows)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PropEvalProfile:
    profile_id: str
    label: str
    profit_target_usd: float
    trailing_drawdown_usd: float
    daily_loss_limit_usd: float | None
    consistency_max_best_day_fraction: float | None
    min_trading_days: int
    eval_window_days: int
    account_size_label: str
    max_contracts_note: str


def evaluate_path(
    pnls: np.ndarray,
    rules: PropEvalProfile,
) -> tuple[str, int, str]:
    """
    Walk a fixed-length eval window (already sampled). Returns:
    (outcome, day_index, reason) where outcome is pass | fail_trailing | fail_dll | expire,
    day_index is 1-based trading day when outcome locks in (or window length on expire).
    """
    if pnls.size == 0:
        return "expire", 0, "empty"

    cum = 0.0
    peak = 0.0
    best_day = float("-inf")
    n = int(pnls.size)
    min_days = max(1, int(rules.min_trading_days))

    for i in range(n):
        day = i + 1
        pnl = float(pnls[i])
        dll = rules.daily_loss_limit_usd
        if dll is not None and pnl <= -float(dll) + 1e-12:
            return "fail_dll", day, "daily_loss_limit"

        cum += pnl
        peak = max(peak, cum)
        best_day = max(best_day, pnl)
        dd = peak - cum
        if dd > float(rules.trailing_drawdown_usd) + 1e-9:
            return "fail_trailing", day, "trailing_drawdown"

        if day >= min_days and cum >= float(rules.profit_target_usd) - 1e-9:
            frac = rules.consistency_max_best_day_fraction
            if frac is None:
                return "pass", day, "profit_target"
            if cum <= 1e-9:
                continue
            if best_day / cum <= float(frac) + 1e-9:
                return "pass", day, "profit_target_consistency"

    return "expire", n, "eval_window"


def observed_path_consistency_pressure(daily: pd.Series) -> dict[str, float]:
    if daily.empty:
        return {
            "best_day_usd": 0.0,
            "worst_day_usd": 0.0,
            "observed_max_best_day_to_equity_ratio": 0.0,
        }
    arr = daily.astype(float).to_numpy()
    total = float(np.sum(arr))
    best = float(np.max(arr))
    worst = float(np.min(arr))
    denom = abs(total) if abs(total) > 1e-9 else 1.0
    return {
        "best_day_usd": best,
        "worst_day_usd": worst,
        "observed_max_best_day_to_equity_ratio": best / denom,
    }


def rolling_eval_stats(daily: pd.Series, rules: PropEvalProfile) -> dict[str, float]:
    """
    For every start index t, run evaluate_path on the contiguous window
    daily[t : t + eval_window_days]. No bootstrap — uses actual calendar order.
    """
    w = int(rules.eval_window_days)
    arr = daily.astype(float).to_numpy()
    n = arr.size
    empty = {
        "rolling_pass_pct": 0.0,
        "rolling_fail_pct": 0.0,
        "rolling_expire_pct": 0.0,
        "rolling_bust_pct": 0.0,
        "rolling_windows": 0.0,
        "rolling_mean_days_to_pass": 0.0,
        "rolling_median_days_to_pass": 0.0,
        "rolling_mean_days_to_fail": 0.0,
        "rolling_median_days_to_fail": 0.0,
        "rolling_mean_max_dd_during_window_usd": 0.0,
        "rolling_pct_windows_dd_within_85pct_of_trail": 0.0,
    }
    if n < w or w < 1:
        return dict(empty)

    pass_n = fail_n = exp_n = 0
    windows = 0
    days_pass: list[float] = []
    days_fail: list[float] = []
    max_dds: list[float] = []
    trail = float(rules.trailing_drawdown_usd)
    thresh = 0.85 * trail if trail > 0 else 0.0
    near_trail = 0

    for start in range(0, n - w + 1):
        chunk = arr[start : start + w]
        out, day_idx, _r = evaluate_path(chunk, rules)
        windows += 1
        mdd = _max_dd_during(chunk, rules)
        max_dds.append(mdd)
        if thresh > 0 and mdd >= thresh - 1e-9:
            near_trail += 1
        if out == "pass":
            pass_n += 1
            days_pass.append(float(day_idx))
        elif out == "expire":
            exp_n += 1
        else:
            fail_n += 1
            days_fail.append(float(day_idx))

    wf = float(windows) if windows else 1.0
    bust = fail_n  # trail + dll

    def _pctiles(xs: list[float], prefix: str, d: dict[str, float]) -> None:
        if not xs:
            for q in (10, 25, 50, 75, 90):
                d[f"rolling_p{q}_{prefix}"] = 0.0
            return
        a = np.array(xs, dtype=float)
        for q in (10, 25, 50, 75, 90):
            d[f"rolling_p{q}_{prefix}"] = float(np.percentile(a, q))

    out: dict[str, float] = {
        "rolling_pass_pct": 100.0 * pass_n / wf,
        "rolling_fail_pct": 100.0 * fail_n / wf,
        "rolling_expire_pct": 100.0 * exp_n / wf,
        "rolling_bust_pct": 100.0 * bust / wf,
        "rolling_windows": float(windows),
        "rolling_mean_days_to_pass": float(np.mean(days_pass)) if days_pass else 0.0,
        "rolling_median_days_to_pass": float(np.median(days_pass)) if days_pass else 0.0,
        "rolling_mean_days_to_fail": float(np.mean(days_fail)) if days_fail else 0.0,
        "rolling_median_days_to_fail": float(np.median(days_fail)) if days_fail else 0.0,
        "rolling_mean_max_dd_during_window_usd": float(np.mean(max_dds)) if max_dds else 0.0,
        "rolling_pct_windows_dd_within_85pct_of_trail": 100.0 * near_trail / wf,
    }
    _pctiles(days_pass, "days_to_pass", out)
    _pctiles(days_fail, "days_to_fail", out)
    if max_dds:
        md = np.array(max_dds, dtype=float)
        for q in (10, 25, 50, 75, 90):
            out[f"rolling_p{q}_max_dd_during_window_usd"] = float(np.percentile(md, q))
    else:
        for q in (10, 25, 50, 75, 90):
            out[f"rolling_p{q}_max_dd_during_window_usd"] = 0.0
    return out


def _max_dd_during(pnls: np.ndarray, rules: PropEvalProfile) -> float:
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        cum += float(pnl)
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
        dll = rules.daily_loss_limit_usd
        if dll is not None and float(pnl) <= -float(dll) + 1e-12:
            break
        if peak - cum > float(rules.trailing_drawdown_usd) + 1e-9:
            break
    return float(max_dd)


def monte_carlo_eval_topstep_deep(
    pool: np.ndarray,
    rules: PropEvalProfile,
    *,
    n_sims: int,
    seed: int,
    eval_days: int,
) -> dict[str, float | int]:
    """i.i.d. bootstrap eval windows; distribution of pass / fail / expire and timing."""
    if pool.size == 0 or n_sims < 1:
        return {"n_sims": int(n_sims)}

    rng = np.random.default_rng(int(seed))
    ed = int(min(eval_days, int(rules.eval_window_days)))
    if ed < 1:
        ed = int(rules.eval_window_days)

    pass_n = fail_n = exp_n = 0
    days_pass: list[float] = []
    days_fail: list[float] = []
    max_dds: list[float] = []
    near_trail = 0

    trail = float(rules.trailing_drawdown_usd)
    thresh = 0.85 * trail if trail > 0 else 0.0

    for _ in range(int(n_sims)):
        sample = pool[rng.integers(0, pool.size, size=ed)]
        out, day_idx, _reason = evaluate_path(sample, rules)
        mdd = _max_dd_during(sample, rules)
        max_dds.append(mdd)
        if thresh > 0 and mdd >= thresh - 1e-9:
            near_trail += 1

        if out == "pass":
            pass_n += 1
            days_pass.append(float(day_idx))
        elif out == "expire":
            exp_n += 1
        else:
            fail_n += 1
            days_fail.append(float(day_idx))

    nf = float(n_sims)
    pass_pct = 100.0 * pass_n / nf
    fail_pct = 100.0 * fail_n / nf
    expire_pct = 100.0 * exp_n / nf
    decided = pass_n + fail_n
    prob_cond = 100.0 * pass_n / decided if decided > 0 else 0.0

    fixed: dict[str, float | int] = {
        "n_sims": int(n_sims),
        "mc_eval_pass_pct": pass_pct,
        "mc_eval_fail_pct": fail_pct,
        "mc_eval_expire_pct": expire_pct,
        "mc_eval_prob_pass_given_pass_or_bust_pct": prob_cond,
        "mc_eval_pct_runs_dd_within_85pct_of_trail": 100.0 * near_trail / nf,
    }
    for q in (10, 25, 50, 75, 90):
        fixed[f"mc_eval_p{q}_days_to_pass"] = float(
            np.percentile(days_pass, q) if days_pass else 0.0
        )
        fixed[f"mc_eval_p{q}_days_to_fail"] = float(
            np.percentile(days_fail, q) if days_fail else 0.0
        )
    fixed["mc_eval_mean_days_to_pass"] = float(np.mean(days_pass)) if days_pass else 0.0
    fixed["mc_eval_median_days_to_pass"] = float(np.median(days_pass)) if days_pass else 0.0
    fixed["mc_eval_mean_days_to_fail"] = float(np.mean(days_fail)) if days_fail else 0.0
    fixed["mc_eval_median_days_to_fail"] = float(np.median(days_fail)) if days_fail else 0.0
    if max_dds:
        md = np.array(max_dds, dtype=float)
        fixed["mc_eval_mean_max_dd_during_window_usd"] = float(np.mean(md))
        for q in (10, 25, 50, 75, 90):
            fixed[f"mc_eval_p{q}_max_dd_during_window_usd"] = float(np.percentile(md, q))
    return fixed
