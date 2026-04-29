"""Pytest hooks — avoid Telegram spam from subprocess script smoke tests."""

from __future__ import annotations

import os

os.environ.setdefault("SKIP_TELEGRAM_SCRIPT_DONE", "1")
