"""Order preparation helpers with dry-run safety.

This module prepares order payloads and (in live mode) sends them via the
provided IB client. In dry-run, orders are only prepared and logged.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PreparedOrder:
    symbol: str
    quantity: int
    order_type: str
    details: Dict[str, Any]


def prepare_close_order(symbol: str, quantity: int, order_type: str = "MKT") -> PreparedOrder:
    return PreparedOrder(symbol=symbol, quantity=quantity, order_type=order_type, details={"prepared_at": "TODO"})


def execute_order(ib_client: Any, prepared: PreparedOrder, dry_run: bool = True) -> Dict[str, Any]:
    """Execute or simulate an order using provided `ib_client`.

    Returns a dict with execution metadata.
    """
    # Always build a prepared object in our IB wrapper so we can log/inspect it
    try:
        # If ib_client has prepare_order (preferred), use it to build a prepared order
        if hasattr(ib_client, 'prepare_order'):
            prepared_ib = ib_client.prepare_order(prepared.symbol, prepared.quantity, prepared.order_type)
        else:
            # fallback: caller provided only a simple prepared order; attempt to transmit directly
            prepared_ib = None
    except Exception as e:
        logger.exception('Failed to prepare IB order')
        return {'status': 'failed_prepare', 'error': str(e)}

    # Dry-run path: log prepared IB order and return simulated status
    if dry_run:
        logger.info('Dry-run: prepared order: %s (ib_prepared=%s)', prepared, bool(prepared_ib))
        return {'status': 'simulated', 'symbol': prepared.symbol, 'quantity': prepared.quantity, 'prepared_ib': bool(prepared_ib)}

    # Live path: run pre-submit safety checks
    try:
        # re-fetch authoritative positions and open orders
        try:
            current_positions = ib_client.positions()
        except Exception:
            current_positions = None
        try:
            current_open_orders = ib_client.openOrders()
        except Exception:
            current_open_orders = None

        logger.info('Pre-submit checks: positions=%s open_orders=%s', bool(current_positions), bool(current_open_orders))

        # transmit: delegate to order_manager for full lifecycle handling
        if prepared_ib:
            prepared_payload = prepared_ib
        else:
            prepared_payload = {
                'symbol': prepared.symbol,
                'quantity': prepared.quantity,
                'order_type': prepared.order_type,
            }

        if dry_run:
            # keep existing dry-run behavior
            logger.info('Dry-run: prepared order: %s (ib_prepared=%s)', prepared, bool(prepared_ib))
            return {'status': 'simulated', 'symbol': prepared.symbol, 'quantity': prepared.quantity, 'prepared_ib': bool(prepared_ib)}

        # live: import and call order_manager
        try:
            from . import order_manager
        except Exception:
            # fallback to simple place if order_manager unavailable
            if prepared_ib:
                res = ib_client.place_order(prepared_ib, transmit=True)
            else:
                res = ib_client.place_order(prepared.symbol, prepared.quantity, prepared.order_type, transmit=True)
            logger.info('Order transmitted (fallback): %s', res)
            return {'status': 'placed', 'result': res}

        # call the manager which handles wait/cancel/verify
        lifecycle_res = order_manager.place_and_finalize(ib_client, prepared_payload)
        logger.info('Order lifecycle result: %s', lifecycle_res)
        return lifecycle_res
    except Exception as e:
        logger.exception('Order transmit failed')
        return {'status': 'failed_transmit', 'error': str(e)}


