"""Tracks working orders and reconciles with Gateway searchOpen + hub events."""

from __future__ import annotations

from typing import Any

from projectx.api.client import ProjectXClient
from projectx.state.state_manager import StateManager


class OrderManager:
    def __init__(self, client: ProjectXClient, state: StateManager):
        self._client = client
        self._state = state

    def sync_open_orders(self) -> None:
        rows = self._client.get_open_orders(self._state.account_id)
        self._state.replace_open_orders(rows)

    def cancel_order(self, order_id: int) -> dict[str, Any]:
        return self._client.cancel_order(self._state.account_id, order_id)

    def modify_order(self, body: dict[str, Any]) -> dict[str, Any]:
        payload = dict(body)
        payload.setdefault("accountId", self._state.account_id)
        return self._client.modify_order(payload)

    @staticmethod
    def is_partial_fill(order: dict[str, Any]) -> bool:
        size = int(order.get("size", 0))
        filled = int(order.get("fillVolume", 0))
        return 0 < filled < size

    @staticmethod
    def working_status(order: dict[str, Any]) -> bool:
        st = int(order.get("status", 0))
        return st in (1, 6, 7, 8)
