"""Lightweight IB client wrapper used by the CLI.

This module provides a minimal `IBClient` class that attempts to use
`ib_insync.IB` when available and otherwise falls back to a harmless
fake implementation useful for dry-run/manual testing.

The implementation intentionally keeps the surface area small: the
CLI expects methods named `connect`, `disconnect`, `download_daily`,
`download_halfhours`, `positions` and `openOrders`.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Any


class IBClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 4001, client_id: int = 1, use_rth: bool = True):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.use_rth = use_rth
        self._ib = None
        self._use_ib = False
        self._connected = False

    def connect(self, timeout: int = 10) -> bool:
        """Connect to IB Gateway/TWS using ib_insync.IB.

        This method requires `ib_insync` to be installed and a reachable IB
        Gateway/TWS at `host:port`. On failure it raises a RuntimeError with a
        helpful message.
        """
        # Ensure an asyncio event loop exists on the main thread before importing
        # `ib_insync` / `eventkit` which may request the current loop at import time.
        import asyncio
        try:
            # This will raise RuntimeError on Python >=3.10 if no loop is set.
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

        try:
            from ib_insync import IB
        except Exception as e:  # pragma: no cover - environment dependent
            raise RuntimeError("ib_insync is required for live IB connections; install it (pip install ib_insync)") from e

        self._ib = IB()
        try:
            self._ib.connect(self.host, self.port, clientId=self.client_id, timeout=timeout)
            self._use_ib = True
            self._connected = self._ib.isConnected()
            if not self._connected:
                raise RuntimeError(f"Failed to connect to IB at {self.host}:{self.port}")
            return True
        except Exception as e:
            self._ib = None
            self._use_ib = False
            self._connected = False
            raise RuntimeError(f"Failed to connect to IB: {e}") from e

    def disconnect(self) -> None:
        if self._use_ib and self._ib is not None:
            try:
                self._ib.disconnect()
            except Exception:
                pass
        self._connected = False

    def download_daily(self, token: str, duration: str = "1 Y") -> List[Dict[str, Any]]:
        """Download daily bars for token.
        """
        if not self._use_ib or self._ib is None:
            raise RuntimeError("IBClient.download_daily requires a live ib_insync connection")

        # build contract from token expected in format EXCHANGE:SYMBOL or SYMBOL
        try:
            from ib_insync import Stock
        except Exception:  # pragma: no cover - environment dependent
            raise RuntimeError("ib_insync is required for historical downloads")

        # token expected like 'NASDAQ:NVDA' or 'NVDA'
        parts = token.split(":")
        if len(parts) == 2:
            exchange, symbol = parts[0], parts[1]
        else:
            exchange = 'SMART'
            symbol = token

        contract = Stock(symbol, exchange, 'USD')
        # request historical data (ib_insync returns bars as list[BarData])
        bars = self._ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr=duration,
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=self.use_rth,
            formatDate=1,
        )

        out: List[Dict[str, Any]] = []
        for b in bars:
            # b.date may be date or string depending on formatDate
            d = getattr(b, 'date', None)
            if hasattr(d, 'isoformat'):
                date_s = d.isoformat()
            else:
                date_s = str(d)
            out.append({
                'Date': date_s,
                'Open': float(getattr(b, 'open', b.open) if hasattr(b, 'open') else b.open),
                'High': float(getattr(b, 'high', b.high) if hasattr(b, 'high') else b.high),
                'Low': float(getattr(b, 'low', b.low) if hasattr(b, 'low') else b.low),
                'Close': float(getattr(b, 'close', b.close) if hasattr(b, 'close') else b.close),
                'Volume': int(getattr(b, 'volume', b.volume) if hasattr(b, 'volume') else b.volume),
            })
        return out

    def download_halfhours(self, token: str, duration: str = "31 D", end: str | None = None) -> List[Dict[str, Any]]:
        """Return 30-minute bars for token using ib_insync historical request.

        `end` may be an ISO datetime string accepted by IB.
        Returns list of dicts newest-last.
        """
        if not self._use_ib or self._ib is None:
            raise RuntimeError("IBClient.download_halfhours requires a live ib_insync connection")

        try:
            from ib_insync import Stock
        except Exception:  # pragma: no cover - environment dependent
            raise RuntimeError("ib_insync is required for historical downloads")

        parts = token.split(":")
        if len(parts) == 2:
            exchange, symbol = parts[0], parts[1]
        else:
            exchange = 'SMART'
            symbol = token

        contract = Stock(symbol, exchange, 'USD')

        # Normalize end datetime into an IB-acceptable format. IB accepts
        # UTC-formatted strings like 'yyyymmdd-HH:MM:SS' or local TZ variants.
        end_dt = ''
        if end:
            try:
                # try ISO parsing first (handles offsets)
                dt = datetime.fromisoformat(end)
            except Exception:
                try:
                    # fallback: try parsing common naive datetime string
                    dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                except Exception:
                    # give IB the raw string as a last resort
                    end_dt = end
                    dt = None
            if dt is not None:
                # assume America/New_York when no tzinfo provided
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
                # convert to UTC and format as IB's UTC notation
                dt_utc = dt.astimezone(ZoneInfo("UTC"))
                end_dt = dt_utc.strftime('%Y%m%d-%H:%M:%S')

        bars = self._ib.reqHistoricalData(
            contract,
            endDateTime=end_dt or '',
            durationStr=duration,
            barSizeSetting='30 mins',
            whatToShow='TRADES',
            useRTH=self.use_rth,
            formatDate=1,
        )

        out: List[Dict[str, Any]] = []
        for b in bars:
            d = getattr(b, 'date', None)
            if hasattr(d, 'isoformat'):
                date_s = d.isoformat()
            else:
                date_s = str(d)
            out.append({
                'Date': date_s,
                'Open': float(getattr(b, 'open', b.open) if hasattr(b, 'open') else b.open),
                'High': float(getattr(b, 'high', b.high) if hasattr(b, 'high') else b.high),
                'Low': float(getattr(b, 'low', b.low) if hasattr(b, 'low') else b.low),
                'Close': float(getattr(b, 'close', b.close) if hasattr(b, 'close') else b.close),
                'Volume': int(getattr(b, 'volume', b.volume) if hasattr(b, 'volume') else b.volume),
            })
        return out

    def positions(self) -> List[Any]:
        if not self._use_ib or self._ib is None:
            raise RuntimeError("IBClient.positions requires a live ib_insync connection")
        return self._ib.positions()

    def openOrders(self) -> List[Any]:
        if not self._use_ib or self._ib is None:
            raise RuntimeError("IBClient.openOrders requires a live ib_insync connection")
        return self._ib.openOrders()

    def prepare_order(self, token: str, quantity: int, order_type: str = "MKT", **kwargs) -> Dict[str, Any]:
        """Prepare an IB order object for the given token and quantity without transmitting it.

        Returns a dict containing 'contract' and 'order' plus metadata. This does NOT submit anything to IB,
        it merely builds the objects so the caller can inspect/log them before transmitting.
        """
        if not self._use_ib or self._ib is None:
            raise RuntimeError("IBClient.prepare_order requires a live ib_insync connection")

        try:
            from ib_insync import Stock, MarketOrder, LimitOrder
        except Exception:
            raise RuntimeError("ib_insync is required to build IB order objects")

        parts = token.split(":")
        if len(parts) == 2:
            exchange, symbol = parts[0], parts[1]
        else:
            exchange = 'SMART'
            symbol = token

        contract = Stock(symbol, exchange, 'USD')

        # Simple order factory: support 'MKT' and 'LMT' (limit via kwargs['limit_price'])
        ot = (order_type or "MKT").upper()
        if ot == 'MKT':
            order = MarketOrder('SELL', quantity)
        elif ot == 'LMT' or ot == 'LIMIT':
            limit_price = kwargs.get('limit_price')
            if limit_price is None:
                raise ValueError('limit_price is required for LMT orders')
            order = LimitOrder('SELL', quantity, limit_price)
        else:
            # fallback to market order for unknown types
            order = MarketOrder('SELL', quantity)

        prepared = {
            'contract': contract,
            'order': order,
            'symbol': token,
            'quantity': quantity,
            'order_type': ot,
        }
        return prepared

    def place_order(self, prepared_or_token, quantity: int | None = None, order_type: str | None = None, transmit: bool = True, **kwargs) -> Dict[str, Any]:
        """Transmit a prepared order (preferred) or build+transmit from token/quantity/order_type.

        Returns a dict with status and the IB order/openOrder information when available.
        """
        if not self._use_ib or self._ib is None:
            raise RuntimeError("IBClient.place_order requires a live ib_insync connection")

        # accept either prepared dict or token
        if isinstance(prepared_or_token, dict) and 'contract' in prepared_or_token and 'order' in prepared_or_token:
            contract = prepared_or_token['contract']
            order = prepared_or_token['order']
        else:
            # build on-the-fly
            if quantity is None or order_type is None:
                raise ValueError('quantity and order_type required when not passing a prepared order')
            prepared = self.prepare_order(prepared_or_token, quantity, order_type, **kwargs)
            contract = prepared['contract']
            order = prepared['order']

        # ensure transmit flag is set on the order object if supported
        try:
            setattr(order, 'transmit', bool(transmit))
        except Exception:
            pass

        try:
            # ib_insync IB.placeOrder will send the order to IB and return an OrderStatus/Trade depending
            trade = self._ib.placeOrder(contract, order)
            return {'status': 'placed', 'trade': trade}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def cancel_order(self, order_or_trade) -> Dict[str, Any]:
        """Cancel an outstanding IB order. Accepts either an Order object or a Trade.

        Returns a small dict describing the cancel attempt.
        """
        if not self._use_ib or self._ib is None:
            raise RuntimeError("IBClient.cancel_order requires a live ib_insync connection")

        try:
            # If a Trade was passed, extract the .order where possible
            order_obj = getattr(order_or_trade, 'order', order_or_trade)
            # call ib_insync cancel
            self._ib.cancelOrder(order_obj)
            return {'status': 'cancel_sent'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def get_trade_status(self, trade) -> str:
        """Return a normalized status string for an ib_insync Trade object.

        Possible outputs: 'filled', 'cancelled', 'done', 'pending', 'unknown'
        """
        try:
            # prefer orderStatus.status when available
            os = getattr(getattr(trade, 'orderStatus', None), 'status', None)
            if isinstance(os, str):
                stat = os.lower()
                if 'filled' in stat:
                    return 'filled'
                if 'cancel' in stat:
                    return 'cancelled'
                if 'done' in stat:
                    return 'done'

            # fallback to trade.isDone() if present
            is_done = False
            if hasattr(trade, 'isDone'):
                try:
                    is_done = bool(trade.isDone())
                except Exception:
                    is_done = False
            if is_done:
                return 'done'
            return 'pending'
        except Exception:
            return 'unknown'


