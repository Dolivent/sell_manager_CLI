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













