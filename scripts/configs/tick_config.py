"""Tick sizes, tick values, and session grids per instrument."""

TICK_SIZES = {
    "CL": 0.01,
    "MGC": 0.10,
    "MNQ": 0.25,
    "YM": 1.0,
    "NG": 0.001,
}

TICK_VALUES = {
    "CL": 10.00,
    "MGC": 1.00,
    "MNQ": 0.50,
    "YM": 5.00,
    "NG": 10.00,
}

INSTRUMENT_GRIDS = {
    "CL": {"bar_minutes": 12, "session_start": 8, "session_end": 18},
    "MGC": {"bar_minutes": 8, "session_start": 8, "session_end": 17},
    "MNQ": {"bar_minutes": 5, "session_start": 8, "session_end": 18},
    "YM": {"bar_minutes": 5, "session_start": 8, "session_end": 18},
    "NG": {"bar_minutes": 8, "session_start": 7, "session_end": 18},
}
