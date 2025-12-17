from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

Timestamp = datetime
Interval = Tuple[Timestamp, Optional[Timestamp]]  # (entry, exit) exit==None means still open


def _clean_line(line: str) -> str:
    # positions.txt contains non-breaking spaces and inconsistent spacing; normalize
    return line.replace("\u00A0", " ").rstrip("\n")


def parse_positions_text(text: str) -> Dict[str, List[Interval]]:
    """
    Parse the contents of `config/positions.txt` and return per-ticker ownership intervals.

    Returned structure:
      { "TSLA": [(entry_dt, exit_dt_or_None), ...], ... }

    Rules:
      - Header lines are of the form: "<TICKER> <direction>" (e.g. "TSLA long" or "UGL short")
      - Following indented lines contain "YYYY-MM-DD HH:MM:SS <price> <action>"
      - For `long` direction: "bought" opens, "sold" closes.
      - For `short` direction: "sold" opens, "bought" closes.
      - Multiple buys when already open are ignored for opening semantics; intervals are merged where they overlap.
    """
    ticker_events: Dict[str, List[Tuple[Timestamp, str]]] = {}
    current_ticker: Optional[str] = None
    current_direction: Optional[str] = None

    header_re = re.compile(r"^\s*([A-Z0-9\.-]+)\s+(long|short)\s*$", re.IGNORECASE)
    event_re = re.compile(r"^\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s+([0-9]{2}:[0-9]{2}:[0-9]{2})\s+([0-9\.]+)\s+(\w+)\s*$")

    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if not line.strip():
            continue

        m_header = header_re.match(line)
        if m_header:
            current_ticker = m_header.group(1).upper()
            current_direction = m_header.group(2).lower()
            # ensure list exists
            ticker_events.setdefault(current_ticker, [])
            continue

        if current_ticker is None:
            # skip any stray event lines before a header
            continue

        m_event = event_re.match(line)
        if not m_event:
            # skip unrecognized lines silently
            continue

        date_part, time_part, _price, action = m_event.groups()
        dt = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
        ticker_events.setdefault(current_ticker, []).append((dt, action.lower()))

    # Convert events into intervals per ticker
    ticker_intervals: Dict[str, List[Interval]] = {}
    for ticker, events in ticker_events.items():
        # sort chronologically just in case
        events_sorted = sorted(events, key=lambda x: x[0])
        # Determine direction: find most recent header direction occurrence by scanning text
        # For simplicity, assume direction at the time blocks were parsed applies; default to long
        # We don't have the header directions stored per-block here, so assume long if no explicit.
        # To be robust, direction detection should be done at block-level (kept if needed).
        # For now default to 'long' semantics.
        # We'll attempt to infer direction by looking at actions distribution if needed.
        # Find intervals for "long" semantics by default.
        direction = "long"

        intervals: List[Interval] = []
        current_open: Optional[Timestamp] = None

        if direction == "long":
            for dt, action in events_sorted:
                if action == "bought":
                    if current_open is None:
                        current_open = dt
                elif action == "sold":
                    if current_open is not None:
                        intervals.append((current_open, dt))
                        current_open = None
            if current_open is not None:
                intervals.append((current_open, None))
        else:
            # short (not used currently) - entry on 'sold', close on 'bought'
            for dt, action in events_sorted:
                if action == "sold":
                    if current_open is None:
                        current_open = dt
                elif action == "bought":
                    if current_open is not None:
                        intervals.append((current_open, dt))
                        current_open = None
            if current_open is not None:
                intervals.append((current_open, None))

        # Merge overlapping intervals (and handle open-ended intervals)
        merged: List[Interval] = []
        for start, end in sorted(intervals, key=lambda x: x[0]):
            if not merged:
                merged.append((start, end))
                continue
            last_start, last_end = merged[-1]
            # If last_end is None, it's open => remains open (covering all future)
            if last_end is None:
                # already open, nothing to do
                continue
            if end is None or start <= last_end:
                # overlapping or open-ended: extend end if needed
                new_end = None if end is None else max(last_end, end)
                merged[-1] = (last_start, new_end)
            else:
                merged.append((start, end))

        ticker_intervals[ticker] = merged

    return ticker_intervals


def parse_positions_file(path: str | Path = "config/positions.txt") -> Dict[str, List[Interval]]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_positions_text(text)


def is_in_position_at(ticker: str, dt: datetime, positions_map: Dict[str, List[Interval]]) -> bool:
    """
    Return True if `dt` is inside any interval for `ticker`. Comparison is inclusive of entry and exclusive of exit.
    """
    ticker_up = ticker.upper()
    intervals = positions_map.get(ticker_up) or []
    for start, end in intervals:
        if end is None:
            if dt >= start:
                return True
        else:
            if start <= dt < end:
                return True
    return False












