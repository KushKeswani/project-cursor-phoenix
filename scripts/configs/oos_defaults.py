"""Default out-of-sample window for Phoenix scripts.

``DEFAULT_OOS_END`` is the **current local calendar date** at import time so CLI defaults
stay “through today” without editing code. Override with ``--oos-end`` for reproducibility.
"""

from __future__ import annotations

from datetime import date

# Wider default so prop_sim_compare / portfolio exports build a longer daily pool when
# parquet history exists. Override with --oos-start for reproducible snapshots.
DEFAULT_OOS_START = "2020-01-01"
DEFAULT_OOS_END = date.today().isoformat()
