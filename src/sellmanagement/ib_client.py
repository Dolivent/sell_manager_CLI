"""Backward-compatible import path for the Interactive Brokers adapter.

Implementation lives in :mod:`sellmanagement.brokers.ibkr`.
"""

from __future__ import annotations

from .brokers.ibkr import IBKRBroker as IBClient

__all__ = ["IBClient"]
