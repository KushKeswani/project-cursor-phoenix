"""Declarative strategy research specs for CL/MGC/MNQ/YM sweeps."""

from __future__ import annotations

from dataclasses import dataclass


INSTRUMENTS = ["CL", "MGC", "MNQ", "YM"]

SESSION_WINDOWS = {
    "full_day": {
        "CL": (9 * 60 + 30, 15 * 60 + 30),
        "MGC": (9 * 60 + 30, 15 * 60 + 30),
        "MNQ": (9 * 60 + 30, 15 * 60 + 30),
        "YM": (9 * 60 + 30, 15 * 60 + 30),
    },
    "after_1pm": {
        "CL": (13 * 60, 16 * 60 + 15),
        "MGC": (13 * 60, 16 * 60 + 15),
        "MNQ": (13 * 60, 16 * 60 + 15),
        "YM": (13 * 60, 16 * 60 + 15),
    },
}


@dataclass(frozen=True)
class FamilySpec:
    """Config grid for one strategy family."""

    name: str
    description: str
    grid: dict[str, list]


FAMILY_SPECS = {
    "fixed_stop_target": FamilySpec(
        name="fixed_stop_target",
        description="Static stop/target in ticks; optional breakeven and trailing.",
        grid={
            "bar_minutes": [5, 8, 12],
            "entry_tick_offset": [0, 2, 5],
            "stop_loss_ticks": [20, 35, 50, 80],
            "rr_multiple": [1.8, 2.5, 3.0],
            "max_entries_per_day": [1, 2],
            "breakeven_on": [False, True],
            "trail_on": [False, True],
        },
    ),
    "atr_volatility": FamilySpec(
        name="atr_volatility",
        description="ATR-adaptive stop/target/trailing with volatility scaling.",
        grid={
            "bar_minutes": [5, 8, 12],
            "entry_tick_offset": [0, 2, 5, 8],
            "sl_atr_mult": [0.9, 1.2, 1.5],
            "pt_atr_mult": [2.0, 2.5, 3.0],
            "trail_atr_mult": [0.8, 1.2, 1.6],
            "max_entries_per_day": [1, 2],
            "breakeven_on": [False, True],
        },
    ),
    "time_exit": FamilySpec(
        name="time_exit",
        description="Primarily time-based exits via shorter close window + adverse move caps.",
        grid={
            "bar_minutes": [5, 8],
            "entry_tick_offset": [0, 2, 5],
            "stop_loss_ticks": [15, 25, 35],
            "rr_multiple": [1.2, 1.6, 2.0],
            "max_entries_per_day": [1, 2, 3],
            "close_buffer_minutes": [15, 30, 45],
            "trail_on": [False, True],
        },
    ),
}


OPTIMISTIC_EXECUTION = {
    "entry_fill_mode": "touch",
    "stop_slippage_ticks": 0.0,
    "close_slippage_ticks": 0.0,
}

REALISTIC_EXECUTION = {
    "entry_fill_mode": "stop_market",
    "stop_slippage_ticks": 1.5,
    "close_slippage_ticks": 1.0,
}


DEFAULT_TOP_N_PER_INSTRUMENT = 8
DEFAULT_NEIGHBORHOOD_PERTURB = [0.85, 0.9, 1.0, 1.1, 1.15]
