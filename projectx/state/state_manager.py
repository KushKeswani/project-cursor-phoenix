"""In-memory broker mirror: positions, orders, balances, contract cache."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Optional

from projectx.utils.helpers import now_ny


@dataclass
class DailyStats:
    ny_date: Optional[date] = None
    trades_count: int = 0
    consecutive_losses: int = 0
    session_start_balance: Optional[float] = None
    peak_balance: Optional[float] = None


class StateManager:
    """
    Thread-safe snapshot updated from REST sync and realtime callbacks.
    """

    def __init__(
        self,
        account_id: int,
        fetch_balance: Callable[[int], float],
        fetch_positions: Callable[[int], list[dict[str, Any]]],
        fetch_open_orders: Callable[[int], list[dict[str, Any]]],
    ):
        self.account_id = account_id
        self._fetch_balance = fetch_balance
        self._fetch_positions = fetch_positions
        self._fetch_open_orders = fetch_open_orders
        self._lock = threading.RLock()
        self.balance: float = 0.0
        self.can_trade: bool = True
        self.positions: dict[str, dict[str, Any]] = {}
        self.open_orders: dict[int, dict[str, Any]] = {}
        self.contract_cache: dict[str, dict[str, Any]] = {}
        self.daily = DailyStats()

    def sync_from_api(self) -> None:
        with self._lock:
            bal = self._fetch_balance(self.account_id)
            self.balance = bal
            pos_list = self._fetch_positions(self.account_id)
            self.positions = {p["contractId"]: p for p in pos_list if p.get("contractId")}
            oo = self._fetch_open_orders(self.account_id)
            self.open_orders = {int(o["id"]): o for o in oo if o.get("id") is not None}
            self._roll_daily_if_needed_locked()
            if self.daily.session_start_balance is None:
                self.daily.session_start_balance = bal
            if self.daily.peak_balance is None or bal > self.daily.peak_balance:
                self.daily.peak_balance = bal

    def _roll_daily_if_needed_locked(self) -> None:
        today = now_ny().date()
        if self.daily.ny_date != today:
            self.daily = DailyStats(
                ny_date=today,
                trades_count=0,
                consecutive_losses=0,
                session_start_balance=self.balance,
                peak_balance=self.balance,
            )

    def update_account_from_hub(self, payload: dict[str, Any]) -> None:
        with self._lock:
            if int(payload.get("id", -1)) != self.account_id:
                return
            self.balance = float(payload.get("balance", self.balance))
            self.can_trade = bool(payload.get("canTrade", self.can_trade))
            self._roll_daily_if_needed_locked()

    def upsert_order_from_hub(self, order: dict[str, Any]) -> None:
        with self._lock:
            oid = order.get("id")
            if oid is None:
                return
            oid = int(oid)
            status = int(order.get("status", 0))
            if status in (2, 3, 4, 5):
                self.open_orders.pop(oid, None)
            else:
                self.open_orders[oid] = order

    def upsert_position_from_hub(self, pos: dict[str, Any]) -> None:
        with self._lock:
            cid = pos.get("contractId")
            if not cid:
                return
            size = int(pos.get("size", 0))
            if size == 0:
                self.positions.pop(cid, None)
            else:
                self.positions[cid] = pos

    def record_trade_fill(self, pnl: Optional[float]) -> None:
        with self._lock:
            self._roll_daily_if_needed_locked()
            self.daily.trades_count += 1
            if pnl is None:
                return
            if pnl < 0:
                self.daily.consecutive_losses += 1
            else:
                self.daily.consecutive_losses = 0

    def has_position_on_contract(self, contract_id: str) -> bool:
        with self._lock:
            p = self.positions.get(contract_id)
            return bool(p and int(p.get("size", 0)) != 0)

    def has_open_orders_on_contract(self, contract_id: str) -> bool:
        with self._lock:
            for o in self.open_orders.values():
                if o.get("contractId") == contract_id:
                    return True
            return False

    def open_order_ids_for_contract(self, contract_id: str) -> list[int]:
        with self._lock:
            return [
                oid
                for oid, o in self.open_orders.items()
                if o.get("contractId") == contract_id
            ]

    def cache_contract(self, symbol_key: str, contract: dict[str, Any]) -> None:
        with self._lock:
            self.contract_cache[symbol_key] = contract

    def get_cached_contract(self, symbol_key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            return self.contract_cache.get(symbol_key)

    def replace_open_orders(self, orders: list[dict[str, Any]]) -> None:
        with self._lock:
            self.open_orders = {
                int(o["id"]): o for o in orders if o.get("id") is not None
            }
