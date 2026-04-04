"""Ticker normalisation utilities.

All modules that handle ticker symbols should use `normalise_ticker` to
produce a canonical form before comparison or storage. This ensures consistent
matching between:
- IB API token format (e.g. "NASDAQ:AAPL")
- CSV assignment format (e.g. "NASDAQ:AAPL" or "AAPL")
- GUI display format

Canonical form:
- Uppercase
- No surrounding whitespace
- If an exchange prefix is present, "EXCHANGE:SYMBOL"
- If no exchange, just the bare symbol
"""

from typing import Optional


def normalise_ticker(ticker: str) -> str:
    """Return the canonical normalised form of a ticker string.

    Examples:
        "NASDAQ:AAPL" -> "NASDAQ:AAPL"
        "aapl"        -> "AAPL"
        "NASDAQ:aapl" -> "NASDAQ:AAPL"
        ""            -> ""
        None          -> ""
    """
    if not ticker:
        return ""
    return ticker.strip().upper()


def ticker_to_symbol(ticker: str) -> str:
    """Extract the bare symbol part from a ticker token.

    Strips any exchange prefix (e.g. "NASDAQ:" or "SMART:") and returns
    the symbol portion in normalised (uppercase) form.

    Examples:
        "NASDAQ:AAPL" -> "AAPL"
        "AAPL"        -> "AAPL"
        "SMART:TSLA"  -> "TSLA"
    """
    if not ticker:
        return ""
    t = ticker.strip().upper()
    if ":" in t:
        return t.split(":")[-1]
    return t


def tickers_match(a: str, b: str) -> bool:
    """Return True if two ticker strings refer to the same instrument.

    Matches on:
    1. Exact normalised equality
    2. Equal bare symbol when one has an exchange prefix and the other doesn't

    Examples:
        tickers_match("NASDAQ:AAPL", "AAPL")       -> True
        tickers_match("AAPL", "NASDAQ:AAPL")       -> True
        tickers_match("NASDAQ:AAPL", "SMART:AAPL") -> False
        tickers_match("AAPL", "TSLA")             -> False
    """
    if not a or not b:
        return False

    na = normalise_ticker(a)
    nb = normalise_ticker(b)

    if na == nb:
        return True

    # bare symbol match (one has exchange, one doesn't)
    sa = ticker_to_symbol(na)
    sb = ticker_to_symbol(nb)
    if sa and sa == sb:
        return True

    return False
