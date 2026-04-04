"""Optional SMTP alerts for SellSignal and failed live orders (stdlib only)."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_warned_incomplete_smtp = False

_FAILURE_ORDER_STATUSES = frozenset(
    {
        "failed_prepare",
        "failed_transmit",
        "timeout",
        "error",
        "cancelled",
    }
)


def _smtp_env_tuple() -> Tuple[
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
]:
    host = os.environ.get("SELLMANAGEMENT_SMTP_HOST")
    port = os.environ.get("SELLMANAGEMENT_SMTP_PORT")
    user = os.environ.get("SELLMANAGEMENT_SMTP_USER")
    password = os.environ.get("SELLMANAGEMENT_SMTP_PASS")
    to_addr = os.environ.get("SELLMANAGEMENT_ALERT_TO")
    return host, port, user, password, to_addr


def _missing_smtp_vars(
    host: Optional[str],
    port: Optional[str],
    user: Optional[str],
    to_addr: Optional[str],
) -> List[str]:
    missing: List[str] = []
    if not (host or "").strip():
        missing.append("SELLMANAGEMENT_SMTP_HOST")
    if not (to_addr or "").strip():
        missing.append("SELLMANAGEMENT_ALERT_TO")
    user_set = bool((user or "").strip())
    pass_in_env = "SELLMANAGEMENT_SMTP_PASS" in os.environ
    if user_set and not pass_in_env:
        missing.append("SELLMANAGEMENT_SMTP_PASS")
    if pass_in_env and not user_set:
        missing.append("SELLMANAGEMENT_SMTP_USER")
    return missing


def _parse_port(port_raw: Optional[str]) -> int:
    if not (port_raw or "").strip():
        return 587
    try:
        p = int(str(port_raw).strip(), 10)
        if 1 <= p <= 65535:
            return p
    except Exception:
        pass
    return 587


def _log_incomplete_once(missing: List[str]) -> None:
    global _warned_incomplete_smtp
    if _warned_incomplete_smtp:
        return
    _warned_incomplete_smtp = True
    logger.warning(
        "SMTP alerts disabled: set %s (and other SELLMANAGEMENT_SMTP_* / SELLMANAGEMENT_ALERT_TO)",
        ", ".join(missing),
    )


def send_smtp_alert(subject: str, body: str) -> bool:
    """Send a plain-text email if SMTP env is complete; otherwise warn once and return False."""
    host, port_raw, user, password, to_addr = _smtp_env_tuple()
    missing = _missing_smtp_vars(host, port_raw, user, to_addr)
    if missing:
        _log_incomplete_once(missing)
        return False

    host = (host or "").strip()
    to_addr = (to_addr or "").strip()
    port = _parse_port(port_raw)
    user_s = (user or "").strip()
    pass_s = "" if password is None else str(password)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user_s or "sellmanagement-alerts@local"
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
                if user_s:
                    smtp.login(user_s, pass_s)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.ehlo()
                try:
                    smtp.starttls()
                    smtp.ehlo()
                except smtplib.SMTPException:
                    pass
                if user_s:
                    smtp.login(user_s, pass_s)
                smtp.send_message(msg)
    except Exception:
        logger.exception("SMTP alert send failed (subject=%r)", subject)
        return False
    logger.info("SMTP alert sent: %s", subject)
    return True


def alert_sellsignal_logged(entry: Dict[str, Any]) -> None:
    """Notify when a SellSignal row was persisted (best-effort)."""
    ticker = entry.get("ticker") or entry.get("symbol") or "?"
    ts = entry.get("ts") or ""
    subject = f"[sellmanagement] SellSignal {ticker}"
    lines = [
        f"ticker: {ticker}",
        f"ts: {ts}",
        f"close: {entry.get('close')}",
        f"ma_value: {entry.get('ma_value')}",
        f"action: {entry.get('action')}",
        f"position: {entry.get('position')}",
    ]
    send_smtp_alert(subject, "\n".join(lines))


def order_transmit_needs_alert(res: Dict[str, Any]) -> bool:
    """True when live transmit outcome should trigger a failure alert."""
    if not isinstance(res, dict):
        return True
    s = str(res.get("status", "")).lower()
    return s in _FAILURE_ORDER_STATUSES


def alert_order_failed(*, ticker: Optional[str], result: Dict[str, Any]) -> None:
    subject = f"[sellmanagement] Order failed {ticker or '?'}"
    body = f"ticker: {ticker}\nstatus: {result.get('status')}\nresult: {result!r}"
    send_smtp_alert(subject, body)


def alert_order_exception(*, ticker: Optional[str], error: str) -> None:
    subject = f"[sellmanagement] Order exception {ticker or '?'}"
    body = f"ticker: {ticker}\nerror: {error}"
    send_smtp_alert(subject, body)
