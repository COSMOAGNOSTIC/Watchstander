"""
Closed-interval coverage, shared by certificate and contractor-window checks.

One definition of "does this set of windows cover the whole work window"
so certificates.py and crews.py can never disagree on boundary handling.
Windows are closed intervals; two windows that touch (one ends at the
instant the next begins) count as continuous coverage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable


def uncovered(
    start: datetime, end: datetime, windows: Iterable[tuple[datetime, datetime]]
) -> list[tuple[datetime, datetime]]:
    """Gaps in [start, end] not covered by any (from, until) window, in order."""
    touching = sorted(
        (max(f, start), min(u, end)) for f, u in windows if u >= start and f <= end
    )
    if not touching:
        return [(start, end)]
    gaps, cursor = [], start
    for s, e in touching:
        if s > cursor:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < end:
        gaps.append((cursor, end))
    return gaps
