"""Read-only Flask UI: latest minute snapshot + recent signal batch."""
from __future__ import annotations

import json
import logging
import os
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask

from .cli_loop import read_last_signal_batch

logger = logging.getLogger(__name__)


def _default_snapshot_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "minute_snapshot.jsonl"


def _default_signals_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "signals.jsonl"


def read_latest_snapshot_record(snapshot_path: Path) -> Optional[Dict[str, Any]]:
    """Return the last JSON object from an NDJSON snapshot file, or None."""
    if not snapshot_path.exists():
        return None
    last: Optional[Dict[str, Any]] = None
    with snapshot_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                last = json.loads(line)
            except Exception:
                continue
    return last


def dashboard_port() -> int:
    raw = os.environ.get("SELLMANAGEMENT_DASHBOARD_PORT", "5055")
    try:
        p = int(str(raw).strip(), 10)
        if 1 <= p <= 65535:
            return p
    except Exception:
        pass
    logger.warning("Invalid SELLMANAGEMENT_DASHBOARD_PORT %r, using 5055", raw)
    return 5055


def create_app(
    *,
    snapshot_path: Optional[Path] = None,
    signals_path: Optional[Path] = None,
) -> Flask:
    app = Flask(__name__)
    app.config["SNAPSHOT_PATH"] = snapshot_path or _default_snapshot_path()
    app.config["SIGNALS_PATH"] = signals_path or _default_signals_path()

    @app.route("/")
    def index() -> str:
        snap_path: Path = app.config["SNAPSHOT_PATH"]
        sig_path: Path = app.config["SIGNALS_PATH"]
        record = read_latest_snapshot_record(snap_path)
        rows = (record or {}).get("rows") or []
        ts = (record or {}).get("ts") or "—"
        signals = read_last_signal_batch(sig_path)

        row_cells: List[List[str]] = []
        for r in rows[:500]:
            if not isinstance(r, dict):
                continue
            row_cells.append(
                [
                    str(r.get("ticker", "")),
                    str(r.get("last_close", "")),
                    str(r.get("ma_value", "")),
                    str(r.get("distance_pct", "")),
                    str(r.get("assigned_ma", "")),
                ]
            )

        def _table(headers: List[str], cells: List[List[str]]) -> str:
            th = "".join(f"<th>{escape(h)}</th>" for h in headers)
            body = ""
            for row in cells:
                body += "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>"
            return f"<table class='grid'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"

        sig_rows: List[List[str]] = []
        for s in signals[:200]:
            if not isinstance(s, dict):
                continue
            sig_rows.append(
                [
                    str(s.get("ts", "")),
                    str(s.get("ticker", "")),
                    str(s.get("decision", "")),
                    str(s.get("close", "")),
                    str(s.get("ma_value", "")),
                ]
            )

        page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>sellmanagement dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; background: #111; color: #e8e8e8; }}
    h1 {{ font-size: 1.25rem; }}
    h2 {{ font-size: 1rem; margin-top: 1.5rem; }}
    .meta {{ color: #9ab; font-size: 0.9rem; }}
    table.grid {{ border-collapse: collapse; width: 100%; max-width: 72rem; font-size: 0.85rem; }}
    table.grid th, table.grid td {{ border: 1px solid #333; padding: 0.35rem 0.5rem; text-align: left; }}
    table.grid th {{ background: #1e1e1e; }}
    tr:nth-child(even) {{ background: #181818; }}
  </style>
</head>
<body>
  <h1>sellmanagement</h1>
  <p class="meta">Latest snapshot ts: <strong>{escape(str(ts))}</strong></p>
  <h2>Snapshot rows</h2>
  {_table(["ticker", "last_close", "ma_value", "distance_pct", "assigned_ma"], row_cells)}
  <h2>Latest signal batch</h2>
  {_table(["ts", "ticker", "decision", "close", "ma_value"], sig_rows)}
</body>
</html>"""
        return page

    return app


def run_dashboard(*, host: str = "127.0.0.1") -> None:
    port = dashboard_port()
    app = create_app()
    logger.info("Dashboard listening on http://%s:%s", host, port)
    app.run(host=host, port=port, debug=False, use_reloader=False)
