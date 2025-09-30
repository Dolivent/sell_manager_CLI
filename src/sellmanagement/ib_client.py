from ib_insync import IB
from typing import List


class IBClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 4001, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()

    def connect(self) -> bool:
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=10)
            return self.ib.isConnected()
        except Exception:
            return False

    def get_positions(self) -> List:
        return self.ib.positions()

    def get_open_orders(self):
        return self.ib.openOrders()

    def disconnect(self):
        try:
            self.ib.disconnect()
        except Exception:
            pass

    def get_latest_positions_normalized(self) -> List[dict]:
        """Return a list of normalized position dicts from the IB client snapshot.

        Each dict contains keys: `exchange`, `symbol`, `token`, `quantity`, `avg_cost`, `raw`.
        This is a best-effort normalizer that tolerates different position object shapes.
        """
        out: List[dict] = []
        try:
            positions = list(self.get_positions() or [])
        except Exception:
            positions = []

        for pv in positions:
            try:
                contract = getattr(pv, 'contract', None) or getattr(pv, 'Contract', None)
                qty = None
                avg = 0.0
                if contract is None and isinstance(pv, (list, tuple)) and len(pv) >= 2:
                    contract = pv[0]
                    qty = pv[1]
                if qty is None:
                    qty = getattr(pv, 'position', None) or getattr(pv, 'Position', None) or 0
                try:
                    avg = getattr(pv, 'avgCost', None) or getattr(pv, 'AvgCost', None) or getattr(pv, 'averageCost', None) or 0.0
                except Exception:
                    avg = 0.0
                symbol = None
                exchange = None
                if contract is not None:
                    symbol = getattr(contract, 'symbol', None) or getattr(contract, 'Symbol', None)
                    exchange = getattr(contract, 'exchange', None) or getattr(contract, 'Exchange', None) or 'SMART'
                else:
                    symbol = getattr(pv, 'symbol', None) or getattr(pv, 'Symbol', None)
                    exchange = getattr(pv, 'exchange', None) or getattr(pv, 'Exchange', None) or 'SMART'

                token = f"{exchange}:{symbol}" if symbol else "<unknown>"
                out.append({'exchange': exchange, 'symbol': symbol, 'token': token, 'quantity': qty or 0, 'avg_cost': avg or 0.0, 'raw': pv})
            except Exception:
                # best-effort fallback
                try:
                    out.append({'exchange': 'UNKNOWN', 'symbol': None, 'token': '<unknown>', 'quantity': 0, 'avg_cost': 0.0, 'raw': pv})
                except Exception:
                    pass
        return out

    def _parse_token(self, token: str):
        # token format: EXCHANGE:SYMBOL or SYMBOL
        if not token:
            return ('SMART', '')
        if ':' in token:
            ex, sym = token.split(':', 1)
            return (ex.strip().upper() or 'SMART', sym.strip().upper())
        return ('SMART', token.strip().upper())

    def download_daily(self, token: str, duration: str = "365 D"):
        """Blocking download of daily bars for `token` using ib_insync.

        Returns list of dict rows or empty list on failure.
        """
        try:
            from ib_insync import Stock  # type: ignore
        except Exception as e:
            try:
                from .trace import append_trace
                append_trace({"event": "download_daily_import_error", "token": token, "error": str(e)})
            except Exception:
                pass
            return []

        ex, sym = self._parse_token(token)
        if not sym:
            return []
        try:
            contract = Stock(sym, ex, 'USD')
            # Perform a synchronous historical data request on this thread
            try:
                # ib_insync's reqHistoricalData is async-backed; call the Async variant and wait via IB.run
                bars = self.ib.run(self.ib.reqHistoricalDataAsync(contract, endDateTime='', durationStr=duration, barSizeSetting='1 day', whatToShow='TRADES', useRTH=True))
            except Exception:
                bars = []

            out = []
            for b in bars:
                out.append({'Date': getattr(b, 'date', None), 'Open': getattr(b, 'open', None), 'High': getattr(b, 'high', None), 'Low': getattr(b, 'low', None), 'Close': getattr(b, 'close', None), 'Volume': getattr(b, 'volume', None)})
            try:
                from .trace import append_trace
                # prepare a small sample to avoid logging huge payloads
                sample = []
                for r in out[:3]:
                    try:
                        sample.append({"Date": r.get('Date'), "Close": r.get('Close')})
                    except Exception:
                        sample.append(None)
                first_date = out[0].get('Date') if out else None
                last_date = out[-1].get('Date') if out else None
                append_trace({"event": "download_daily_ok", "token": token, "rows": len(out), "first_date": first_date, "last_date": last_date, "sample": sample})
            except Exception:
                pass
            return out
        except Exception as e_all:
            try:
                from .trace import append_trace
                append_trace({"event": "download_daily_exception", "token": token, "error": str(e_all)})
            except Exception:
                pass
            return []

    # Half-hour downloads removed in simplified mode
    def download_halfhours(self, token: str, duration: str = "31 D", max_bars: int | None = 31, endDateTime: str = ""):
        """Blocking download of 30-minute bars for `token`.

        Returns list of dict rows (newest last) or empty list on failure.
        """
        try:
            from ib_insync import Stock  # type: ignore
        except Exception:
            try:
                from .trace import append_trace
                append_trace({"event": "download_halfhours_import_error", "token": token})
            except Exception:
                pass
            return []

        ex, sym = self._parse_token(token)
        if not sym:
            return []
        try:
            contract = Stock(sym, ex, 'USD')
            try:
                bars = self.ib.run(self.ib.reqHistoricalDataAsync(contract, endDateTime=endDateTime or '', durationStr=duration, barSizeSetting='30 mins', whatToShow='TRADES', useRTH=True))
            except Exception:
                bars = []

            out = []
            for b in bars:
                out.append({'Date': getattr(b, 'date', None), 'Open': getattr(b, 'open', None), 'High': getattr(b, 'high', None), 'Low': getattr(b, 'low', None), 'Close': getattr(b, 'close', None), 'Volume': getattr(b, 'volume', None)})
            if max_bars is not None and len(out) > max_bars:
                out = out[-max_bars:]
            try:
                from .trace import append_trace
                first_date = out[0].get('Date') if out else None
                last_date = out[-1].get('Date') if out else None
                append_trace({"event": "download_halfhours_ok", "token": token, "rows": len(out), "first_date": first_date, "last_date": last_date})
            except Exception:
                pass
            return out
        except Exception as e_all:
            try:
                from .trace import append_trace
                append_trace({"event": "download_halfhours_exception", "token": token, "error": str(e_all)})
            except Exception:
                pass
            return []


