"""Scoring math: rates, the balanced score, Wilson intervals, and latency
percentiles. Kept separate from the runner so the math can be tested on
its own, with plain numbers instead of real guard runs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

Z_95 = 1.96


@dataclass
class WilsonInterval:
    low: float
    high: float


def wilson_interval(successes: int, total: int, z: float = Z_95) -> Optional[WilsonInterval]:
    """95 percent Wilson score interval for a proportion.

    Returns None when total is 0, since a rate is not defined there.
    """
    if total == 0:
        return None

    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = p + z2 / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total)

    low = (center - margin) / denom
    high = (center + margin) / denom
    return WilsonInterval(low=max(0.0, low), high=min(1.0, high))


def rate(successes: int, total: int) -> Optional[float]:
    """A simple proportion, or None when total is 0."""
    if total == 0:
        return None
    return successes / total


def balanced_score(catch_rate: Optional[float], wrongly_held_rate: Optional[float]) -> Optional[float]:
    """(catch rate + (1 minus wrongly held rate)) divided by 2.

    Returns None if either input rate is undefined, since the score
    cannot be computed without both halves.
    """
    if catch_rate is None or wrongly_held_rate is None:
        return None
    return (catch_rate + (1 - wrongly_held_rate)) / 2


def percentile(values: list[float], pct: float) -> Optional[float]:
    """Nearest-rank percentile. pct is between 0 and 100.

    Returns None for an empty list.
    """
    if not values:
        return None

    ordered = sorted(values)
    rank = math.ceil((pct / 100) * len(ordered))
    rank = max(1, min(len(ordered), rank))
    return ordered[rank - 1]


def median_latency(values: list[float]) -> Optional[float]:
    return percentile(values, 50)


def p95_latency(values: list[float]) -> Optional[float]:
    return percentile(values, 95)
