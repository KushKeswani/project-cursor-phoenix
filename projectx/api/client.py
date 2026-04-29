"""Typed-ish wrapper over ProjectX Gateway REST API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import requests

from projectx.api.auth import ProjectXAuth
from projectx.api.endpoints import Paths


class ProjectXClient:
    def __init__(
        self,
        base_url: str,
        auth: ProjectXAuth,
        timeout: float = 30.0,
    ):
        self._base = base_url.rstrip("/")
        self._auth = auth
        self._timeout = timeout
        self._session = requests.Session()

    def _headers(self) -> dict[str, str]:
        token = self._auth.get_token()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    def _post(self, path: str, json: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        url = self._base + path
        resp = self._session.post(
            url, json=json or {}, headers=self._headers(), timeout=self._timeout
        )
        if resp.status_code == 401:
            self._auth.force_refresh()
            resp = self._session.post(
                url, json=json or {}, headers=self._headers(), timeout=self._timeout
            )
        resp.raise_for_status()
        return resp.json()

    def get_accounts(self, only_active: bool = True) -> list[dict[str, Any]]:
        data = self._post(Paths.ACCOUNT_SEARCH, {"onlyActiveAccounts": only_active})
        self._raise_if_error(data, "Account search")
        return list(data.get("accounts") or [])

    def get_balance(self, account_id: int) -> float:
        for acc in self.get_accounts(True):
            if int(acc.get("id", -1)) == int(account_id):
                return float(acc.get("balance", 0.0))
        raise KeyError(f"Account {account_id} not found")

    def get_contracts(self, live: bool) -> list[dict[str, Any]]:
        data = self._post(Paths.CONTRACT_AVAILABLE, {"live": live})
        self._raise_if_error(data, "Contract available")
        return list(data.get("contracts") or [])

    def search_contracts(self, live: bool, search_text: str) -> list[dict[str, Any]]:
        data = self._post(
            Paths.CONTRACT_SEARCH,
            {"live": live, "searchText": search_text},
        )
        self._raise_if_error(data, "Contract search")
        return list(data.get("contracts") or [])

    def place_order(self, request_body: dict[str, Any]) -> dict[str, Any]:
        data = self._post(Paths.ORDER_PLACE, request_body)
        return data

    def cancel_order(self, account_id: int, order_id: int) -> dict[str, Any]:
        return self._post(
            Paths.ORDER_CANCEL,
            {"accountId": account_id, "orderId": order_id},
        )

    def modify_order(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post(Paths.ORDER_MODIFY, body)

    def retrieve_bars(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post(Paths.HISTORY_RETRIEVE_BARS, body)

    def get_open_orders(self, account_id: int) -> list[dict[str, Any]]:
        data = self._post(Paths.ORDER_SEARCH_OPEN, {"accountId": account_id})
        self._raise_if_error(data, "Open orders")
        return list(data.get("orders") or [])

    def get_positions(self, account_id: int) -> list[dict[str, Any]]:
        data = self._post(Paths.POSITION_SEARCH_OPEN, {"accountId": account_id})
        self._raise_if_error(data, "Open positions")
        return list(data.get("positions") or [])

    def search_orders_recent(
        self, account_id: int, days: int = 7
    ) -> list[dict[str, Any]]:
        start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        data = self._post(
            Paths.ORDER_SEARCH,
            {"accountId": account_id, "startTimestamp": start},
        )
        self._raise_if_error(data, "Order search")
        return list(data.get("orders") or [])

    @staticmethod
    def _raise_if_error(data: dict[str, Any], ctx: str) -> None:
        if not data.get("success") or data.get("errorCode", -1) != 0:
            raise RuntimeError(
                f"{ctx} failed: errorCode={data.get('errorCode')} "
                f"message={data.get('errorMessage')}"
            )
