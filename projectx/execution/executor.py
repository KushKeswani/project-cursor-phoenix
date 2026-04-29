"""Signal → Gateway PlaceOrderRequest (market or limit entry + SL/TP brackets)."""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

from projectx.api.client import ProjectXClient
from projectx.risk.risk_manager import RiskManager
from projectx.state.state_manager import StateManager
from projectx.utils.contract_pick import pick_contract_from_search
from projectx.utils.helpers import (
    ORDER_SIDE_ASK,
    ORDER_SIDE_BID,
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
    ORDER_TYPE_STOP,
    dollar_risk_to_bracket_ticks,
    gateway_signed_bracket_ticks,
    price_to_bracket_ticks,
    round_price_to_tick,
)


class ExecutionError(Exception):
    pass


class Executor:
    def __init__(
        self,
        client: ProjectXClient,
        state: StateManager,
        risk: RiskManager,
        *,
        dry_run: bool = True,
        live_contracts: bool = True,
        logger: Any,
    ):
        self._client = client
        self._state = state
        self._risk = risk
        self._dry_run = dry_run
        self._live_contracts = live_contracts
        self._log = logger
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._recent_signal_ids: dict[str, float] = {}
        self._dedupe_ttl_sec = 300.0

    def _lock_for_contract(self, contract_id: str) -> threading.Lock:
        with self._locks_guard:
            if contract_id not in self._locks:
                self._locks[contract_id] = threading.Lock()
            return self._locks[contract_id]

    def resolve_contract(
        self,
        symbol_key: str,
        instrument_cfg: dict[str, Any],
        *,
        live: Optional[bool] = None,
    ) -> dict[str, Any]:
        use_live = self._live_contracts if live is None else live
        cached = self._state.get_cached_contract(symbol_key)
        if cached and live is None:
            return cached
        search_text = instrument_cfg.get("search_text", symbol_key)
        rows = self._client.search_contracts(use_live, search_text)
        if not rows:
            raise ExecutionError(f"No contracts for search_text={search_text!r}")
        pick = pick_contract_from_search(symbol_key, rows)
        if live is None:
            self._state.cache_contract(symbol_key, pick)
        return pick

    def execute_dollar_risk_bracket(
        self,
        *,
        symbol: str,
        side: str,
        size: int,
        risk_usd: float,
        reward_usd: float,
        instrument_cfg: dict[str, Any],
        signal_id: str = "",
        custom_tag: Optional[str] = None,
        live_contracts: Optional[bool] = None,
        ignore_ny_session: bool = False,
        limit_entry_price: Optional[float] = None,
    ) -> Optional[dict[str, Any]]:
        symbol_u = str(symbol).upper()
        stub: dict[str, Any] = {
            "symbol": symbol_u,
            "side": side,
            "size": size,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "reference_price": 1.0,
        }
        self._log.info(
            "Dollar bracket: %s %s x%s risk $%s reward $%s",
            symbol_u,
            side,
            size,
            risk_usd,
            reward_usd,
        )
        if signal_id:
            stub["signal_id"] = signal_id
            self._log.info("Signal received: %s", stub)
            self._purge_old_signal_ids()
            if signal_id in self._recent_signal_ids:
                raise ExecutionError(f"duplicate signal_id {signal_id!r}")
            self._recent_signal_ids[signal_id] = time.monotonic()
        self._risk.validate_signal(
            stub,
            require_price_brackets=False,
            ignore_ny_session=ignore_ny_session,
        )

        contract = self.resolve_contract(
            symbol_u, instrument_cfg, live=live_contracts
        )
        contract_id = contract["id"]
        tick_size = float(contract.get("tickSize") or 0.0)
        tick_value = float(contract.get("tickValue") or 0.0)
        if tick_value <= 0:
            raise ExecutionError(f"Invalid tickValue for {contract_id}")
        if tick_size <= 0:
            raise ExecutionError(f"Invalid tickSize for {contract_id}")

        try:
            sl_u, tp_u = dollar_risk_to_bracket_ticks(
                risk_usd=risk_usd,
                reward_usd=reward_usd,
                tick_value=tick_value,
                contracts=size,
            )
        except ValueError as e:
            raise ExecutionError(str(e)) from e

        side_long = str(side).lower() in ("long", "buy")
        sl_ticks, tp_ticks = gateway_signed_bracket_ticks(
            sl_u, tp_u, side_long=side_long
        )
        ord_side = ORDER_SIDE_BID if side_long else ORDER_SIDE_ASK

        # Phoenix "limit" path uses breakout **stop** at engine trigger (Gateway type Stop + stopPrice).
        # A buy/sell **limit** at the breakout level is often rejected once price has moved through.
        use_stop_trigger = limit_entry_price is not None
        if use_stop_trigger:
            sp = round_price_to_tick(float(limit_entry_price), tick_size)
            if sp <= 0:
                raise ExecutionError(f"Invalid limit_entry_price after tick round: {sp!r}")

        lock = self._lock_for_contract(contract_id)
        if not lock.acquire(blocking=False):
            raise ExecutionError(f"Another execution in progress for {contract_id}")

        try:
            self._state.sync_from_api()
            if self._state.has_position_on_contract(contract_id):
                raise ExecutionError(
                    f"Already have a position on {contract_id}; one position per instrument."
                )
            if self._state.has_open_orders_on_contract(contract_id):
                raise ExecutionError(
                    f"Open orders exist on {contract_id}; refusing duplicate entry."
                )

            entry_type = ORDER_TYPE_STOP if use_stop_trigger else ORDER_TYPE_MARKET
            payload: dict[str, Any] = {
                "accountId": self._state.account_id,
                "contractId": contract_id,
                "type": entry_type,
                "side": ord_side,
                "size": int(size),
                "stopLossBracket": {"ticks": sl_ticks, "type": ORDER_TYPE_STOP},
                "takeProfitBracket": {"ticks": tp_ticks, "type": ORDER_TYPE_LIMIT},
            }
            if use_stop_trigger:
                payload["stopPrice"] = float(sp)
            if custom_tag:
                payload["customTag"] = str(custom_tag)[:200]

            self._log.info(
                "Bracket ticks from contract tickValue=%s tickSize=%s: sl_ticks=%s tp_ticks=%s "
                "entry=%s payload=%s",
                tick_value,
                tick_size,
                sl_ticks,
                tp_ticks,
                "STOP@%s" % sp if use_stop_trigger else "MARKET",
                payload,
            )
            if self._dry_run:
                self._log.warning("dry_run=True — order not sent")
                return {"dry_run": True, "payload": payload}

            resp = self._client.place_order(payload)
            if not resp.get("success") or resp.get("errorCode", -1) != 0:
                raise ExecutionError(
                    f"place_order failed: {resp.get('errorCode')} {resp.get('errorMessage')}"
                )
            self._log.info("Order placed orderId=%s", resp.get("orderId"))
            return resp
        finally:
            lock.release()

    def execute_phoenix_arm_breakout_pair(
        self,
        *,
        symbol: str,
        size: int,
        long_stop_price: float,
        short_stop_price: float,
        risk_usd: float,
        reward_usd: float,
        instrument_cfg: dict[str, Any],
        signal_id_long: str,
        signal_id_short: str,
        custom_tag_long: str,
        custom_tag_short: str,
        live_contracts: Optional[bool] = None,
        ignore_ny_session: bool = False,
        place_long: bool = True,
        place_short: bool = True,
    ) -> dict[str, Any]:
        """
        Place **buy stop** + **sell stop** at range breakout levels with SL/TP brackets.
        Used when the trade window opens so triggers rest before price runs through.
        Caller must cancel siblings when one fills or at trade_end (OCO is manual).
        """
        symbol_u = str(symbol).upper()
        if not place_long and not place_short:
            self._log.warning("Phoenix arm: no legs to place for %s", symbol_u)
            return {"skipped": True, "reason": "no_legs"}

        leg_specs: list[tuple[str, str, str]] = []
        if place_long:
            leg_specs.append(("long", signal_id_long, custom_tag_long))
        if place_short:
            leg_specs.append(("short", signal_id_short, custom_tag_short))

        for tag, sig_id, _ct in leg_specs:
            stub: dict[str, Any] = {
                "symbol": symbol_u,
                "side": "long" if tag == "long" else "short",
                "size": size,
                "stop_loss": 0.0,
                "take_profit": 0.0,
                "reference_price": 1.0,
                "signal_id": sig_id,
            }
            self._log.info("Phoenix arm signal (%s): %s", tag, stub)
            self._purge_old_signal_ids()
            if sig_id in self._recent_signal_ids:
                raise ExecutionError(f"duplicate signal_id {sig_id!r}")
            self._recent_signal_ids[sig_id] = time.monotonic()
            self._risk.validate_signal(
                stub,
                require_price_brackets=False,
                ignore_ny_session=ignore_ny_session,
            )

        contract = self.resolve_contract(
            symbol_u, instrument_cfg, live=live_contracts
        )
        contract_id = contract["id"]
        tick_size = float(contract.get("tickSize") or 0.0)
        tick_value = float(contract.get("tickValue") or 0.0)
        if tick_value <= 0:
            raise ExecutionError(f"Invalid tickValue for {contract_id}")
        if tick_size <= 0:
            raise ExecutionError(f"Invalid tickSize for {contract_id}")

        try:
            sl_u, tp_u = dollar_risk_to_bracket_ticks(
                risk_usd=risk_usd,
                reward_usd=reward_usd,
                tick_value=tick_value,
                contracts=size,
            )
        except ValueError as e:
            raise ExecutionError(str(e)) from e

        sp_l = round_price_to_tick(float(long_stop_price), tick_size)
        sp_s = round_price_to_tick(float(short_stop_price), tick_size)
        if sp_l <= 0 or sp_s <= 0:
            raise ExecutionError(f"Invalid arm stop prices after tick round: {sp_l!r} {sp_s!r}")

        lock = self._lock_for_contract(contract_id)
        if not lock.acquire(blocking=False):
            raise ExecutionError(f"Another execution in progress for {contract_id}")

        def _payload(side_long: bool, stop_px: float, custom_tag: str) -> dict[str, Any]:
            sl_ticks, tp_ticks = gateway_signed_bracket_ticks(
                sl_u, tp_u, side_long=side_long
            )
            ord_side = ORDER_SIDE_BID if side_long else ORDER_SIDE_ASK
            pl: dict[str, Any] = {
                "accountId": self._state.account_id,
                "contractId": contract_id,
                "type": ORDER_TYPE_STOP,
                "side": ord_side,
                "size": int(size),
                "stopPrice": float(stop_px),
                "stopLossBracket": {"ticks": sl_ticks, "type": ORDER_TYPE_STOP},
                "takeProfitBracket": {"ticks": tp_ticks, "type": ORDER_TYPE_LIMIT},
            }
            if custom_tag:
                pl["customTag"] = str(custom_tag)[:200]
            self._log.info(
                "Phoenix arm bracket: side_long=%s stop=%s sl_ticks=%s tp_ticks=%s payload=%s",
                side_long,
                stop_px,
                sl_ticks,
                tp_ticks,
                pl,
            )
            return pl

        try:
            self._state.sync_from_api()
            if self._state.has_position_on_contract(contract_id):
                raise ExecutionError(
                    f"Already have a position on {contract_id}; skip arm pair."
                )
            if self._state.has_open_orders_on_contract(contract_id):
                raise ExecutionError(
                    f"Open orders exist on {contract_id}; refuse arm pair (close or cancel first)."
                )

            pl_long = _payload(True, sp_l, custom_tag_long) if place_long else None
            pl_short = _payload(False, sp_s, custom_tag_short) if place_short else None

            if self._dry_run:
                self._log.warning("dry_run=True — arm stops not sent")
                return {
                    "dry_run": True,
                    "long_payload": pl_long,
                    "short_payload": pl_short,
                }

            out_long: Optional[dict[str, Any]] = None
            out_short: Optional[dict[str, Any]] = None

            if place_long and pl_long is not None:
                resp1 = self._client.place_order(pl_long)
                if not resp1.get("success") or resp1.get("errorCode", -1) != 0:
                    raise ExecutionError(
                        f"arm long stop failed: {resp1.get('errorCode')} {resp1.get('errorMessage')}"
                    )
                out_long = resp1
                oid1 = resp1.get("orderId")

            if place_short and pl_short is not None:
                resp2 = self._client.place_order(pl_short)
                if not resp2.get("success") or resp2.get("errorCode", -1) != 0:
                    err = f"{resp2.get('errorCode')} {resp2.get('errorMessage')}"
                    if out_long is not None and out_long.get("orderId") is not None:
                        oid1 = out_long.get("orderId")
                        try:
                            self._client.cancel_order(self._state.account_id, int(oid1))
                            self._log.warning(
                                "Cancelled arm long order %s after short leg failed: %s",
                                oid1,
                                err,
                            )
                        except Exception as ce:
                            self._log.error(
                                "Arm short failed (%s) and could not cancel long %s: %s",
                                err,
                                oid1,
                                ce,
                            )
                    raise ExecutionError(f"arm short stop failed: {err}")
                out_short = resp2

            self._log.info(
                "Phoenix arm orders placed long orderId=%s short orderId=%s",
                (out_long or {}).get("orderId"),
                (out_short or {}).get("orderId"),
            )
            return {"long": out_long, "short": out_short}
        finally:
            lock.release()

    def execute_signal(
        self,
        signal: dict[str, Any],
        instrument_cfg: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        self._log.info("Signal received: %s", signal)
        work = dict(signal)
        ign = bool(work.pop("ignore_ny_session", False))
        sim = bool(work.pop("sim_contract_search", False))
        live_res: Optional[bool] = False if sim else None

        symbol = str(work["symbol"]).upper()
        sig_id = str(work.get("signal_id", "")).strip()
        if sig_id:
            self._purge_old_signal_ids()
            if sig_id in self._recent_signal_ids:
                raise ExecutionError(f"duplicate signal_id {sig_id!r}")
            self._recent_signal_ids[sig_id] = time.monotonic()

        self._risk.validate_signal(work, ignore_ny_session=ign)

        contract = self.resolve_contract(symbol, instrument_cfg, live=live_res)
        contract_id = contract["id"]
        tick_size = float(contract.get("tickSize") or 0.0)
        if tick_size <= 0:
            raise ExecutionError(f"Invalid tickSize for {contract_id}")

        side_long = str(work["side"]).lower() in ("long", "buy")
        side = ORDER_SIDE_BID if side_long else ORDER_SIDE_ASK
        ref = float(work["reference_price"])
        sl = float(work["stop_loss"])
        tp = float(work["take_profit"])
        sl_u, tp_u = price_to_bracket_ticks(
            reference_price=ref,
            stop_price=sl,
            take_profit_price=tp,
            tick_size=tick_size,
            side_long=side_long,
        )
        sl_ticks, tp_ticks = gateway_signed_bracket_ticks(
            sl_u, tp_u, side_long=side_long
        )

        lock = self._lock_for_contract(contract_id)
        if not lock.acquire(blocking=False):
            raise ExecutionError(f"Another execution in progress for {contract_id}")

        try:
            self._state.sync_from_api()
            if self._state.has_position_on_contract(contract_id):
                raise ExecutionError(
                    f"Already have a position on {contract_id}; one position per instrument."
                )
            if self._state.has_open_orders_on_contract(contract_id):
                raise ExecutionError(
                    f"Open orders exist on {contract_id}; refusing duplicate entry."
                )

            payload: dict[str, Any] = {
                "accountId": self._state.account_id,
                "contractId": contract_id,
                "type": ORDER_TYPE_MARKET,
                "side": side,
                "size": int(work["size"]),
                "stopLossBracket": {"ticks": sl_ticks, "type": ORDER_TYPE_STOP},
                "takeProfitBracket": {"ticks": tp_ticks, "type": ORDER_TYPE_LIMIT},
            }
            tag = work.get("custom_tag")
            if tag:
                payload["customTag"] = str(tag)[:200]

            self._log.info("Order payload prepared: %s", payload)
            if self._dry_run:
                self._log.warning("dry_run=True — order not sent")
                return {"dry_run": True, "payload": payload}

            resp = self._client.place_order(payload)
            if not resp.get("success") or resp.get("errorCode", -1) != 0:
                raise ExecutionError(
                    f"place_order failed: {resp.get('errorCode')} {resp.get('errorMessage')}"
                )
            self._log.info("Order placed orderId=%s", resp.get("orderId"))
            return resp
        finally:
            lock.release()

    def _purge_old_signal_ids(self) -> None:
        now = time.monotonic()
        dead = [k for k, t in self._recent_signal_ids.items() if now - t > self._dedupe_ttl_sec]
        for k in dead:
            del self._recent_signal_ids[k]
