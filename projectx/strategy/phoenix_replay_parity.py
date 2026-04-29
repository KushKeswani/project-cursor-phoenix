"""
Replay parity helpers (no Gateway / executor).

Mirrors ``projectx.main`` behavior for whether a **fresh engine hit** would proceed
when ``phoenix_entry_order`` is **limit** (stop @ engine ``entry_price``): see
``entry_breakout_stop_valid`` vs last bar close — same logic as ``main.py`` before
``execute_dollar_risk_bracket``.

This does **not** simulate arm orders, risk checks, or partial-bar Gateway quirks.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

import pandas as pd

from .phoenix_auto import entry_breakout_stop_valid


def live_stop_entry_eligibility(
    inst: str,
    trade: dict[str, Any],
    bars: Optional[pd.DataFrame],
    tick_size: float,
    *,
    phoenix_limit_entry: bool,
) -> Tuple[bool, str]:
    """
    Returns (would_check_pass, reason).

    When ``phoenix_limit_entry`` is False (market entry), live skips stop-validity;
    we return (True, \"market_entry_no_stop_check\").

    When True, we require positive ``entry_price`` and last bar close vs trigger,
    matching ``main.py``'s ``Phoenix skip API entry`` branch.
    """
    _ = inst
    if not phoenix_limit_entry:
        return True, "market_entry_no_stop_check"
    if bars is None or len(bars) < 1:
        return False, "no_bars"
    try:
        limit_px = float(trade.get("entry_price", 0) or 0)
    except (TypeError, ValueError):
        limit_px = 0.0
    if limit_px <= 0:
        return False, "invalid_entry_price"
    last_px = float(bars["close"].iloc[-1])
    side = str(trade.get("direction", ""))
    if not entry_breakout_stop_valid(side, limit_px, last_px, float(tick_size)):
        return False, "entry_breakout_stop_invalid"
    return True, "ok"


def filter_hits_with_live_stop_gate(
    hits: list[tuple[str, dict[str, Any], float, float]],
    bars_by_inst: dict[str, pd.DataFrame],
    tick_sizes: dict[str, float],
    *,
    phoenix_limit_entry: bool,
) -> tuple[list[tuple[str, dict[str, Any], float, float]], dict[str, int]]:
    """Drop hits live would skip before bracket; return (kept, skip_counts_by_reason)."""
    skips: dict[str, int] = {}
    kept: list[tuple[str, dict[str, Any], float, float]] = []
    for inst, tr, r_usd, rw_usd in hits:
        tsz = float(tick_sizes.get(inst, 0.25))
        ok, reason = live_stop_entry_eligibility(
            inst,
            tr,
            bars_by_inst.get(inst),
            tsz,
            phoenix_limit_entry=phoenix_limit_entry,
        )
        if ok:
            kept.append((inst, tr, r_usd, rw_usd))
        else:
            skips[reason] = skips.get(reason, 0) + 1
    return kept, skips
