"""Central logging setup for CLI and GUI entry points."""
from __future__ import annotations

import logging
import sys
_LOG = logging.getLogger("sellmanagement")
_CONFIGURED: bool = False


def setup_logging(console_level: int = logging.WARNING) -> None:
    """Attach a stderr :class:`~logging.StreamHandler` to the ``sellmanagement`` logger.

    Idempotent. Child loggers (e.g. ``sellmanagement.downloader``) propagate here.
    The trace file logger remains separate (``propagate=False``) so JSONL is not echoed.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True
    _LOG.setLevel(logging.DEBUG)
    h = logging.StreamHandler(sys.stderr)
    h.setLevel(console_level)
    h.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    _LOG.addHandler(h)
