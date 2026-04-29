"""
ProjectX execution runner (Phase 1): auth, state sync, risk, mock signal, optional RTC.

Run from repository root:
  python -m projectx.main
  python -m projectx.main --list-accounts
  python -m projectx.main --session --live-order
  python -m projectx.main --phoenix-auto --live-order   # API orders; range sealed → optional arm stops; entry uses stop@trigger
  python -m projectx.main --phoenix-auto --phoenix-manual   # Placement print only (no API orders)

Dependencies:
  pip install -r projectx/requirements.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from projectx.api.auth import AuthConfig, ProjectXAuth
from projectx.api.client import ProjectXClient
from projectx.notify.telegram import send_telegram_if_configured
from projectx.notify.webhook import send_webhook_if_configured
from projectx.execution.executor import ExecutionError, Executor
from projectx.execution.order_manager import OrderManager
from projectx.realtime.listener import UserHubListener
from projectx.risk.risk_manager import RiskCheckError, RiskConfig, RiskManager
from projectx.state.state_manager import StateManager
from projectx.utils.helpers import (
    dollar_risk_to_bracket_ticks,
    gateway_signed_bracket_ticks,
    load_settings,
    now_ny,
)
from projectx.utils.logger import setup_logging


def _parse_phoenix_contracts(spec: str, instruments: list[str]) -> dict[str, int]:
    out = {i: 1 for i in instruments}
    if not spec.strip():
        return out
    for part in spec.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip().upper()] = int(v.strip())
    return out


def _phoenix_placement_instructions_text(
    *,
    inst: str,
    tr: dict[str, Any],
    side: str,
    contracts: int,
    r_usd: float,
    rw_usd: float,
    use_limit: bool,
    tick_value: float,
    api_sends_order: bool,
) -> str:
    """Human-readable placement notes (uses CME-style tick $; live Gateway tickValue can differ slightly)."""
    side_long = str(side).lower() in ("long", "buy")
    sl_u, tp_u = dollar_risk_to_bracket_ticks(
        risk_usd=r_usd,
        reward_usd=rw_usd,
        tick_value=tick_value,
        contracts=contracts,
    )
    sl_sig, tp_sig = gateway_signed_bracket_ticks(sl_u, tp_u, side_long=side_long)
    ep = tr.get("entry_price")
    try:
        ep_f = float(ep) if ep is not None else 0.0
    except (TypeError, ValueError):
        ep_f = 0.0
    if use_limit and ep_f > 0:
        entry_line = (
            f"ENTRY:  STOP @ {ep_f:g}  (breakout trigger at engine price; SL/TP brackets)"
        )
    else:
        entry_line = "ENTRY:  MARKET  (then attach brackets from fill price)"
    usd_per_tick = tick_value * float(contracts)
    if api_sends_order:
        banner = (
            "  PHOENIX PLACEMENT  —  mirror for your manual / parallel trade; "
            "API bracket order is submitted next"
        )
    else:
        banner = "  PHOENIX MANUAL  —  place in your platform (no API order was sent)"
    lines = [
        "",
        "=" * 66,
        banner,
        "=" * 66,
        f"  {inst}   {str(side).upper()}   x{contracts}",
        f"  {entry_line}",
        f"  Total SL risk:   ${r_usd:.2f}   (~{usd_per_tick:.2f} $/tick combined → ~{sl_u} stop ticks)",
        f"  Total TP reward: ${rw_usd:.2f}   (~{tp_u} target ticks)",
        f"  Gateway-style bracket ticks (verify in UI):  SL ticks={sl_sig}   TP ticks={tp_sig}",
        f"  Engine entry_ts: {tr.get('entry_ts')!r}",
        "  Tip: attach OCO / auto brackets from fill; tickValue on live contract may differ slightly.",
        "=" * 66,
        "",
    ]
    return "\n".join(lines)


def _instrument_map(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in cfg.get("trading", {}).get("instruments", []):
        sym = str(row.get("symbol", "")).upper()
        if sym:
            out[sym] = row
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ProjectX live execution shell")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to settings.yaml (default: projectx/config/settings.yaml)",
    )
    parser.add_argument(
        "--no-rtc",
        action="store_true",
        help="Do not start SignalR user hub listener",
    )
    parser.add_argument(
        "--demo-risk-block",
        action="store_true",
        help="Send an oversized mock signal to verify risk blocking",
    )
    parser.add_argument(
        "--list-accounts",
        action="store_true",
        help="After login, print each account (full JSON from API) for PROJECTX_ACCOUNT_ID",
    )
    parser.add_argument(
        "--list-accounts-include-inactive",
        action="store_true",
        help="With --list-accounts: pass onlyActiveAccounts=false (see leader / inactive evals)",
    )
    parser.add_argument(
        "--place-dollar-bracket",
        action="store_true",
        help="Market entry + SL/TP brackets sized from USD risk/reward (total $ across all contracts)",
    )
    parser.add_argument(
        "--bracket-symbol",
        default="MNQ",
        help="Instrument symbol (default MNQ)",
    )
    parser.add_argument(
        "--bracket-side",
        default="long",
        choices=["long", "short", "buy", "sell"],
    )
    parser.add_argument("--bracket-size", type=int, default=None, help="Contracts")
    parser.add_argument(
        "--risk-usd",
        type=float,
        default=None,
        help="Total stop $ across all contracts (e.g. 400)",
    )
    parser.add_argument(
        "--reward-usd",
        type=float,
        default=None,
        help="Total take-profit $ across all contracts (e.g. 800)",
    )
    parser.add_argument(
        "--live-order",
        action="store_true",
        help="Actually send order (otherwise preview only unless execution.dry_run is false)",
    )
    parser.add_argument(
        "--ignore-ny-session",
        action="store_true",
        help="Skip NY clock window check (futures trade outside 9:30-16:00 NY)",
    )
    parser.add_argument(
        "--sim-contract-search",
        action="store_true",
        help="Use live=false for Contract/search (try if practice rejects live=true)",
    )
    parser.add_argument(
        "--session",
        action="store_true",
        help="Run until Ctrl+C: sync + RTC (unless --no-rtc) + watch signals/inbox for *.json",
    )
    parser.add_argument(
        "--signals-dir",
        type=Path,
        default=None,
        help="Inbox directory for JSON signals (default: projectx/signals/inbox)",
    )
    parser.add_argument(
        "--poll-signals-seconds",
        type=float,
        default=5.0,
        help="How often to scan the signals inbox",
    )
    parser.add_argument(
        "--phoenix-scan",
        action="store_true",
        help="Run Phoenix range-breakout detector once on latest bar (uses scripts/ engine)",
    )
    parser.add_argument(
        "--phoenix-auto",
        action="store_true",
        help=(
            "Poll Phoenix scan until Ctrl+C. By default each symbol is scanned only inside "
            "its strategy trade window (ET): MNQ/YM 11:00-13:00, MGC 12:00-13:00, CL 10:30-12:30. "
            "Entry order type: execution.phoenix_entry_order (limit at engine entry_price vs market); "
            "override with --phoenix-market-entry."
        ),
    )
    parser.add_argument(
        "--phoenix-poll-seconds",
        type=float,
        default=30.0,
        help="Interval for --phoenix-auto (default 30s)",
    )
    parser.add_argument(
        "--phoenix-data-dir",
        type=Path,
        default=None,
        help="Parquet dir (e.g. Data-DataBento). If omitted, uses TopstepX History API.",
    )
    parser.add_argument(
        "--phoenix-live-bars",
        action="store_true",
        help="Gateway: use live=true for bars/contracts (default: sim/practice)",
    )
    parser.add_argument(
        "--phoenix-instruments",
        type=str,
        default="MNQ,MGC,YM",
        help="Comma-separated: MNQ,MGC,CL,YM (default: MNQ,MGC,YM). RTY/M2K rejected - not Phoenix symbols.",
    )
    parser.add_argument(
        "--phoenix-contracts",
        type=str,
        default="MNQ=1,MGC=3,YM=1",
        help=(
            "Per-symbol size (default = 50k_low / Balanced_50k_survival). "
            "Four-tier presets: 50k_high MNQ=4,MGC=5,YM=1; 150k_* add CL - see portfolio_presets.FOUR_TIER_PROFILES"
        ),
    )
    parser.add_argument(
        "--phoenix-market-entry",
        action="store_true",
        help="Phoenix: use market entry (overrides execution.phoenix_entry_order limit)",
    )
    parser.add_argument(
        "--phoenix-entry-fill",
        type=str,
        default=None,
        choices=("touch", "touch_legacy", "touch_strict"),
        help=(
            "fast_engine entry semantics (default: execution.phoenix_entry_fill). "
            "touch|touch_legacy = high>=long / low<=short (research default). "
            "touch_strict = wick-through trigger. "
            "Limit/stop API may still skip when the exchange rejects stop vs last."
        ),
    )
    parser.add_argument(
        "--phoenix-manual",
        action="store_true",
        help=(
            "Phoenix: print placement only - no API orders (for testing the scanner). "
            "Without this, orders still send and placement is printed unless "
            "--phoenix-no-placement-print."
        ),
    )
    parser.add_argument(
        "--phoenix-no-placement-print",
        action="store_true",
        help="Phoenix: do not print the placement box (API behavior unchanged).",
    )
    parser.add_argument(
        "--phoenix-no-engine-events",
        action="store_true",
        help="Phoenix: skip range-built / armed notifications (terminal + Telegram)",
    )
    parser.add_argument(
        "--phoenix-poll-status",
        action="store_true",
        help="Phoenix: print a one-line status every poll (noisy; default is event-only)",
    )
    parser.add_argument(
        "--phoenix-no-telegram",
        action="store_true",
        help=(
            "Phoenix: do not send Telegram (overrides execution.phoenix_telegram even if token + chat id are set)"
        ),
    )
    parser.add_argument(
        "--phoenix-telegram-test",
        action="store_true",
        help=(
            "Send sample Phoenix-style Telegram messages (startup, range/armed, order signal) and exit "
            "(no Gateway login; uses projectx/.env Telegram vars)"
        ),
    )
    parser.add_argument(
        "--phoenix-no-webhook",
        action="store_true",
        help="Phoenix: do not POST to PROJECTX_WEBHOOK_URL / DISCORD_WEBHOOK_URL",
    )
    parser.add_argument(
        "--phoenix-range-resend",
        action="store_true",
        help="Phoenix: clear today's range_sealed dedupe keys so the next poll can notify again",
    )
    parser.add_argument(
        "--phoenix-no-range-addon-fetch",
        action="store_true",
        help="Gateway only: skip extra History retrieve for the opening-range window (merged with day series)",
    )
    parser.add_argument(
        "--phoenix-range-single-telegram",
        action="store_true",
        help="Phoenix: one Telegram message for range sealed + armed (default: two separate sends)",
    )
    parser.add_argument(
        "--phoenix-respect-ny-session",
        action="store_true",
        help="Apply risk NY clock window to orders (default: off for futures)",
    )
    parser.add_argument(
        "--phoenix-no-arm-orders",
        action="store_true",
        help=(
            "Phoenix: disable resting buy/sell stop brackets at range levels when the trade "
            "window opens (default is ON: place as soon as armed window is active)"
        ),
    )
    args = parser.parse_args(argv)

    cfg_path = args.config
    if cfg_path is None:
        cfg_path = Path(__file__).resolve().parent / "config" / "settings.yaml"
    cfg = load_settings(cfg_path)

    log_cfg = cfg.get("logging", {})
    logger = setup_logging(
        level=str(log_cfg.get("level", "INFO")),
        log_file=log_cfg.get("file"),
    )

    if args.phoenix_telegram_test:
        from projectx.strategy.phoenix_auto import (
            ensure_scripts_on_path as _phoenix_ensure_scripts,
            phoenix_telegram_sample_bodies,
        )

        _phoenix_ensure_scripts()
        bodies = phoenix_telegram_sample_bodies(
            single_combined=args.phoenix_range_single_telegram,
        )
        logger.info("Phoenix Telegram test: sending %s sample message(s)", len(bodies))
        for body in bodies:
            send_telegram_if_configured(body, logger=logger)
        print(
            f"Sent {len(bodies)} Phoenix-style Telegram sample(s). Check your chat.",
            flush=True,
        )
        return 0

    cred = cfg.get("credentials", {})
    user_name = cred.get("user_name") or ""
    api_key = cred.get("api_key") or ""
    if not user_name or not api_key:
        logger.error("Set credentials.user_name and credentials.api_key (or env vars).")
        return 1

    trade = cfg.get("trading", {})
    account_id = trade.get("account_id")
    if account_id is not None:
        account_id = int(account_id)

    base_url = cfg["api"]["base_url"]
    auth_cfg = AuthConfig(
        base_url=base_url,
        user_name=user_name,
        api_key=api_key,
        refresh_margin_seconds=float(
            cfg.get("auth", {}).get("refresh_margin_seconds", 1800)
        ),
        request_timeout=float(cfg.get("auth", {}).get("request_timeout_seconds", 30)),
    )
    auth = ProjectXAuth(auth_cfg)
    client = ProjectXClient(
        base_url,
        auth,
        timeout=auth_cfg.request_timeout,
    )

    try:
        auth.get_token()
        logger.info("Authenticated to ProjectX Gateway")
    except Exception as e:
        logger.exception("Authentication failed: %s", e)
        return 1

    if args.list_accounts:
        only_active = not args.list_accounts_include_inactive
        try:
            accounts = client.get_accounts(only_active=only_active)
        except Exception as e:
            logger.exception("Account search failed: %s", e)
            return 1
        if not accounts:
            logger.warning(
                "No accounts returned (onlyActiveAccounts=%s). "
                "Try --list-accounts-include-inactive.",
                only_active,
            )
            return 0
        print(
            f"ProjectX accounts (onlyActiveAccounts={only_active}). "
            "Use id for PROJECTX_ACCOUNT_ID or trading.account_id in settings.yaml.\n"
        )
        for i, a in enumerate(accounts):
            aid = a.get("id")
            name = a.get("name") or ""
            print(f"--- [{i}] id={aid} name={name!r} ---")
            # Surface any leader-related keys without guessing exact API spelling
            for k in sorted(a.keys()):
                lk = str(k).lower()
                if "leader" in lk or "follow" in lk or "copy" in lk:
                    print(f"  {k}: {a.get(k)!r}")
            print(json.dumps(a, indent=2, sort_keys=True, default=str))
            print()
        print(
            "Set PROJECTX_ACCOUNT_ID=<id> in projectx/.env "
            "(or trading.account_id in projectx/config/settings.yaml)."
        )
        return 0

    if account_id is None:
        logger.error(
            "Set trading.account_id or PROJECTX_ACCOUNT_ID "
            "(or run with --list-accounts to see ids)."
        )
        return 1

    state = StateManager(
        account_id,
        fetch_balance=client.get_balance,
        fetch_positions=client.get_positions,
        fetch_open_orders=client.get_open_orders,
    )
    try:
        state.sync_from_api()
    except Exception as e:
        logger.exception("Initial state sync failed: %s", e)
        return 1

    imap = _instrument_map(cfg)
    risk_yaml = cfg.get("risk", {})
    ny = risk_yaml.get("ny_session", {})
    risk = RiskManager(
        RiskConfig(
            max_daily_loss_usd=float(risk_yaml.get("max_daily_loss_usd", 500)),
            max_drawdown_from_peak_usd=float(
                risk_yaml.get("max_drawdown_from_peak_usd", 1500)
            ),
            max_position_contracts=int(risk_yaml.get("max_position_contracts", 3)),
            max_trades_per_day=int(risk_yaml.get("max_trades_per_day", 10)),
            max_consecutive_losses=int(risk_yaml.get("max_consecutive_losses", 3)),
            ny_session_enabled=bool(ny.get("enabled", True)),
            ny_session_start=str(ny.get("start", "09:30")),
            ny_session_end=str(ny.get("end", "16:00")),
            emergency_halt=bool(risk_yaml.get("emergency_halt", False)),
            kill_switch_path=risk_yaml.get("kill_switch_path"),
        ),
        state,
    )

    order_mgr = OrderManager(client, state)
    order_mgr.sync_open_orders()
    logger.info(
        "State synced: balance=%s positions=%s open_orders=%s",
        state.balance,
        len(state.positions),
        len(state.open_orders),
    )

    exec_cfg = cfg.get("execution", {})
    dry_run = bool(exec_cfg.get("dry_run", True))
    if args.live_order:
        dry_run = False
    executor = Executor(
        client,
        state,
        risk,
        dry_run=dry_run,
        live_contracts=bool(trade.get("live_contracts", True)),
        logger=logger,
    )

    if args.place_dollar_bracket:
        if args.bracket_size is None or args.risk_usd is None or args.reward_usd is None:
            logger.error(
                "--place-dollar-bracket requires --bracket-size, --risk-usd, and --reward-usd"
            )
            return 1
        sym = str(args.bracket_symbol).upper()
        inst = imap.get(sym)
        if not inst:
            logger.error("Unknown symbol %s; add to trading.instruments in settings.yaml", sym)
            return 1
        live_override = False if args.sim_contract_search else None
        try:
            result = executor.execute_dollar_risk_bracket(
                symbol=sym,
                side=args.bracket_side,
                size=int(args.bracket_size),
                risk_usd=float(args.risk_usd),
                reward_usd=float(args.reward_usd),
                instrument_cfg=inst,
                signal_id=f"cli-dollar-{uuid.uuid4().hex[:16]}",
                custom_tag=f"cli-db-{uuid.uuid4().hex[:16]}",
                live_contracts=live_override,
                ignore_ny_session=bool(args.ignore_ny_session),
            )
            logger.info("Bracket result: %s", result)
        except RiskCheckError as e:
            logger.warning("Risk blocked: %s", e)
            return 1
        except ExecutionError as e:
            logger.error("Execution error: %s", e)
            return 1
        except Exception as e:
            logger.exception("Unexpected: %s", e)
            return 1
        if not args.live_order and bool(exec_cfg.get("dry_run", True)):
            logger.warning(
                "Preview only. Re-run with --live-order to submit (practice/live — still real orders on that account)."
            )
        return 0

    if not args.no_rtc:
        hub_url = cfg["api"].get("rtc_user_hub", "")
        if hub_url:
            UserHubListener(
                hub_url,
                auth,
                account_id,
                on_account=state.update_account_from_hub,
                on_order=state.upsert_order_from_hub,
                on_position=state.upsert_position_from_hub,
                on_trade=_on_trade(state, logger),
                logger=logger,
            ).start_background()
            logger.info("Realtime listener start requested (signalrcore)")
        else:
            logger.warning("api.rtc_user_hub empty; skipping realtime")

    if args.phoenix_scan or args.phoenix_auto:
        from projectx.strategy.phoenix_auto import (
            DedupeStore,
            arm_exchange_valid_stop_legs,
            arm_risk_reward_usd,
            entry_breakout_stop_valid,
            ensure_scripts_on_path,
            format_order_signal_message,
            format_phoenix_story,
            format_range_built_armed_message,
            in_strategy_session,
            last_range_sealed_for_session_day,
            load_arm_order_state,
            opening_range_notification_parts,
            run_scan_once,
            save_arm_order_state,
            trade_fingerprint,
        )

        ensure_scripts_on_path()
        from configs.strategy_configs import get_config as phoenix_get_config
        from configs.tick_config import TICK_SIZES, TICK_VALUES
        from engine.fast_engine import ExecutionOptions

        _fill_spec = (
            str(args.phoenix_entry_fill).lower().strip()
            if args.phoenix_entry_fill
            else str(exec_cfg.get("phoenix_entry_fill", "touch")).lower().strip()
        )
        if _fill_spec not in ("touch", "touch_legacy", "touch_strict"):
            logger.warning("Unknown phoenix_entry_fill %r; using touch", _fill_spec)
            _fill_spec = "touch"
        phoenix_execution_options = ExecutionOptions(entry_fill_mode=_fill_spec)

        instruments = [
            x.strip().upper()
            for x in args.phoenix_instruments.split(",")
            if x.strip()
        ]
        # Agent Phoenix strategies exist only for CL / MGC / MNQ / YM (engine configs). Never RTY.
        _phoenix_blocked = frozenset({"RTY", "M2K"})
        for inst in instruments:
            if inst in _phoenix_blocked:
                logger.error(
                    "Phoenix does not trade %s (stack is CL, MGC, MNQ, YM only). "
                    "Remove it from --phoenix-instruments.",
                    inst,
                )
                return 1
        sizes = _parse_phoenix_contracts(args.phoenix_contracts, instruments)
        gateway_sim = not bool(args.phoenix_live_bars)
        data_path = (
            args.phoenix_data_dir.expanduser().resolve()
            if args.phoenix_data_dir is not None
            else None
        )
        if data_path is not None and not data_path.is_dir():
            logger.error("phoenix-data-dir is not a directory: %s", data_path)
            return 1
        use_client = client if data_path is None else None
        if data_path is None and use_client is None:
            logger.error(
                "Phoenix mode needs TopstepX auth for Gateway bars, or --phoenix-data-dir for local parquet."
            )
            return 1

        state_dir = Path(__file__).resolve().parent / "strategy" / "state"
        dedupe = DedupeStore(
            state_dir / f"dedupe_{now_ny().date().isoformat()}.json"
        )
        event_dedupe = DedupeStore(
            state_dir / f"phoenix_events_{now_ny().date().isoformat()}.json"
        )
        if args.phoenix_range_resend:
            event_dedupe.remove_keys_starting_with("range_sealed|")
            logger.info("Phoenix: cleared range_sealed dedupe keys for today")
        ign_ny = not bool(args.phoenix_respect_ny_session)
        live_contract_override = False if gateway_sim else None

        peo = str(exec_cfg.get("phoenix_entry_order", "limit")).lower().strip()
        phoenix_limit_entry = peo not in ("market", "m", "false", "0", "no")
        if args.phoenix_market_entry:
            phoenix_limit_entry = False
        phoenix_arm_orders = bool(exec_cfg.get("phoenix_arm_orders", True))
        if args.phoenix_no_arm_orders:
            phoenix_arm_orders = False

        phoenix_telegram_on = bool(exec_cfg.get("phoenix_telegram", True))

        def _phoenix_notify(body: str) -> None:
            if phoenix_telegram_on and not args.phoenix_no_telegram:
                send_telegram_if_configured(body, logger=logger)
            if not args.phoenix_no_webhook:
                send_webhook_if_configured(body, logger=logger)

        _acct_tag = "?"
        try:
            for _a in client.get_accounts(True):
                if int(_a.get("id", -1)) == int(account_id):
                    _acct_tag = (
                        "practice/sim"
                        if _a.get("simulated")
                        else "live_eval_or_funded"
                    )
                    break
        except Exception:
            pass

        _mode = "phoenix-auto" if args.phoenix_auto else "phoenix-scan"
        _order_pipe = "API (real requests)" if not dry_run else "dry_run (no API orders)"
        _startup = (
            f"Phoenix started ({_mode}) — {','.join(instruments)} | "
            f"poll={args.phoenix_poll_seconds}s | {_order_pipe} | "
            f"engine_fill={_fill_spec} | "
            f"account_id={account_id} ({_acct_tag}) | "
            f"{now_ny().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        print(_startup, flush=True)
        logger.info(_startup)
        _phoenix_notify(_startup)

        _et0 = now_ny()
        if _et0.weekday() >= 5:
            _wk = (
                "Sat/Sun: fast_engine skips all bars (excluded_weekdays in strategy config), "
                "so there is no opening range or range_sealed Telegram alert — use a Mon–Fri RTH session."
            )
            print(f"Phoenix note: {_wk}", flush=True)
            logger.warning(_wk)

        range_dedupe_logged: set[str] = set()
        arm_state_path = state_dir / f"phoenix_arm_orders_{now_ny().date().isoformat()}.json"

        def _cancel_arm_orders_for_inst(inst_sym: str) -> None:
            raw = load_arm_order_state(arm_state_path)
            rec = raw.get(inst_sym)
            if not rec:
                return
            for k in ("long_oid", "short_oid"):
                oid = rec.get(k)
                if oid is None:
                    continue
                try:
                    order_mgr.cancel_order(int(oid))
                    logger.info("Phoenix arm: cancelled %s %s order_id=%s", inst_sym, k, oid)
                except Exception as e:
                    logger.warning(
                        "Phoenix arm: cancel %s %s failed: %s", inst_sym, k, e
                    )
            raw.pop(inst_sym, None)
            save_arm_order_state(arm_state_path, raw)

        def _clear_residual_open_orders_for_inst(inst_sym: str) -> None:
            """Cancel any working orders on this contract (arm legs, children, stale OIDs)."""
            state.sync_from_api()
            try:
                ct = executor.resolve_contract(
                    inst_sym, imap[inst_sym], live=live_contract_override
                )
            except Exception as e:
                logger.warning("Phoenix: resolve contract for %s: %s", inst_sym, e)
                return
            cid = ct["id"]
            oids = state.open_order_ids_for_contract(cid)
            if not oids:
                return
            logger.info(
                "Phoenix: clearing %s working order(s) on %s before entry: %s",
                len(oids),
                inst_sym,
                oids,
            )
            for oid in oids:
                try:
                    order_mgr.cancel_order(int(oid))
                    logger.info("Phoenix: cancelled working order_id=%s", oid)
                except Exception as e:
                    logger.warning("Phoenix: cancel order_id=%s failed: %s", oid, e)
            state.sync_from_api()

        def _prepare_before_phoenix_entry(inst_sym: str) -> None:
            if phoenix_arm_orders:
                _cancel_arm_orders_for_inst(inst_sym)
            _clear_residual_open_orders_for_inst(inst_sym)

        def _phoenix_arm_maintenance() -> None:
            if not phoenix_arm_orders:
                return
            state.sync_from_api()
            raw = load_arm_order_state(arm_state_path)
            now = now_ny()
            for inst_sym in list(raw.keys()):
                cfg_i = phoenix_get_config(inst_sym)
                if not in_strategy_session(now, cfg_i):
                    logger.info(
                        "Phoenix arm: closing %s (outside strategy trade window)",
                        inst_sym,
                    )
                    _cancel_arm_orders_for_inst(inst_sym)
                    continue
                try:
                    ct = executor.resolve_contract(
                        inst_sym, imap[inst_sym], live=live_contract_override
                    )
                    if state.has_position_on_contract(ct["id"]):
                        logger.info(
                            "Phoenix arm: closing %s (position open; cancel sibling stops)",
                            inst_sym,
                        )
                        _cancel_arm_orders_for_inst(inst_sym)
                except Exception as e:
                    logger.warning("Phoenix arm maintenance %s: %s", inst_sym, e)

        def _phoenix_round() -> None:
            hits, diag_by_inst, range_audit_by_inst, bars_by_inst = run_scan_once(
                instruments=instruments,
                sizes=sizes,
                data_dir=data_path,
                client=use_client,
                gateway_sim=gateway_sim,
                imap=imap,
                as_of_et=None,
                tick_sizes=TICK_SIZES,
                tick_values=TICK_VALUES,
                get_config_fn=phoenix_get_config,
                collect_diagnostics=True,
                opening_range_addon_fetch=not bool(args.phoenix_no_range_addon_fetch),
                execution_options=phoenix_execution_options,
            )
            for inst_sym in instruments:
                inst_sym = inst_sym.strip().upper()
                if inst_sym not in imap:
                    continue
                bdf = bars_by_inst.get(inst_sym)
                n = len(bdf) if bdf is not None else 0
                ts = str(bdf.index[-1]) if n else "-"
                nh = sum(1 for h in hits if h[0] == inst_sym)
                cid = "-"
                if n > 0:
                    try:
                        ct = executor.resolve_contract(
                            inst_sym,
                            imap[inst_sym],
                            live=live_contract_override,
                        )
                        cid = str(ct.get("id", "")) or "-"
                    except Exception:
                        cid = "unresolved"
                logger.info(
                    "Phoenix.parity kind=round symbol=%s contract_id=%s bars_n=%s "
                    "bars_last_ts=%s hits=%s engine_fill=%s dry_run=%s",
                    inst_sym,
                    cid,
                    n,
                    ts,
                    nh,
                    _fill_spec,
                    dry_run,
                )
            _phoenix_arm_maintenance()
            if not args.phoenix_no_engine_events:
                for inst_sym in instruments:
                    inst_sym = inst_sym.strip().upper()
                    diag = diag_by_inst.get(inst_sym) or []
                    cfg_i = phoenix_get_config(inst_sym)
                    for d in diag:
                        if d.get("kind") != "range_sealed":
                            continue
                        day = str(d.get("date") or "")
                        ev_key = f"range_sealed|{inst_sym}|{day}"
                        if ev_key in event_dedupe.load():
                            if ev_key not in range_dedupe_logged:
                                range_dedupe_logged.add(ev_key)
                                _aud = range_audit_by_inst.get(inst_sym) or {}
                                _aud_s = (
                                    f"n_bars={_aud.get('n_bars')} raw H/L={_aud.get('raw_high')}/"
                                    f"{_aud.get('raw_low')} engine_match={_aud.get('engine_match')}"
                                    if _aud.get("ok")
                                    else repr(_aud)
                                )
                                logger.info(
                                    "Phoenix: range_sealed already notified for %s (dedupe). "
                                    "Use --phoenix-range-resend or delete %s. Data: %s",
                                    ev_key,
                                    event_dedupe.path,
                                    _aud_s,
                                )
                            continue
                        _audit = range_audit_by_inst.get(inst_sym)
                        if args.phoenix_range_single_telegram:
                            msg = format_range_built_armed_message(
                                inst_sym, cfg_i, d, _audit
                            )
                            print(msg, flush=True)
                            logger.info(msg)
                            _phoenix_notify(msg)
                        else:
                            msg_sealed, msg_armed = opening_range_notification_parts(
                                inst_sym, cfg_i, d, _audit
                            )
                            msg = f"{msg_sealed}\n\n{msg_armed}"
                            print(msg, flush=True)
                            logger.info(msg)
                            _phoenix_notify(msg_sealed)
                            _phoenix_notify(msg_armed)
                        event_dedupe.add(ev_key)
            if phoenix_arm_orders and not args.phoenix_manual and not dry_run:
                session_day = now_ny().date()
                hit_insts = {h[0] for h in hits}
                for inst_sym in instruments:
                    inst_sym = inst_sym.strip().upper()
                    if inst_sym not in imap:
                        continue
                    if inst_sym in hit_insts:
                        continue
                    cfg_i = phoenix_get_config(inst_sym)
                    if not in_strategy_session(now_ny(), cfg_i):
                        continue
                    arm_rec_existing = load_arm_order_state(arm_state_path).get(
                        inst_sym
                    )
                    if arm_rec_existing and (
                        arm_rec_existing.get("long_oid") is not None
                        or arm_rec_existing.get("short_oid") is not None
                    ):
                        continue
                    diag = diag_by_inst.get(inst_sym) or []
                    seal = last_range_sealed_for_session_day(diag, session_day)
                    if not seal:
                        continue
                    bars = bars_by_inst.get(inst_sym)
                    if bars is None or len(bars) < 12:
                        continue
                    try:
                        ll = float(seal.get("long_level") or 0)
                        ss = float(seal.get("short_level") or 0)
                    except (TypeError, ValueError):
                        continue
                    if ll <= 0 or ss <= 0:
                        continue
                    tsz = float(TICK_SIZES[inst_sym])
                    tv = float(TICK_VALUES[inst_sym])
                    n = int(sizes.get(inst_sym, 1))
                    r_usd, rw_usd = arm_risk_reward_usd(
                        inst_sym, cfg_i, bars, n, tsz, tv
                    )
                    if r_usd <= 0 or rw_usd <= 0:
                        continue
                    last_px = float(bars["close"].iloc[-1])
                    place_long, place_short = arm_exchange_valid_stop_legs(
                        last_px, ll, ss, tsz
                    )
                    if not place_long and not place_short:
                        logger.warning(
                            "Phoenix arm: skip %s — no valid resting stops vs last=%s "
                            "(buy stop needs last < long %s; sell stop needs last > short %s). "
                            "Will retry next poll if price moves.",
                            inst_sym,
                            last_px,
                            ll,
                            ss,
                        )
                        continue
                    if not place_long:
                        logger.info(
                            "Phoenix arm: %s skip buy stop (market at/above long %s, last=%s); "
                            "sell stop only",
                            inst_sym,
                            ll,
                            last_px,
                        )
                    if not place_short:
                        logger.info(
                            "Phoenix arm: %s skip sell stop (market at/below short %s, last=%s); "
                            "buy stop only",
                            inst_sym,
                            ss,
                            last_px,
                        )
                    try:
                        res = executor.execute_phoenix_arm_breakout_pair(
                            symbol=inst_sym,
                            size=n,
                            long_stop_price=ll,
                            short_stop_price=ss,
                            risk_usd=r_usd,
                            reward_usd=rw_usd,
                            instrument_cfg=imap[inst_sym],
                            signal_id_long=f"phoenix-arm-{inst_sym}-L-{uuid.uuid4().hex[:12]}",
                            signal_id_short=f"phoenix-arm-{inst_sym}-S-{uuid.uuid4().hex[:12]}",
                            custom_tag_long=f"phx-arm-{inst_sym}-L-{uuid.uuid4().hex[:8]}",
                            custom_tag_short=f"phx-arm-{inst_sym}-S-{uuid.uuid4().hex[:8]}",
                            live_contracts=live_contract_override,
                            ignore_ny_session=ign_ny,
                            place_long=place_long,
                            place_short=place_short,
                        )
                    except RiskCheckError as e:
                        logger.info(
                            "Phoenix.parity kind=skip bucket=risk_arm symbol=%s detail=%s",
                            inst_sym,
                            e,
                        )
                        logger.warning("Phoenix arm risk blocked %s: %s", inst_sym, e)
                        continue
                    except ExecutionError as e:
                        logger.error("Phoenix arm execution error %s: %s", inst_sym, e)
                        continue
                    if isinstance(res, dict) and res.get("dry_run"):
                        continue
                    lo = (res.get("long") or {}).get("orderId")
                    so = (res.get("short") or {}).get("orderId")
                    arm_rec = {
                        "long_oid": int(lo) if lo is not None else None,
                        "short_oid": int(so) if so is not None else None,
                    }
                    merged = load_arm_order_state(arm_state_path)
                    merged[inst_sym] = arm_rec
                    save_arm_order_state(arm_state_path, merged)
                    logger.info(
                        "Phoenix arm: placed buy/sell stops for %s long_oid=%s short_oid=%s",
                        inst_sym,
                        arm_rec["long_oid"],
                        arm_rec["short_oid"],
                    )
            if args.phoenix_poll_status:
                for inst_sym in instruments:
                    inst_sym = inst_sym.strip().upper()
                    diag = diag_by_inst.get(inst_sym)
                    if not diag:
                        continue
                    cfg_i = phoenix_get_config(inst_sym)
                    line = format_phoenix_story(
                        inst_sym, cfg_i, diag, compact=True
                    )
                    if line:
                        print(line, flush=True)
                        logger.info(line)
            for inst, tr, r_usd, rw_usd in hits:
                fp = trade_fingerprint(inst, tr)
                if fp in dedupe.load():
                    logger.info(
                        "Phoenix.parity kind=skip bucket=dedupe symbol=%s fingerprint=%s",
                        inst,
                        fp,
                    )
                    continue
                if not in_strategy_session(now_ny(), phoenix_get_config(inst)):
                    logger.info(
                        "Phoenix.parity kind=skip bucket=outside_trade_window symbol=%s",
                        inst,
                    )
                    logger.warning(
                        "Phoenix skip %s: entry outside strategy trade window (unexpected)",
                        inst,
                    )
                    continue
                side = str(tr["direction"])
                placement_msg = ""
                limit_px: float | None = None
                if phoenix_limit_entry:
                    try:
                        limit_px = float(tr.get("entry_price", 0) or 0)
                    except (TypeError, ValueError):
                        limit_px = 0.0
                    if limit_px <= 0:
                        logger.info(
                            "Phoenix.parity kind=skip bucket=invalid_entry_price symbol=%s "
                            "entry_price=%r",
                            inst,
                            tr.get("entry_price"),
                        )
                        logger.error(
                            "Phoenix skip %s: invalid entry_price for stop trigger: %r",
                            inst,
                            tr.get("entry_price"),
                        )
                        continue
                    bdf = bars_by_inst.get(inst)
                    if bdf is not None and len(bdf) > 0:
                        last_px = float(bdf["close"].iloc[-1])
                        tsz = float(TICK_SIZES.get(inst, 0.25))
                        if not entry_breakout_stop_valid(
                            side, limit_px, last_px, tsz
                        ):
                            logger.info(
                                "Phoenix.parity kind=skip bucket=entry_breakout_stop_invalid "
                                "symbol=%s side=%s trigger=%s last_close=%s",
                                inst,
                                side,
                                limit_px,
                                last_px,
                            )
                            logger.info(
                                "Phoenix %s: skip API entry — resting stop at trigger %s "
                                "invalid vs last bar close=%s (already through level). "
                                "No market chase; working short/long arm orders unchanged.",
                                inst,
                                limit_px,
                                last_px,
                            )
                            dedupe.add(fp)
                            continue
                use_trigger_stop = limit_px is not None
                logger.info(
                    "Phoenix NEW entry %s %s risk=$%.2f reward=$%.2f trade=%s",
                    inst,
                    side,
                    r_usd,
                    rw_usd,
                    tr,
                )
                order_line = format_order_signal_message(
                    inst,
                    side,
                    tr,
                    use_limit=use_trigger_stop,
                )
                print(order_line, flush=True)
                logger.info(order_line)
                if args.phoenix_manual:
                    tv = float(TICK_VALUES.get(inst, 0.5))
                    placement_msg = _phoenix_placement_instructions_text(
                        inst=inst,
                        tr=tr,
                        side=side,
                        contracts=int(sizes.get(inst, 1)),
                        r_usd=r_usd,
                        rw_usd=rw_usd,
                        use_limit=use_trigger_stop,
                        tick_value=tv,
                        api_sends_order=False,
                    )
                    print(placement_msg, flush=True)
                    logger.info(placement_msg)
                    dedupe.add(fp)
                    _phoenix_notify(f"{order_line}\n{placement_msg}")
                    continue
                if not args.phoenix_no_placement_print:
                    tv = float(TICK_VALUES.get(inst, 0.5))
                    placement_msg = _phoenix_placement_instructions_text(
                        inst=inst,
                        tr=tr,
                        side=side,
                        contracts=int(sizes.get(inst, 1)),
                        r_usd=r_usd,
                        rw_usd=rw_usd,
                        use_limit=use_trigger_stop,
                        tick_value=tv,
                        api_sends_order=True,
                    )
                    print(placement_msg, flush=True)
                    logger.info(placement_msg)

                def _place_phoenix_bracket() -> Any:
                    return executor.execute_dollar_risk_bracket(
                        symbol=inst,
                        side=side,
                        size=int(sizes.get(inst, 1)),
                        risk_usd=r_usd,
                        reward_usd=rw_usd,
                        instrument_cfg=imap[inst],
                        signal_id=f"phoenix-{uuid.uuid4().hex[:16]}",
                        custom_tag=f"phx-{inst}-{uuid.uuid4().hex[:8]}",
                        live_contracts=live_contract_override,
                        ignore_ny_session=ign_ny,
                        limit_entry_price=limit_px,
                    )

                if not dry_run:
                    _prepare_before_phoenix_entry(inst)
                try:
                    res = _place_phoenix_bracket()
                    logger.info("Phoenix order result: %s", res)
                    if isinstance(res, dict) and res.get("dry_run"):
                        logger.info(
                            "Phoenix.parity kind=order bucket=dry_run symbol=%s",
                            inst,
                        )
                    if isinstance(res, dict) and not res.get("dry_run"):
                        dedupe.add(fp)
                        _phoenix_notify(f"{order_line}\n{placement_msg}")
                except RiskCheckError as e:
                    logger.info(
                        "Phoenix.parity kind=skip bucket=risk symbol=%s detail=%s",
                        inst,
                        e,
                    )
                    logger.warning("Phoenix risk blocked %s: %s", inst, e)
                except ExecutionError as e:
                    logger.info(
                        "Phoenix.parity kind=skip bucket=execution_error symbol=%s detail=%s",
                        inst,
                        e,
                    )
                    logger.error("Phoenix execution error %s: %s", inst, e)
                    if (
                        not dry_run
                        and "open orders exist" in str(e).lower()
                    ):
                        _prepare_before_phoenix_entry(inst)
                        try:
                            res = _place_phoenix_bracket()
                            logger.info(
                                "Phoenix order result (retry): %s", res
                            )
                            if isinstance(res, dict) and not res.get("dry_run"):
                                dedupe.add(fp)
                                _phoenix_notify(
                                    f"{order_line}\n{placement_msg}"
                                )
                        except ExecutionError as e2:
                            logger.info(
                                "Phoenix.parity kind=skip bucket=execution_error symbol=%s "
                                "detail=%s phase=retry",
                                inst,
                                e2,
                            )
                            logger.error(
                                "Phoenix execution error %s (retry): %s",
                                inst,
                                e2,
                            )
                            dedupe.add(fp)

        try:
            if args.phoenix_scan and not args.phoenix_auto:
                _phoenix_round()
            else:
                logger.info(
                    "Phoenix auto every %ss — dry_run=%s — entry=%s — arm_orders=%s — manual=%s "
                    "placement_print=%s — Ctrl+C to stop",
                    args.phoenix_poll_seconds,
                    dry_run,
                    "STOP@engine_trigger" if phoenix_limit_entry else "MARKET",
                    phoenix_arm_orders,
                    args.phoenix_manual,
                    not args.phoenix_no_placement_print and not args.phoenix_manual,
                )
                while True:
                    _phoenix_round()
                    time.sleep(float(args.phoenix_poll_seconds))
        except KeyboardInterrupt:
            logger.info("Phoenix auto stopped.")
        return 0

    if args.session:
        from projectx.signal_runner import _default_inbox, start_signal_watcher_thread

        inbox = args.signals_dir if args.signals_dir is not None else _default_inbox()
        _, watcher_stop = start_signal_watcher_thread(
            inbox,
            float(args.poll_signals_seconds),
            executor,
            imap,
            logger,
        )
        logger.info(
            "Session mode — drop JSON signals into: %s",
            inbox.resolve(),
        )
        logger.info(
            "dry_run=%s (set execution.dry_run: false in settings.yaml or use --live-order to send orders)",
            dry_run,
        )
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Session stopped (Ctrl+C).")
            watcher_stop.set()
        return 0

    # --- Phase 1: mock signals (skipped when only listing / bracket handled above) ---
    if args.demo_risk_block:
        bad = _mock_signal_risk_fail()
        logger.info("Demo: risk should block: %s", bad)
        try:
            risk.validate_signal(bad)
            logger.error("Risk incorrectly allowed bad signal")
            return 1
        except RiskCheckError as e:
            logger.info("Risk blocked as expected: %s", e)

    ok_signal = _mock_signal_ok()
    logger.info("Mock signal (executor): %s", ok_signal)
    try:
        inst = imap.get(str(ok_signal["symbol"]).upper())
        if not inst:
            logger.error("Unknown symbol in mock signal; add to settings instruments")
            return 1
        result = executor.execute_signal(ok_signal, inst)
        logger.info("Executor result: %s", result)
    except RiskCheckError as e:
        logger.warning("Risk blocked mock signal: %s", e)
    except ExecutionError as e:
        logger.error("Execution error: %s", e)
    except Exception as e:
        logger.exception("Unexpected: %s", e)
        return 1

    logger.info("Startup complete (NY time %s). Phase 1 runner idle.", now_ny())
    return 0


def _on_trade(state: StateManager, logger: Any):
    def _handler(trade: dict[str, Any]) -> None:
        if trade.get("voided"):
            return
        pnl = trade.get("profitAndLoss")
        try:
            pnl_f = float(pnl) if pnl is not None else None
        except (TypeError, ValueError):
            pnl_f = None
        state.record_trade_fill(pnl_f)
        logger.info(
            "Trade event: contractId=%s size=%s pnl=%s",
            trade.get("contractId"),
            trade.get("size"),
            pnl_f,
        )

    return _handler


def _mock_signal_risk_fail() -> dict[str, Any]:
    return {
        "symbol": "MNQ",
        "side": "long",
        "size": 999,
        "entry_type": "market",
        "stop_loss": 100.0,
        "take_profit": 200.0,
        "reference_price": 150.0,
    }


def _mock_signal_ok() -> dict[str, Any]:
    """Bracket ticks are illustrative; replace reference/SL/TP with live values."""
    return {
        "symbol": "MNQ",
        "side": "long",
        "size": 1,
        "entry_type": "market",
        "reference_price": 20000.0,
        "stop_loss": 19990.0,
        "take_profit": 20030.0,
        "signal_id": "phase1-mock-1",
        "custom_tag": "projectx-phase1",
    }


if __name__ == "__main__":
    _sd = Path(__file__).resolve().parents[1] / "scripts"
    if str(_sd) not in sys.path:
        sys.path.insert(0, str(_sd))
    from telegram_script_done import run_with_telegram

    sys.exit(run_with_telegram(main, script_name="projectx.main"))
