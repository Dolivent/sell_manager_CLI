"""Indicator functions: SMA and EMA.

Simple, well-tested implementations for use in the CLI tool.
"""
from typing import List, Optional


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


