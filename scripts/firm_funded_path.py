"""Funded-account path simulation (classic withdrawal vs Express-style capped gross + split)."""

from __future__ import annotations

import math

import numpy as np


def simulate_topstep_funded_extended(
    funded_pnls: np.ndarray,
    *,
    starting_balance_usd: float,
    trail_on_profit_usd: float,
    min_profit_per_day_usd: float,
    n_qualifying_days: int,
    withdraw_fraction: float,
) -> dict[str, float]:
    """
    Classic model: trailing drawdown on account balance; payout when `n_qualifying_days`
    consecutive days each have pnl >= min_profit. Gross withdrawal = withdraw_fraction
    of profits above starting balance; balance reduced by gross; trader receives all gross.
    """
    balance = float(starting_balance_usd)
    start = float(starting_balance_usd)
    peak = balance
    qual_streak = 0
    n_payouts = 0
    total_withdrawn = 0.0
    breach_day_index = float("nan")
    first_payout_trading_day = float("nan")
    n = int(funded_pnls.size)

    for i in range(n):
        day = i + 1
        pnl = float(funded_pnls[i])
        balance += pnl
        peak = max(peak, balance)
        if peak - balance > float(trail_on_profit_usd) + 1e-9:
            breach_day_index = float(day)
            break

        if pnl >= float(min_profit_per_day_usd):
            qual_streak += 1
        else:
            qual_streak = 0

        if qual_streak >= int(n_qualifying_days):
            profit_above = max(0.0, balance - start)
            gross = float(withdraw_fraction) * profit_above
            if gross > 1e-6:
                balance -= gross
                total_withdrawn += gross
                n_payouts += 1
                if math.isnan(first_payout_trading_day):
                    first_payout_trading_day = float(day)
            qual_streak = 0

    breach_before = not math.isnan(breach_day_index) and n_payouts < 0.5
    return {
        "n_payouts": float(n_payouts),
        "total_withdrawn": float(total_withdrawn),
        "lifespan_trading_days": float(n if math.isnan(breach_day_index) else int(breach_day_index)),
        "breach_day_index": breach_day_index,
        "breach_before_first_payout": 1.0 if breach_before else 0.0,
        "first_payout_trading_day": first_payout_trading_day,
    }


def simulate_topstep_funded_express_extended(
    funded_pnls: np.ndarray,
    *,
    starting_balance_usd: float,
    trail_on_profit_usd: float,
    min_profit_per_day_usd: float,
    n_qualifying_days: int,
    withdraw_fraction: float,
    payout_cap_usd: float,
    trader_first_full_usd: float,
    trader_split_after_first: float,
) -> dict[str, float]:
    """Express-style: gross per cycle capped; trader gets 100% until cumulative trader hits first_full, then split."""
    balance = float(starting_balance_usd)
    start = float(starting_balance_usd)
    peak = balance
    qual_streak = 0
    n_payouts = 0.0
    total_trader_received_usd = 0.0
    total_gross_withdrawn = 0.0
    breach_day_index = float("nan")
    first_payout_trading_day = float("nan")
    n = int(funded_pnls.size)
    split = float(trader_split_after_first)
    cap = float(payout_cap_usd)
    first_full = float(trader_first_full_usd)

    for i in range(n):
        day = i + 1
        pnl = float(funded_pnls[i])
        balance += pnl
        peak = max(peak, balance)
        if peak - balance > float(trail_on_profit_usd) + 1e-9:
            breach_day_index = float(day)
            break

        if pnl >= float(min_profit_per_day_usd):
            qual_streak += 1
        else:
            qual_streak = 0

        if qual_streak >= int(n_qualifying_days):
            profit_above = max(0.0, balance - start)
            desired = float(withdraw_fraction) * profit_above
            gross = min(cap, desired) if cap > 0 else desired
            if gross > 1e-6:
                balance -= gross
                total_gross_withdrawn += gross
                n_payouts += 1.0
                if math.isnan(first_payout_trading_day):
                    first_payout_trading_day = float(day)
                remaining_full = max(0.0, first_full - total_trader_received_usd)
                at_full = min(gross, remaining_full)
                rest = gross - at_full
                total_trader_received_usd += at_full + rest * split
            qual_streak = 0

    breach_before = not math.isnan(breach_day_index) and n_payouts < 0.5
    return {
        "n_payouts": float(n_payouts),
        "total_withdrawn": float(total_gross_withdrawn),
        "total_trader_received_usd": float(total_trader_received_usd),
        "lifespan_trading_days": float(n if math.isnan(breach_day_index) else int(breach_day_index)),
        "breach_day_index": breach_day_index,
        "breach_before_first_payout": 1.0 if breach_before else 0.0,
        "first_payout_trading_day": first_payout_trading_day,
    }
