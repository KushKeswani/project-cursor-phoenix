"""Locked strategy configs for CL, MGC, MNQ, YM range breakout algos."""

from engine.fast_engine import FastConfig

# MGC trades 12:00-13:00
MGC_TRADE_START = 12 * 60 + 0
MGC_TRADE_END = 13 * 60 + 0

# Manual / fixed MGC exits (no ATR at the desk). OOS sweep 2023-01 → 2025-06 vs `get_config("MGC")`
# ATR baseline: ~25.4k total ticks, PF ~5.26, maxDD ~692 ticks.
# Fixed 3:1, trail off: SL 30 / PT 90 ≈ ~26.5k ticks, PF ~5.6, maxDD ~284 — near median loss (~29 ticks), round numbers.
# Tighter: 28/84 or 18/54 (higher PF, smaller risk $). Wider: 50/150 (higher OOS total ticks, larger DD).
MGC_MANUAL_FIXED_SL_TICKS = 30
MGC_MANUAL_FIXED_PT_TICKS = 90

# CL: 10:30-12:30 peak liquidity window (slippage-robust, ~941 trades OOS)
CL_TRADE_START = 10 * 60 + 30
CL_TRADE_END = 12 * 60 + 30

# MNQ: 11:00-13:00 peak liquidity (sweep: $257k OOS at 0-tick, $244k at 3-tick, PF 3.14/2.94)
MNQ_TRADE_START = 11 * 60 + 0
MNQ_TRADE_END = 13 * 60 + 0

# YM: 11:00-13:00 peak liquidity (sweep: $267k OOS at 0-tick, $250k at 3-tick, PF 7.50/6.35)
YM_TRADE_START = 11 * 60 + 0
YM_TRADE_END = 13 * 60 + 0


def get_config(instrument: str, slippage_robust: bool = False) -> FastConfig:
    """Return FastConfig for the locked strategy.

    slippage_robust is retained for backward compatibility but CL now uses
    the narrow window (10:30-12:30) by default.
    """
    configs = {
        "CL": FastConfig(
            instrument="CL",
            bar_minutes=12,
            entry_tick_offset=0,
            range_start_minutes=9 * 60 + 0,
            range_end_minutes=9 * 60 + 30,
            trade_start_minutes=CL_TRADE_START,
            trade_end_minutes=CL_TRADE_END,
            close_all_minutes=16 * 60 + 55,
            stop_loss_ticks=45,
            profit_target_ticks=135,
            breakeven_on=True,
            breakeven_after_ticks=30,
            breakeven_offset=4,
            trail_on=True,
            trail_by_ticks=10,
            trail_start_after_ticks=15,
            trail_frequency=5,
            excluded_weekdays={5, 6},
            max_entries_per_day=2,
        ),
        "MGC": FastConfig(
            instrument="MGC",
            bar_minutes=8,
            entry_tick_offset=15,
            range_start_minutes=9 * 60 + 0,
            range_end_minutes=9 * 60 + 30,
            trade_start_minutes=MGC_TRADE_START,
            trade_end_minutes=MGC_TRADE_END,
            close_all_minutes=16 * 60 + 55,
            stop_loss_ticks=0,
            profit_target_ticks=0,
            breakeven_on=False,
            breakeven_after_ticks=33,
            breakeven_offset=3,
            trail_on=True,
            trail_by_ticks=1.2,
            trail_start_after_ticks=999,
            trail_frequency=50,
            excluded_weekdays={5, 6},
            max_entries_per_day=1,
            atr_adaptive=True,
            sl_atr_mult=1.0,
            pt_atr_mult=3.0,
            trail_atr_mult=1.2,
        ),
        "MNQ": FastConfig(
            instrument="MNQ",
            bar_minutes=5,
            entry_tick_offset=2,
            range_start_minutes=9 * 60 + 35,
            range_end_minutes=9 * 60 + 55,
            trade_start_minutes=MNQ_TRADE_START,
            trade_end_minutes=MNQ_TRADE_END,
            close_all_minutes=16 * 60 + 55,
            stop_loss_ticks=80,
            profit_target_ticks=240,
            breakeven_on=False,
            breakeven_after_ticks=30,
            breakeven_offset=0,
            trail_on=False,
            trail_by_ticks=10,
            trail_start_after_ticks=999,
            trail_frequency=10,
            excluded_weekdays={5, 6},
            max_entries_per_day=2,
        ),
        "YM": FastConfig(
            instrument="YM",
            bar_minutes=5,
            entry_tick_offset=5,
            range_start_minutes=9 * 60 + 0,
            range_end_minutes=9 * 60 + 30,
            trade_start_minutes=YM_TRADE_START,
            trade_end_minutes=YM_TRADE_END,
            close_all_minutes=16 * 60 + 55,
            stop_loss_ticks=25,
            profit_target_ticks=75,
            breakeven_on=True,
            breakeven_after_ticks=82,
            breakeven_offset=1,
            trail_on=True,
            trail_by_ticks=25,
            trail_start_after_ticks=31,
            trail_frequency=5,
            excluded_weekdays={5, 6},
            max_entries_per_day=2,
        ),
    }
    if instrument not in configs:
        raise ValueError(f"Unknown instrument: {instrument}")
    return configs[instrument]
