"""Broker backends (market data + order execution)."""

from __future__ import annotations

from typing import Any

from .ibkr import IBKRBroker

__all__ = ["IBKRBroker", "create_broker"]


def create_broker(name: str = "ibkr", **kwargs: Any) -> IBKRBroker:
    """Factory for named broker adapters. Currently only ``ibkr`` is implemented."""
    key = (name or "ibkr").strip().lower()
    if key == "ibkr":
        return IBKRBroker(**kwargs)
    raise ValueError(f"Unknown broker: {name!r}")
