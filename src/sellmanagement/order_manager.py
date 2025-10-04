"""Order lifecycle manager: place -> wait-for-fill -> cancel outstanding -> verify.

This module implements a conservative, timeboxed workflow for live order
transmission. It uses `IBClient` methods (place_order, cancel_order,
openOrders, positions) and never performs aggressive automatic resubmits.
"""
from __future__ import annotations
import time
from typing import Any, Dict, List


DEFAULT_FILL_TIMEOUT = 15  # seconds
DEFAULT_CANCEL_VERIFY_RETRIES = 5
DEFAULT_CANCEL_VERIFY_DELAY = 1.5  # seconds


def find_orders_for_symbol(open_orders: List[Any], symbol: str) -> List[Any]:
    out: List[Any] = []
    for o in (open_orders or []):
        try:
            # try to extract contract symbol/exchange
            contract = getattr(o, 'contract', None) or getattr(o, 'order', None)
            sym = None
            if contract is not None:
                sym = getattr(contract, 'symbol', None) or getattr(contract, 'localSymbol', None)
            # fallback: if order has .symbol or .ticker fields
            if sym is None:
                sym = getattr(o, 'symbol', None) or getattr(o, 'ticker', None)
            if sym:
                # token may be EXCHANGE:SYM or SYM; check suffix
                if symbol.endswith(f":{sym}") or symbol.endswith(sym):
                    out.append(o)
        except Exception:
            continue
    return out


def place_and_finalize(ib_client, prepared_order: Dict[str, Any], timeout: int = DEFAULT_FILL_TIMEOUT) -> Dict[str, Any]:
    """Place an IB order and follow through until filled/cancelled/timeout.

    Returns a dict with detailed results.
    """
    result: Dict[str, Any] = {
        'status': 'unknown',
        'placed_trade': None,
        'cancelled': [],
        'positions_before': None,
        'positions_after': None,
        'open_orders_before': None,
        'open_orders_after': None,
    }

    # snapshot before
    try:
        result['positions_before'] = ib_client.positions()
    except Exception:
        result['positions_before'] = None
    try:
        result['open_orders_before'] = ib_client.openOrders()
    except Exception:
        result['open_orders_before'] = None

    # place order
    placed = ib_client.place_order(prepared_order, transmit=True)
    result['placed'] = placed
    trade = placed.get('trade')
    result['placed_trade'] = trade

    # wait for fill or timeout
    deadline = time.time() + timeout
    final_status = 'timeout'
    try:
        while time.time() < deadline:
            if trade is None:
                # no trade object returned; break and treat as placed
                break
            stat = ib_client.get_trade_status(trade)
            if stat == 'filled' or stat == 'done':
                final_status = 'filled'
                break
            if stat == 'cancelled':
                final_status = 'cancelled'
                break
            time.sleep(0.5)
    except Exception:
        final_status = 'error'

    result['status'] = final_status

    # on filled: cancel outstanding orders for symbol and verify
    if final_status == 'filled':
        try:
            open_after = ib_client.openOrders()
        except Exception:
            open_after = None
        result['open_orders_after'] = open_after

        # identify orders for the symbol
        symbol = prepared_order.get('symbol') or prepared_order.get('token')
        outstanding = find_orders_for_symbol(open_after, symbol) if open_after else []
        cancelled = []
        for o in outstanding:
            try:
                cres = ib_client.cancel_order(o)
                # verify cancel via re-fetch
                verified = False
                for _ in range(DEFAULT_CANCEL_VERIFY_RETRIES):
                    time.sleep(DEFAULT_CANCEL_VERIFY_DELAY)
                    cur = ib_client.openOrders()
                    if o not in (cur or []):
                        verified = True
                        break
                cancelled.append({'order': str(o), 'cancel_sent': cres, 'verified': verified})
            except Exception as e:
                cancelled.append({'order': str(o), 'error': str(e)})
        result['cancelled'] = cancelled

        # final positions check
        try:
            result['positions_after'] = ib_client.positions()
        except Exception:
            result['positions_after'] = None

    else:
        # not filled: capture snapshots and return
        try:
            result['open_orders_after'] = ib_client.openOrders()
        except Exception:
            result['open_orders_after'] = None
        try:
            result['positions_after'] = ib_client.positions()
        except Exception:
            result['positions_after'] = None

    return result


