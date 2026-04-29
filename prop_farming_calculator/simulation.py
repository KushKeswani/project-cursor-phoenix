"""Monte Carlo prop audition + Topstep-style funded economics across horizons."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from _paths import ensure_scripts_on_path

ensure_scripts_on_path()

from firm_funded_path import (
    simulate_topstep_funded_express_extended,
    simulate_topstep_funded_extended,
)
from prop_firm_sim import (
    PropEvalProfile,
    evaluate_path,
    observed_path_consistency_pressure,
    rolling_eval_stats,
)


TD_PER_MONTH = 21

HORIZONS: list[tuple[str, str, int]] = [
    ("1w", "1 Week", 5),
    ("1m", "1 Month", 1 * TD_PER_MONTH),
    ("1q", "1 Quarter", 3 * TD_PER_MONTH),
    ("6m", "6 Months", 6 * TD_PER_MONTH),
    ("12m", "12 Months", 12 * TD_PER_MONTH),
    ("18m", "18 Months", 18 * TD_PER_MONTH),
    ("24m", "24 Months", 24 * TD_PER_MONTH),
]


@dataclass
class FarmSimParams:
    n_sims: int
    seed: int
    n_accounts: int
    start_frequency: Literal["monthly", "weekly", "daily"]
    challenge_fee_usd: float
    challenge_billing: Literal["one_time", "monthly"]
    activation_fee_usd: float
    use_vps: bool
    vps_monthly_usd: float
    min_profit_per_day_usd: float
    n_qualifying_days: int
    withdraw_fraction: float
    funded_starting_balance_usd: float
    funded_trail_on_profit_usd: float
    # If set, funded leg uses Express-style gross cap per cycle + trader split (see firm_funded_path).
    funded_payout_cap_usd: float | None = None
    express_trader_first_full_usd: float = 10_000.0
    express_trader_split_after_first: float = 0.9


def run_funded_segment(
    funded_pnls: np.ndarray,
    farm: FarmSimParams,
) -> tuple[dict[str, float], float]:
    """
    Run one funded path. Returns (engine result dict, cash to trader for PnL economics).
    Classic model: trader cash = gross withdrawals. Express cap model: trader cash = total_trader_received_usd.
    """
    if farm.funded_payout_cap_usd is not None:
        r = simulate_topstep_funded_express_extended(
            funded_pnls,
            starting_balance_usd=float(farm.funded_starting_balance_usd),
            trail_on_profit_usd=float(farm.funded_trail_on_profit_usd),
            min_profit_per_day_usd=float(farm.min_profit_per_day_usd),
            n_qualifying_days=int(farm.n_qualifying_days),
            withdraw_fraction=float(farm.withdraw_fraction),
            payout_cap_usd=float(farm.funded_payout_cap_usd),
            trader_first_full_usd=float(farm.express_trader_first_full_usd),
            trader_split_after_first=float(farm.express_trader_split_after_first),
        )
        cash = float(r["total_trader_received_usd"])
        return r, cash
    r = simulate_topstep_funded_extended(
        funded_pnls,
        starting_balance_usd=float(farm.funded_starting_balance_usd),
        trail_on_profit_usd=float(farm.funded_trail_on_profit_usd),
        min_profit_per_day_usd=float(farm.min_profit_per_day_usd),
        n_qualifying_days=int(farm.n_qualifying_days),
        withdraw_fraction=float(farm.withdraw_fraction),
    )
    cash = float(r["total_withdrawn"])
    return r, cash


def _horizon_months(trading_days: int) -> float:
    return float(trading_days) / float(TD_PER_MONTH)


def eval_starts_in_horizon(
    n_accounts: int,
    start_frequency: Literal["monthly", "weekly", "daily"],
    trading_days: int,
) -> int:
    """Rough count of independent eval starts (throughput) for farm scaling."""
    hm = _horizon_months(trading_days)
    if start_frequency == "monthly":
        mult = max(1.0, float(np.ceil(hm)))
    elif start_frequency == "weekly":
        mult = max(1.0, float(np.ceil(hm * 4.345)))
    else:
        mult = max(1.0, float(np.ceil(hm * TD_PER_MONTH)))
    return int(n_accounts * mult)


def _challenge_component(
    fee: float,
    billing: Literal["one_time", "monthly"],
    horizon_months: float,
) -> float:
    if billing == "one_time":
        return float(fee)
    return float(fee) * max(1, int(np.ceil(horizon_months)))


def build_eval_rules(
    *,
    profit_target_usd: float,
    trailing_drawdown_usd: float,
    eval_window_days: int,
    daily_loss_limit_usd: float | None,
    consistency_max_best_day_fraction: float | None,
    min_trading_days: int = 1,
) -> PropEvalProfile:
    md = max(1, int(min_trading_days))
    return PropEvalProfile(
        profile_id="ui_custom",
        label="UI rules",
        profit_target_usd=float(profit_target_usd),
        trailing_drawdown_usd=float(trailing_drawdown_usd),
        daily_loss_limit_usd=daily_loss_limit_usd,
        consistency_max_best_day_fraction=consistency_max_best_day_fraction,
        min_trading_days=md,
        eval_window_days=int(eval_window_days),
        account_size_label="",
        max_contracts_note="",
    )


def _tape_contiguous(pool: np.ndarray, start: int, length: int) -> np.ndarray:
    """
    ``length`` consecutive trading days from ``pool``, wrapping at the end (circular tape).

    Used so lifecycle / sequential sims follow calendar-ordered returns like ``rolling_eval_stats``,
    instead of i.i.d. resampling with replacement (which inflated eval pass vs rolling windows).
    """
    n = int(pool.size)
    if n < 1 or length < 1:
        return np.empty(0, dtype=float)
    idx = (int(start) + np.arange(length, dtype=np.int64)) % n
    return pool[idx].astype(np.float64, copy=False)


def _random_eval_start(n_pool: int, eval_len: int, rng: np.random.Generator) -> int:
    """Uniform start index for a contiguous eval window (same support as ``rolling_eval_stats``)."""
    if n_pool < 1 or eval_len < 1:
        return 0
    el = min(int(eval_len), n_pool)
    max_start = max(0, n_pool - el)
    return int(rng.integers(0, max_start + 1))


def _funnel_bucket_from_funded(
    remaining: int,
    r: dict[str, float],
) -> str:
    """Single funded segment → mutually exclusive outcome label."""
    if remaining <= 0:
        return "pass_no_funded_days"
    breach_before = float(r.get("breach_before_first_payout", 0.0)) >= 0.5
    breach_day = r.get("breach_day_index", float("nan"))
    n_pay = float(r.get("n_payouts", 0.0))
    breached = not (isinstance(breach_day, float) and math.isnan(breach_day))
    if breach_before:
        return "funded_breach_before_first_payout"
    if breached:
        if n_pay >= 1.0:
            return "funded_breach_after_payouts"
        return "funded_breach_zero_payouts"
    return "funded_survived_segment"


def simulate_one_lifecycle(
    pool: np.ndarray,
    horizon_days: int,
    rules: PropEvalProfile,
    rng: np.random.Generator,
    farm: FarmSimParams,
) -> dict[str, float | bool | str]:
    if pool.size == 0:
        return {
            "passed_eval": False,
            "eval_outcome": "empty_pool",
            "funnel_bucket": "empty_pool",
            "payouts_usd": 0.0,
            "n_payouts": 0.0,
            "firm_fees_usd": 0.0,
            "expenses_incl_vps_usd": 0.0,
            "net_usd": 0.0,
            "roi_pct": 0.0,
            "eval_days_used": 0.0,
            "days_to_first_payout_trading": float("nan"),
            "funded_trading_days_to_first_payout": float("nan"),
            "avg_days_between_payouts": float("nan"),
        }

    H = int(horizon_days)
    hm = _horizon_months(H)
    challenge_part = _challenge_component(
        farm.challenge_fee_usd, farm.challenge_billing, hm
    )
    vps_part = farm.vps_monthly_usd * hm if farm.use_vps else 0.0

    n = int(pool.size)
    eval_len = int(min(rules.eval_window_days, H))
    # Must match ``rolling_eval_stats``: do not score a shorter "partial" eval window.
    if n < eval_len:
        return {
            "passed_eval": False,
            "eval_outcome": "insufficient_history",
            "eval_reason": "pool_shorter_than_eval_window",
            "funnel_bucket": "eval_insufficient_history",
            "payouts_usd": 0.0,
            "n_payouts": 0.0,
            "firm_fees_usd": float(
                _challenge_component(farm.challenge_fee_usd, farm.challenge_billing, hm)
            ),
            "expenses_incl_vps_usd": float(
                _challenge_component(farm.challenge_fee_usd, farm.challenge_billing, hm)
                + (farm.vps_monthly_usd * hm if farm.use_vps else 0.0)
            ),
            "net_usd": 0.0,
            "roi_pct": 0.0,
            "eval_days_used": 0.0,
            "days_to_first_payout_trading": float("nan"),
            "funded_trading_days_to_first_payout": float("nan"),
            "avg_days_between_payouts": float("nan"),
        }

    start = _random_eval_start(n, eval_len, rng)
    eval_sample = pool[start : start + eval_len].astype(np.float64, copy=True)
    out, day_idx, reason = evaluate_path(eval_sample, rules)

    passed = out == "pass"
    if out == "expire":
        days_eval = float(eval_len)
    else:
        days_eval = float(day_idx)

    payouts_usd = 0.0
    n_payouts = 0.0
    activation = 0.0
    days_to_first_payout_trading = float("nan")
    funded_trading_days_to_first_payout = float("nan")
    avg_days_between_payouts = float("nan")
    funnel_bucket = "eval_expire_unpassed"
    if out == "fail_trailing":
        funnel_bucket = "eval_fail_trailing_drawdown"
    elif out == "fail_dll":
        funnel_bucket = "eval_fail_daily_loss_limit"
    elif out == "expire":
        funnel_bucket = "eval_expire_unpassed"

    if passed:
        activation = float(farm.activation_fee_usd)
        remaining = H - int(days_eval)
        if remaining > 0:
            tape_pos = start + int(days_eval)
            funded_sample = _tape_contiguous(pool, tape_pos, remaining)
            r, payouts_usd = run_funded_segment(funded_sample, farm)
            payouts_usd = float(payouts_usd)
            n_payouts = float(r["n_payouts"])
            funnel_bucket = _funnel_bucket_from_funded(remaining, r)
            fpd = r.get("first_payout_trading_day", float("nan"))
            if not (isinstance(fpd, float) and math.isnan(fpd)) and float(fpd) > 0:
                funded_trading_days_to_first_payout = float(fpd)
                days_to_first_payout_trading = float(int(days_eval) + int(float(fpd)))
            life = float(r.get("lifespan_trading_days", 0.0))
            if n_payouts >= 2.0 and not (
                isinstance(fpd, float) and math.isnan(fpd)
            ):
                avg_days_between_payouts = (life - float(fpd)) / (n_payouts - 1.0)
        else:
            funnel_bucket = "pass_no_funded_days"

    firm_fees = challenge_part + activation
    expenses = firm_fees + vps_part
    net = payouts_usd - expenses
    denom = expenses if expenses > 1e-9 else 1.0
    roi_pct = 100.0 * net / denom

    return {
        "passed_eval": passed,
        "eval_outcome": str(out),
        "eval_reason": str(reason),
        "funnel_bucket": funnel_bucket,
        "payouts_usd": payouts_usd,
        "n_payouts": n_payouts,
        "firm_fees_usd": firm_fees,
        "expenses_incl_vps_usd": expenses,
        "net_usd": net,
        "roi_pct": float(roi_pct),
        "eval_days_used": float(days_eval),
        "days_to_first_payout_trading": float(days_to_first_payout_trading),
        "funded_trading_days_to_first_payout": float(funded_trading_days_to_first_payout),
        "avg_days_between_payouts": float(avg_days_between_payouts),
    }


FUNNEL_LABELS: dict[str, str] = {
    "eval_insufficient_history": "Audition: pool shorter than eval window (cannot score)",
    "eval_fail_trailing_drawdown": "Audition: max trailing drawdown",
    "eval_fail_daily_loss_limit": "Audition: daily loss limit",
    "eval_expire_unpassed": "Audition: window ended (no pass)",
    "pass_no_funded_days": "Passed eval, no funded days left in horizon",
    "funded_breach_before_first_payout": "Funded: breach before 1st payout",
    "funded_breach_after_payouts": "Funded: breach after ≥1 payout",
    "funded_breach_zero_payouts": "Funded: breach, zero payouts (edge)",
    "funded_survived_segment": "Funded: survived funded segment (no trail hit)",
    "empty_pool": "Empty pool",
}


def simulate_sequential_trader(
    pool: np.ndarray,
    horizon_days: int,
    rules: PropEvalProfile,
    rng: np.random.Generator,
    farm: FarmSimParams,
    *,
    challenge_fee_per_attempt: float,
    activation_fee_per_funded: float,
    use_vps: bool,
    vps_monthly_usd: float,
) -> dict[str, Any]:
    """
    One trader slot: repeat audition → (if pass) funded until trading-day budget hits zero.
    Fees: one challenge fee per audition attempt; activation per funded account opened; VPS once for horizon.
    """
    if pool.size == 0:
        return {}

    days_left = int(horizon_days)
    aud_attempts = 0
    aud_pass = 0
    aud_fail_trail = 0
    aud_fail_dll = 0
    aud_expire = 0
    funded_accounts = 0
    funded_failed_bf = 0
    funded_failed_after = 0
    funded_survived_seg = 0

    total_payout_events = 0
    total_payout_usd = 0.0
    total_challenge_fees = 0.0
    total_activation_fees = 0.0

    n = int(pool.size)
    if n < int(rules.eval_window_days):
        return {}

    cursor = int(rng.integers(0, n)) if n > 0 else 0

    while days_left > 0:
        eval_len = min(int(rules.eval_window_days), days_left, n)
        if eval_len < 1:
            break

        aud_attempts += 1
        total_challenge_fees += float(challenge_fee_per_attempt)

        eval_sample = _tape_contiguous(pool, cursor, eval_len)
        out, day_idx, _reason = evaluate_path(eval_sample, rules)

        if out == "expire":
            days_used = eval_len
        else:
            days_used = int(day_idx)

        cursor = (cursor + days_used) % n

        days_left -= days_used
        if days_left < 0:
            days_left = 0

        if out == "pass":
            aud_pass += 1
            total_activation_fees += float(activation_fee_per_funded)
            funded_accounts += 1
            if days_left <= 0:
                break
            funded_sample = _tape_contiguous(pool, cursor, days_left)
            r, trader_cash = run_funded_segment(funded_sample, farm)
            lifespan = int(float(r["lifespan_trading_days"]))
            cursor = (cursor + lifespan) % n
            days_left -= lifespan
            if days_left < 0:
                days_left = 0

            total_payout_events += int(r["n_payouts"])
            total_payout_usd += float(trader_cash)

            bd = r["breach_day_index"]
            breached = not (isinstance(bd, float) and math.isnan(bd))
            if float(r["breach_before_first_payout"]) >= 0.5:
                funded_failed_bf += 1
            elif breached:
                if float(r["n_payouts"]) >= 1.0:
                    funded_failed_after += 1
                else:
                    funded_failed_bf += 1
            else:
                funded_survived_seg += 1
        elif out == "fail_trailing":
            aud_fail_trail += 1
        elif out == "fail_dll":
            aud_fail_dll += 1
        else:
            aud_expire += 1

    hm = _horizon_months(int(horizon_days))
    vps_once = float(vps_monthly_usd) * hm if use_vps else 0.0
    total_fees = total_challenge_fees + total_activation_fees + vps_once
    net = total_payout_usd - total_fees
    roi_pct = 100.0 * net / total_fees if total_fees > 1e-9 else 0.0
    aud_failed = aud_fail_trail + aud_fail_dll + aud_expire
    funded_failed = funded_failed_bf + funded_failed_after

    return {
        "period_months": round(hm, 2),
        "audition_attempts": aud_attempts,
        "auditions_passed": aud_pass,
        "auditions_failed": aud_failed,
        "aud_fail_trailing": aud_fail_trail,
        "aud_fail_dll": aud_fail_dll,
        "aud_expire": aud_expire,
        "funded_accounts": funded_accounts,
        "funded_failed": funded_failed,
        "funded_failed_before_first": funded_failed_bf,
        "funded_failed_after_payout": funded_failed_after,
        "funded_survived_segment": funded_survived_seg,
        "total_payout_events": total_payout_events,
        "total_fees": total_fees,
        "total_payout_amount": total_payout_usd,
        "net_profit": net,
        "roi_pct": roi_pct,
    }


def build_cohort_rows(
    daily: pd.Series,
    horizon_days: int,
    rules: PropEvalProfile,
    farm: FarmSimParams,
    *,
    n_traders: int,
    base_seed: int,
) -> pd.DataFrame:
    pool = daily.astype(float).to_numpy()
    rows: list[dict[str, Any]] = []
    for i in range(n_traders):
        rng = np.random.default_rng(base_seed + 17_771 * i + horizon_days)
        row = simulate_sequential_trader(
            pool,
            horizon_days,
            rules,
            rng,
            farm,
            challenge_fee_per_attempt=float(farm.challenge_fee_usd),
            activation_fee_per_funded=float(farm.activation_fee_usd),
            use_vps=farm.use_vps,
            vps_monthly_usd=float(farm.vps_monthly_usd),
        )
        if not row:
            continue
        row["trader_id"] = f"Trader_{i + 1}"
        row["start_date"] = (
            pd.Timestamp("2020-01-02") + pd.Timedelta(days=i)
        ).date().isoformat()
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    front = [
        "period_months",
        "trader_id",
        "start_date",
        "audition_attempts",
        "auditions_passed",
        "auditions_failed",
        "aud_fail_trailing",
        "aud_fail_dll",
        "aud_expire",
        "funded_accounts",
        "funded_failed",
        "funded_failed_before_first",
        "funded_failed_after_payout",
        "funded_survived_segment",
        "total_payout_events",
        "total_fees",
        "total_payout_amount",
        "net_profit",
        "roi_pct",
    ]
    cols = [c for c in front if c in df.columns]
    rest = [c for c in df.columns if c not in cols]
    return df[cols + rest]


def run_horizon_batch(
    daily: pd.Series,
    horizon_days: int,
    rules: PropEvalProfile,
    farm: FarmSimParams,
) -> dict[str, float]:
    pool = daily.astype(float).to_numpy()

    nets: list[float] = []
    rois: list[float] = []
    payouts: list[float] = []
    firm_fees: list[float] = []
    expenses: list[float] = []
    n_pay: list[float] = []
    passed_flags: list[bool] = []
    funnel_buckets: list[str] = []
    days_first_pay: list[float] = []
    funded_days_first_pay: list[float] = []
    days_between_pay: list[float] = []
    eval_days_used_l: list[float] = []
    eval_days_on_pass: list[float] = []

    for i in range(farm.n_sims):
        rng = np.random.default_rng(farm.seed + horizon_days * 1_000_003 + i * 97_981)
        row = simulate_one_lifecycle(pool, horizon_days, rules, rng, farm)
        nets.append(float(row["net_usd"]))
        rois.append(float(row["roi_pct"]))
        payouts.append(float(row["payouts_usd"]))
        firm_fees.append(float(row["firm_fees_usd"]))
        expenses.append(float(row["expenses_incl_vps_usd"]))
        n_pay.append(float(row["n_payouts"]))
        passed_flags.append(bool(row["passed_eval"]))
        funnel_buckets.append(str(row["funnel_bucket"]))
        evu = float(row.get("eval_days_used", 0.0))
        eval_days_used_l.append(evu)
        if bool(row["passed_eval"]):
            eval_days_on_pass.append(evu)
        dfp = float(row.get("days_to_first_payout_trading", float("nan")))
        if not math.isnan(dfp):
            days_first_pay.append(dfp)
        fdfp = float(row.get("funded_trading_days_to_first_payout", float("nan")))
        if not math.isnan(fdfp):
            funded_days_first_pay.append(fdfp)
        ib = float(row.get("avg_days_between_payouts", float("nan")))
        if not math.isnan(ib):
            days_between_pay.append(ib)

    pos_roi = sum(1 for x in nets if x > 0)
    starts = eval_starts_in_horizon(
        farm.n_accounts, farm.start_frequency, horizon_days
    )
    scale = float(starts)

    def _mean(a: list[float]) -> float:
        return float(np.mean(a)) if a else 0.0

    mean_net = _mean(nets)
    mean_payout = _mean(payouts)
    mean_firm_fees = _mean(firm_fees)
    mean_exp = _mean(expenses)
    mean_n_pay = _mean(n_pay)
    pass_rate = 100.0 * sum(passed_flags) / farm.n_sims if farm.n_sims else 0.0
    hm_h = _horizon_months(int(horizon_days))
    avg_monthly_payout_usd = mean_payout / hm_h if hm_h > 1e-9 else 0.0
    mean_days_to_first_payout = _mean(days_first_pay) if days_first_pay else float("nan")
    mean_funded_days_to_first_payout = (
        _mean(funded_days_first_pay) if funded_days_first_pay else float("nan")
    )
    mean_days_between_payouts = _mean(days_between_pay) if days_between_pay else float("nan")
    pct_sims_with_payout = (
        100.0 * len(days_first_pay) / farm.n_sims if farm.n_sims else 0.0
    )
    mean_eval_days_used = _mean(eval_days_used_l)
    mean_days_to_pass_conditional = (
        _mean(eval_days_on_pass) if eval_days_on_pass else float("nan")
    )

    n_f = float(farm.n_sims) if farm.n_sims else 1.0

    fc = Counter(funnel_buckets)
    out_funnel: dict[str, float] = {}
    for k in FUNNEL_LABELS:
        cnt = float(fc.get(k, 0))
        out_funnel[f"funnel_pct__{k}"] = 100.0 * cnt / n_f

    return {
        "horizon_trading_days": float(horizon_days),
        "eval_starts_scaled": float(starts),
        "audition_pass_pct": pass_rate,
        "avg_payout_events_per_trader": mean_n_pay,
        "avg_prop_firm_fees_per_trader": mean_firm_fees,
        "avg_total_payouts_per_trader": mean_payout,
        "avg_total_expenses_per_trader": mean_exp,
        "avg_net_profit_per_trader": mean_net,
        "avg_roi_pct": _mean(rois),
        "pct_positive_roi": 100.0 * pos_roi / farm.n_sims if farm.n_sims else 0.0,
        "farm_est_total_fees": mean_firm_fees * scale,
        "farm_est_net": mean_net * scale,
        "avg_monthly_payout_usd": float(avg_monthly_payout_usd),
        "mean_days_to_first_payout_trading": float(mean_days_to_first_payout),
        "mean_funded_trading_days_to_first_payout": float(mean_funded_days_to_first_payout),
        "mean_days_between_payouts_conditional": float(mean_days_between_payouts),
        "pct_simulations_with_any_payout": float(pct_sims_with_payout),
        "mean_eval_days_used_single_lifecycle": float(mean_eval_days_used),
        "mean_days_to_pass_eval_conditional_mc": float(mean_days_to_pass_conditional),
        **out_funnel,
    }


def _mc_aliases_from_rolling(roll: dict[str, float]) -> dict[str, float]:
    """
    Populate legacy mc_eval_* keys from contiguous rolling windows (start every day).
    Keeps pool_diagnostics.csv column names stable for downstream tools.
    """
    pp = roll.get("rolling_pass_pct", 0.0)
    fp = roll.get("rolling_fail_pct", 0.0)
    decided = (pp + fp) / 100.0 * roll.get("rolling_windows", 0.0)
    pass_n = (pp / 100.0) * roll.get("rolling_windows", 0.0)
    prob = 100.0 * pass_n / decided if decided > 1e-9 else 0.0
    m: dict[str, float] = {
        "mc_eval_pass_pct": float(pp),
        "mc_eval_fail_pct": float(roll.get("rolling_fail_pct", 0.0)),
        "mc_eval_expire_pct": float(roll.get("rolling_expire_pct", 0.0)),
        "mc_eval_prob_pass_given_pass_or_bust_pct": float(prob),
        "mc_eval_pct_runs_dd_within_85pct_of_trail": float(
            roll.get("rolling_pct_windows_dd_within_85pct_of_trail", 0.0)
        ),
        "mc_eval_mean_days_to_pass": float(roll.get("rolling_mean_days_to_pass", 0.0)),
        "mc_eval_median_days_to_pass": float(roll.get("rolling_median_days_to_pass", 0.0)),
        "mc_eval_mean_days_to_fail": float(roll.get("rolling_mean_days_to_fail", 0.0)),
        "mc_eval_median_days_to_fail": float(roll.get("rolling_median_days_to_fail", 0.0)),
        "mc_eval_mean_max_dd_during_window_usd": float(
            roll.get("rolling_mean_max_dd_during_window_usd", 0.0)
        ),
    }
    for q in (10, 25, 50, 75, 90):
        m[f"mc_eval_p{q}_days_to_pass"] = float(
            roll.get(f"rolling_p{q}_days_to_pass", 0.0)
        )
        m[f"mc_eval_p{q}_days_to_fail"] = float(
            roll.get(f"rolling_p{q}_days_to_fail", 0.0)
        )
        m[f"mc_eval_p{q}_max_dd_during_window_usd"] = float(
            roll.get(f"rolling_p{q}_max_dd_during_window_usd", 0.0)
        )
    return m


def pool_diagnostics(
    daily: pd.Series,
    rules: PropEvalProfile,
    *,
    n_sims: int,
    seed: int,
) -> dict[str, float]:
    """Observed stats + contiguous eval: every start day, length = eval_window_days (no bootstrap)."""
    del n_sims, seed  # retained for API compatibility with cli.py
    if daily.empty:
        return {}
    obs = observed_path_consistency_pressure(daily)
    roll = rolling_eval_stats(daily, rules)
    out: dict[str, float] = {}
    for k, v in obs.items():
        out[f"obs_{k}"] = float(v)
    for k, v in roll.items():
        out[f"roll_{k}"] = float(v)
    out.update(_mc_aliases_from_rolling(roll))
    return out
