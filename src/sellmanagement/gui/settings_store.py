from qtpy.QtCore import QSettings

ORG = "sellmanagement"
APP = "gui"


def _settings():
    return QSettings(ORG, APP)


def get_bool(key: str, default: bool = False) -> bool:
    s = _settings()
    v = s.value(key, default)
    try:
        return bool(v) if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes")
    except Exception:
        return default


def set_value(key: str, value) -> None:
    s = _settings()
    s.setValue(key, value)


def get_value(key: str, default=None):
    s = _settings()
    return s.value(key, default)


# ---------------------------------------------------------------------------
# use_rth — global flag for IB historical data requests
# When True, only include Regular Trading Hours data (09:30–16:00 ET).
# When False, include extended-hours data as well.
# ---------------------------------------------------------------------------
USE_RTH_KEY = "ib/use_rth"


def get_use_rth() -> bool:
    """Return the stored use_rth flag. Defaults to True (RTH only)."""
    return get_bool(USE_RTH_KEY, default=True)


def set_use_rth(value: bool) -> None:
    """Persist the use_rth flag."""
    set_value(USE_RTH_KEY, bool(value))


# ---------------------------------------------------------------------------
# client_id — IB API session id (one active connection per id)
# ---------------------------------------------------------------------------
CLIENT_ID_KEY = "ib/client_id"


def get_client_id() -> int:
    """Return stored client id; default 1; clamp to 1..999999."""
    raw = get_value(CLIENT_ID_KEY, 1)
    try:
        i = int(raw)
        if 1 <= i <= 999_999:
            return i
    except Exception:
        pass
    return 1


def set_client_id(value: int) -> None:
    """Persist client id."""
    try:
        i = int(value)
    except Exception:
        i = 1
    i = max(1, min(999_999, i))
    set_value(CLIENT_ID_KEY, i)





















