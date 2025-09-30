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
    if dry_run:
        logger.info("Dry-run: would execute order: %s %s", prepared.symbol, prepared.quantity)
        return {"status": "simulated", "symbol": prepared.symbol, "quantity": prepared.quantity}

    # live path: call client's placeOrder or Prepare/Transmit pattern
    try:
        # adapt to IB wrapper: some clients expect contract + order object
        res = ib_client.place_order(prepared.symbol, prepared.quantity, prepared.order_type)
        logger.info("Order executed: %s", res)
        return {"status": "placed", "result": res}
    except Exception as e:
        logger.exception("Order execution failed")
        return {"status": "failed", "error": str(e)}


