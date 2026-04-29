"""Section 5: prop evaluation + funded simulation + risk proximity on history."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from firm_funded_path import simulate_topstep_funded_extended
from prop_firm_sim import PropEvalProfile, evaluate_path, rolling_eval_stats

from ._utils import safe_div


def _profile_from_params(p: dict[str, Any]) -> PropEvalProfile:
    dll = p.get("daily_loss_limit")
    cons = p.get("consistency_rule")
    return PropEvalProfile(
        profile_id="dashboard",
        label="dashboard",
        profit_target_usd=float(p["profit_target"]),
        trailing_drawdown_usd=float(p["trailing_drawdown"]),
        daily_loss_limit_usd=float(dll) if dll is not None else None,
        consistency_max_best_day_fraction=float(cons) if cons is not None else None,
        min_trading_days=max(1, int(p.get("eval_min_trading_days", 1))),
        eval_window_days=int(p.get("eval_window_days", 60)),
        account_size_label="",
        max_contracts_note="",
    )


def _observed_prop_risk(
    daily_pnl: pd.Series,
    *,
    trailing_drawdown: float,
    daily_loss_limit: float | None,
) -> dict[str, Any]:
    """Apply prop-style cumulative profit trail + DLL proximity to historical days."""
    out = {
        "pct_days_near_dll": 0.0,
        "pct_days_near_trailing_dd": 0.0,
        "avg_buffer_to_trailing_dd_usd": 0.0,
        "n_days": 0,
    }
    if daily_pnl.empty:
        return out
    cum = daily_pnl.astype(float).cumsum()
    peak = cum.cummax()
    dd = peak - cum
    n = len(daily_pnl)
    out["n_days"] = n
    near_t = (dd >= 0.9 * float(trailing_drawdown)).sum()
    out["pct_days_near_trailing_dd"] = 100.0 * safe_div(float(near_t), float(n))
    buf = float(trailing_drawdown) - dd
    pos = buf[dd > 1e-9]
    out["avg_buffer_to_trailing_dd_usd"] = float(pos.mean()) if not pos.empty else float(buf.mean())

    if daily_loss_limit is not None and float(daily_loss_limit) > 0:
        dll = float(daily_loss_limit)
        losses = -daily_pnl.astype(float)
        near_d = (losses >= 0.9 * dll) & (daily_pnl < 0)
        out["pct_days_near_dll"] = 100.0 * safe_div(float(near_d.sum()), float(n))
    return out


def compute_prop_metrics(
    daily_pnl: pd.Series,
    prop_params: dict[str, Any] | None,
    *,
    n_bootstrap: int = 1000,
    seed: int = 42,
    funded_horizon_days: int = 120,
) -> dict[str, Any]:
    del n_bootstrap, seed  # eval uses every start-day window; args kept for API compatibility
    empty = {
        "evaluation": {},
        "funded": {},
        "risk_proximity_history": {},
        "note": "prop_params omitted or empty",
    }
    if not prop_params:
        return empty
    for req in ("profit_target", "trailing_drawdown"):
        if req not in prop_params:
            return {**empty, "note": f"missing required prop_params.{req}"}

    rules = _profile_from_params(prop_params)
    pool = daily_pnl.astype(float).dropna().to_numpy()
    W = int(rules.eval_window_days)
    if pool.size < W:
        return {
            "evaluation": {},
            "funded": {},
            "risk_proximity_history": _observed_prop_risk(
                daily_pnl,
                trailing_drawdown=float(prop_params["trailing_drawdown"]),
                daily_loss_limit=prop_params.get("daily_loss_limit"),
            ),
            "note": f"need at least {W} daily samples (eval_window_days)",
        }

    roll = rolling_eval_stats(daily_pnl, rules)
    n = pool.size

    first_pay_days: list[float] = []
    payout_sizes: list[float] = []
    payout_gaps: list[float] = []
    lifespans: list[float] = []
    total_payouts_list: list[float] = []

    start_bal = float(prop_params.get("starting_balance_usd", 50_000))
    fund_trail = float(prop_params.get("funded_trailing_drawdown", rules.trailing_drawdown_usd))
    min_profit = float(prop_params.get("min_profit_per_day_usd", 150.0))
    n_qual = int(prop_params.get("min_days_for_payout", 5))
    withdraw_frac = float(prop_params.get("withdraw_fraction", 0.5))

    for start in range(0, n - W + 1):
        chunk = pool[start : start + W]
        outc, day_idx, _reason = evaluate_path(chunk, rules)
        if outc != "pass":
            continue
        next_idx = start + int(day_idx)
        rem = min(funded_horizon_days, n - next_idx)
        if rem < 1:
            continue
        funded_sample = pool[next_idx : next_idx + rem]
        fr = simulate_topstep_funded_extended(
            funded_sample,
            starting_balance_usd=start_bal,
            trail_on_profit_usd=fund_trail,
            min_profit_per_day_usd=min_profit,
            n_qualifying_days=n_qual,
            withdraw_fraction=withdraw_frac,
        )
        npy = int(fr["n_payouts"])
        total_payouts_list.append(float(npy))
        lifespans.append(float(fr["lifespan_trading_days"]))
        if npy > 0 and not np.isnan(fr["first_payout_trading_day"]):
            first_pay_days.append(float(day_idx) + float(fr["first_payout_trading_day"]))
            avg_pay = fr["total_withdrawn"] / max(npy, 1)
            payout_sizes.append(float(avg_pay))
            life = float(fr["lifespan_trading_days"])
            fp = float(fr["first_payout_trading_day"])
            if npy >= 2 and life > fp:
                payout_gaps.append((life - fp) / (npy - 1))

    ev = {
        "pass_rate_pct": float(roll["rolling_pass_pct"]),
        "bust_rate_pct": float(roll["rolling_fail_pct"]),
        "expire_rate_pct": float(roll["rolling_expire_pct"]),
        "avg_time_to_pass_days": float(roll["rolling_mean_days_to_pass"]),
        "distribution_pass_times": {
            "p10": float(roll["rolling_p10_days_to_pass"]),
            "p25": float(roll["rolling_p25_days_to_pass"]),
            "p50": float(roll["rolling_p50_days_to_pass"]),
            "p75": float(roll["rolling_p75_days_to_pass"]),
            "p90": float(roll["rolling_p90_days_to_pass"]),
        },
        "distribution_bust_times": {
            "p50": float(roll["rolling_p50_days_to_fail"]),
        },
    }

    fd = {
        "avg_time_to_first_payout_days": float(np.mean(first_pay_days)) if first_pay_days else 0.0,
        "avg_payout_size_usd": float(np.mean(payout_sizes)) if payout_sizes else 0.0,
        "payout_frequency_days": float(np.mean(payout_gaps)) if payout_gaps else 0.0,
        "avg_total_payouts_per_account": float(np.mean(total_payouts_list)) if total_payouts_list else 0.0,
        "avg_account_lifespan_days": float(np.mean(lifespans)) if lifespans else 0.0,
        "conditional_on_pass_windows": True,
        "funded_follows_contiguous_calendar_after_pass": True,
    }

    risk = _observed_prop_risk(
        daily_pnl,
        trailing_drawdown=float(prop_params["trailing_drawdown"]),
        daily_loss_limit=prop_params.get("daily_loss_limit"),
    )

    return {
        "evaluation": ev,
        "funded": fd,
        "risk_proximity_history": risk,
        "rolling_eval_windows": int(roll["rolling_windows"]),
        "method": "contiguous_start_every_day",
    }
