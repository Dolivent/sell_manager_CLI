"""Indicator functions: SMA and EMA.

Simple, well-tested implementations for use in the CLI tool.
"""
from typing import List, Optional, Dict, Any
import json
from pathlib import Path


def simple_moving_average(values: List[float], length: int) -> Optional[float]:
    if length <= 0:
        raise ValueError("length must be > 0")
    if not values or len(values) < length:
        return None
    window = values[-length:]
    return float(sum(window)) / float(length)


def exponential_moving_average(values: List[float], length: int) -> Optional[float]:
    if length <= 0:
        raise ValueError("length must be > 0")
    if not values or len(values) < length:
        return None
    alpha = 2.0 / (length + 1)
    # start EMA with the simple average of the first `length` values
    ema = float(sum(values[-length:]) / float(length))
    # apply EMA across the tail values after the seed point
    tail = values[-length + 1:]
    for v in tail:
        ema = (float(v) * alpha) + (ema * (1.0 - alpha))
    return ema


def series_sma(values: List[float], length: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for i in range(len(values)):
        if i + 1 < length:
            out.append(None)
        else:
            out.append(simple_moving_average(values[: i + 1], length))
    return out


def series_ema(values: List[float], length: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    if not values:
        return out
    ema = None
    alpha = 2.0 / (length + 1)
    for i, v in enumerate(values):
        if i + 1 < length:
            out.append(None)
            continue
        if ema is None:
            ema = float(sum(values[i - length + 1 : i + 1]) / float(length))
            out.append(ema)
        else:
            ema = (float(v) * alpha) + (ema * (1.0 - alpha))
            out.append(ema)
    return out


def compute_sma_series_all(values: List[float], lengths: List[int]) -> Dict[int, List[Optional[float]]]:
    """Compute SMA series for multiple lengths.

    Returns a mapping length -> series (same length as input values).
    """
    result: Dict[int, List[Optional[float]]] = {}
    for l in lengths:
        if l <= 0:
            raise ValueError("SMA length must be > 0")
        result[l] = series_sma(values, l)
    return result


def compute_ema_series_all(values: List[float], lengths: List[int]) -> Dict[int, List[Optional[float]]]:
    """Compute EMA series for multiple lengths.

    Returns a mapping length -> series (same length as input values).
    """
    result: Dict[int, List[Optional[float]]] = {}
    for l in lengths:
        if l <= 0:
            raise ValueError("EMA length must be > 0")
        result[l] = series_ema(values, l)
    return result


def enrich_ndjson_with_indicators(
    input_path: str,
    output_path: Optional[str] = None,
    sma_lengths: List[int] = (5, 10, 20, 50, 100, 150, 200),
    ema_lengths: List[int] = (5, 10, 20, 50, 100, 150, 200),
    overwrite: bool = False,
) -> str:
    """Read an NDJSON file of OHLCV daily bars, compute SMA/EMA series and write an enriched NDJSON.

    Each output record will include new keys like `SMA_50` and `EMA_50` with numeric values or null.
    The function preserves the input order of records when computing series.

    Returns the path to the written NDJSON file.
    """
    inp = Path(input_path)
    if not inp.exists():
        raise FileNotFoundError(f"input file not found: {input_path}")
    if output_path is None:
        if overwrite:
            outp = inp
        else:
            outp = inp.with_suffix(inp.suffix + ".enriched")
    else:
        outp = Path(output_path)

    records: List[Dict[str, Any]] = []
    closes: List[float] = []
    with inp.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            records.append(obj)
            # tolerate missing or null Close values
            c = obj.get("Close")
            closes.append(None if c is None else float(c))

    # Replace None with previous close or 0.0 for calculation safety
    clean_closes: List[float] = []
    last_val = 0.0
    for c in closes:
        if c is None:
            clean_closes.append(last_val)
        else:
            clean_closes.append(c)
            last_val = c

    sma_map = compute_sma_series_all(clean_closes, list(sma_lengths))
    ema_map = compute_ema_series_all(clean_closes, list(ema_lengths))

    # enrich records
    for i, rec in enumerate(records):
        for l, series in sma_map.items():
            rec[f"SMA_{l}"] = None if series[i] is None else float(series[i])
        for l, series in ema_map.items():
            rec[f"EMA_{l}"] = None if series[i] is None else float(series[i])

    # write output
    with outp.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return str(outp)


