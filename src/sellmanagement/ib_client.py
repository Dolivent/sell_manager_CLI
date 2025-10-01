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
        bars = self._ib.reqHistoricalData(
            contract,
            endDateTime=end or '',
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


