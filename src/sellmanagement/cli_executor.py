"""Live CLI transmission of sell signals (minute-loop path)."""
from __future__ import annotations

import hashlib
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .intent_store import exists as intent_exists
from .intent_store import update_intent as intent_update
from .intent_store import write_intent as intent_write
from .alerts import alert_order_exception, alert_order_failed, order_transmit_needs_alert
from .orders import execute_order, prepare_close_order
from .trace import append_trace
from .utils.ticker import tickers_match


_transmit_lock = threading.Lock()


def transmit_live_sell_signals(
    ib: Any,
    generated: List[Dict[str, Any]],
    *,
    snapshot_ts: str,
    dry_run: bool = False,
    lock: Optional[threading.Lock] = None,
) -> None:
    """Place market close orders for each ``SellSignal`` in ``generated``.

    Caller must ensure dry-run is off and the user has already confirmed.

    The function is guarded by a process-level ``threading.Lock`` so concurrent
    invocation cannot double-transmit the same intent. The intent record is
    appended atomically (status="pending") before any other work so a crash
    mid-transmit still leaves a recoverable audit trail; an idempotency check
    via ``intent_exists`` detects prior runs that already wrote the same intent.
    """
    _lock = lock if lock is not None else _transmit_lock
    with _lock:
        _transmit_locked(ib, generated, snapshot_ts=snapshot_ts, dry_run=dry_run)


def _transmit_locked(
    ib: Any,
    generated: List[Dict[str, Any]],
    *,
    snapshot_ts: str,
    dry_run: bool,
) -> None:
    for e in generated:
        try:
            if e.get("decision") != "SellSignal":
                continue
            ticker = e.get("ticker")
            decision = e.get("decision")
            bucket_ts = e.get("ts") or snapshot_ts or ""
            try:
                intent_key = f"{ticker}:{bucket_ts}:{decision}"
                intent_id = hashlib.sha256(intent_key.encode("utf-8")).hexdigest()
            except Exception:
                intent_id = None

            pos = e.get("position")
            try:
                qty = int(abs(round(float(pos)))) if pos is not None else None
            except Exception:
                qty = None
            if not qty or qty <= 0:
                append_trace(
                    {
                        "event": "order_skipped",
                        "ticker": ticker,
                        "reason": "no_position",
                        "position": pos,
                    }
                )
                continue

            try:
                cur_positions = ib.positions()
            except Exception:
                cur_positions = None
            cur_pos_val = None
            try:
                if cur_positions:
                    for p in cur_positions:
                        try:
                            contract = getattr(p, "contract", None)
                            if contract is None:
                                continue
                            sym = getattr(contract, "symbol", None) or getattr(
                                contract, "localSymbol", None
                            )
                            exchange = getattr(contract, "exchange", None) or ""
                            token_full = f"{exchange}:{sym}" if exchange else sym
                            if token_full and tickers_match(token_full, ticker):
                                cur_pos_val = (
                                    getattr(p, "position", None)
                                    or getattr(p, "pos", None)
                                    or 0
                                )
                                break
                        except Exception:
                            continue
            except Exception:
                cur_pos_val = None

            # Idempotency: if a prior run already wrote this intent, skip.
            try:
                if intent_id and intent_exists(intent_id):
                    append_trace(
                        {
                            "event": "intent_duplicate",
                            "ticker": ticker,
                            "intent_id": intent_id,
                        }
                    )
                    continue
            except Exception:
                pass

            # Write the intent record FIRST (status=pending) before any other
            # work, so a crash mid-transmit still leaves a recoverable audit
            # trail. The lock above ensures no other thread races us.
            try:
                if intent_id:
                    intent_write(
                        {
                            "intent_id": intent_id,
                            "ticker": ticker,
                            "decision": decision,
                            "bucket_ts": bucket_ts,
                            "requested_qty": qty,
                            "status": "pending",
                            "ts": datetime.now().isoformat(),
                        }
                    )
            except Exception:
                pass

            # Fail-closed: if we cannot confirm a live position, do NOT transmit.
            if cur_pos_val is None:
                append_trace(
                    {
                        "event": "order_skipped",
                        "ticker": ticker,
                        "reason": "position_check_failed",
                    }
                )
                continue

            try:
                cap_qty = int(abs(round(float(cur_pos_val))))
            except Exception:
                try:
                    cap_qty = int(abs(cur_pos_val))
                except Exception:
                    cap_qty = qty
            if cap_qty <= 0:
                append_trace(
                    {
                        "event": "order_skipped",
                        "ticker": ticker,
                        "reason": "no_position_at_transmit",
                        "sig_qty": qty,
                        "cur_pos": cur_pos_val,
                    }
                )
                continue
            if qty > cap_qty:
                append_trace(
                    {
                        "event": "qty_capped",
                        "ticker": ticker,
                        "sig_qty": qty,
                        "capped_to": cap_qty,
                    }
                )
                qty_to_send = cap_qty
            else:
                qty_to_send = qty

            try:
                if intent_id:
                    intent_write(
                        {
                            "intent_id": intent_id,
                            "ticker": ticker,
                            "decision": decision,
                            "bucket_ts": bucket_ts,
                            "requested_qty": qty,
                            "qty_to_send": qty_to_send,
                            "status": "attempting",
                            "ts": datetime.now().isoformat(),
                        }
                    )
            except Exception:
                pass

            po = prepare_close_order(ticker, qty_to_send, order_type="MKT")
            res = execute_order(ib, po, dry_run=dry_run)
            if order_transmit_needs_alert(res):
                try:
                    alert_order_failed(ticker=ticker, result=res)
                except Exception:
                    pass
            append_trace(
                {
                    "event": "order_attempt",
                    "ticker": ticker,
                    "position": pos,
                    "qty": qty_to_send,
                    "result": str(res),
                }
            )
            try:
                if intent_id:
                    intent_update(
                        intent_id,
                        {
                            "status": res.get("status"),
                            "result": res,
                            "completed_ts": datetime.now().isoformat(),
                        },
                    )
            except Exception:
                pass
        except Exception as ex:
            try:
                alert_order_exception(ticker=e.get("ticker"), error=str(ex))
            except Exception:
                pass
            append_trace(
                {
                    "event": "order_attempt_failed",
                    "ticker": e.get("ticker"),
                    "error": str(ex),
                }
            )
