"""Resolve repo root and scripts dir for imports."""

from __future__ import annotations

import sys
from pathlib import Path

_CALC_DIR = Path(__file__).resolve().parent
REPO_ROOT = _CALC_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


def ensure_scripts_on_path() -> Path:
    s = str(SCRIPTS_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)
    return SCRIPTS_DIR
