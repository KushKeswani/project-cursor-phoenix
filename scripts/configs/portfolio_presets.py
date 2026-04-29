"""Manual portfolio contract presets."""

INSTRUMENTS = ["CL", "MGC", "MNQ", "YM"]

# --- Micro contract budget (CME-style mental model) ---
# 1 E-mini index notional ≈ 10 micro contracts (e.g. 1 NQ ≈ 10 MNQ).
# "3 minis max" ⇒ at most ~30 micro contracts across MNQ + MGC + YM.
# CL is a full-size energy contract — not a micro; do not add it into the 30.
# Use micro_stack_count() to verify any mix.

MICRO_CAP = 30  # 3 minis × 10 micros per mini


def micro_stack_count(contracts: dict[str, int]) -> int:
    """Count CME micro contracts only: MNQ + MGC + MYM (YM). Excludes CL."""
    return int(contracts["MNQ"]) + int(contracts["MGC"]) + int(contracts["YM"])


# Full four-leg mix (150k high).
_FULL_BALANCED = {"CL": 1, "MGC": 11, "MNQ": 3, "YM": 1}

# Only the four Phoenix tier books (50k/150k × high/survival).
PORTFOLIO_PRESETS = {
    "Balanced_50k_high": {"CL": 0, "MGC": 5, "MNQ": 4, "YM": 1},
    "Balanced_50k_survival": {"CL": 0, "MGC": 3, "MNQ": 1, "YM": 1},
    "Balanced_150k_high": dict(_FULL_BALANCED),
    "Balanced_150k_survival": {"CL": 1, "MGC": 7, "MNQ": 2, "YM": 1},
}

PRESET_NOTES = {
    "Balanced_50k_high": (
        "50k high — no CL. CL 0 / MGC 5 / MNQ 4 / YM 1. Re-run MC with your EOD/DLL."
    ),
    "Balanced_50k_survival": (
        "50k survival — no CL. CL 0 / MGC 3 / MNQ 1 / YM 1. Re-run MC with --eod-dd / --dll."
    ),
    "Balanced_150k_high": (
        "150k high — CL 1 / MGC 11 / MNQ 3 / YM 1. EOD $5k / DLL $3k MC band in past sweeps."
    ),
    "Balanced_150k_survival": (
        "150k survival — CL 1 / MGC 7 / MNQ 2 / YM 1 (~0.64× full Balanced). "
        "Typical MC band: EOD $5k / DLL $3k."
    ),
}

# Titles for charts/reports (human-readable). Keys must match PORTFOLIO_PRESETS.
PRESET_DISPLAY_TITLES = {
    "Balanced_50k_high": "Balanced $50k high — CL 0 / MGC 5 / MNQ 4 / YM 1",
    "Balanced_50k_survival": "Balanced $50k survival — CL 0 / MGC 3 / MNQ 1 / YM 1",
    "Balanced_150k_high": "Balanced $150k high — CL 1 / MGC 11 / MNQ 3 / YM 1",
    "Balanced_150k_survival": "Balanced $150k survival — CL 1 / MGC 7 / MNQ 2 / YM 1",
}

# Four-tier matrix for Phoenix reporting (high = larger stack, low = survival-style).
FOUR_TIER_PROFILES: dict[str, str] = {
    "50k_high": "Balanced_50k_high",
    "50k_low": "Balanced_50k_survival",
    "150k_high": "Balanced_150k_high",
    "150k_low": "Balanced_150k_survival",
}
