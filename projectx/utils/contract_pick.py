"""Disambiguate Gateway Contract/search results (e.g. YM mini vs MYM micro)."""

from __future__ import annotations

import logging
from typing import Any, List

_log = logging.getLogger(__name__)


def _contract_label(c: dict[str, Any]) -> str:
    return str(c.get("id") or c.get("name") or c.get("symbol") or "")


def pick_contract_from_search(symbol_key: str, rows: List[dict[str, Any]]) -> dict[str, Any]:
    """
    Choose one row from ``search_contracts`` results.

    TopstepX searchText ``YM`` often returns **MYM** (micro) before **YM** (mini).
    For ``symbol_key == "YM"`` we drop rows whose contract id/name contains ``MYM``.
    """
    if not rows:
        raise ValueError("empty contract rows")
    active = [c for c in rows if c.get("activeContract")]
    pool: List[dict[str, Any]] = active if active else list(rows)
    sk = symbol_key.strip().upper()

    if sk == "YM":
        filtered = [c for c in pool if "MYM" not in _contract_label(c).upper()]
        # After dropping MYM, search can still return RTY/M2K/etc. Never use those for symbol YM.
        ym_dow = [c for c in filtered if ".YM." in _contract_label(c).upper()]
        if ym_dow:
            pool = ym_dow
            # Polled often (Phoenix); avoid INFO spam — use DEBUG for routine resolution.
            _log.debug("Contract pick: YM → mini Dow. id=%s", pool[0].get("id"))
        elif filtered:
            sample = [_contract_label(c) for c in filtered[:8]]
            raise ValueError(
                "YM resolution failed: no mini Dow (contract id containing '.YM.') in search "
                f"after excluding MYM. Refusing RTY/other minis. Sample ids: {sample}"
            )
        else:
            _log.warning(
                "Contract pick YM: search returned only MYM — using first row; "
                "check Gateway / search_text in settings.yaml"
            )

    return pool[0]
