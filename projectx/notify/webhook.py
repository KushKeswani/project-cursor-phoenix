"""POST Phoenix alerts to a Discord (or compatible) webhook — works on Windows/Linux."""

from __future__ import annotations

import os
from typing import Any, Optional

import requests


def send_webhook_if_configured(body: str, *, logger: Optional[Any] = None) -> None:
    """
    If ``PROJECTX_WEBHOOK_URL`` is set, POST ``body`` as JSON ``{"content": "..."}``
    (Discord incoming webhooks). Optional alias ``DISCORD_WEBHOOK_URL``.

    Truncates to ~1900 chars (Discord limit 2000). Failures are logged, never raised.
    """
    url = (
        os.environ.get("PROJECTX_WEBHOOK_URL")
        or os.environ.get("DISCORD_WEBHOOK_URL")
        or ""
    ).strip()
    if not url or not (body or "").strip():
        return
    text = body.strip()
    if len(text) > 1900:
        text = text[:1890] + "\n…(truncated)"

    try:
        r = requests.post(url, json={"content": text}, timeout=30)
        if r.status_code >= 400:
            msg = f"webhook HTTP {r.status_code}: {r.text[:200]}"
            if logger:
                logger.warning("Phoenix %s", msg)
            else:
                print(msg, flush=True)
    except OSError as e:
        if logger:
            logger.warning("Phoenix webhook failed: %s", e)
        else:
            print(f"Phoenix webhook failed: {e}", flush=True)
