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

from agent_core.validation import instant, require_comparable


def uncovered(
    start: datetime, end: datetime, windows: Iterable[tuple[datetime, datetime]]
) -> list[tuple[datetime, datetime]]:
    """
    Gaps in [start, end] not covered by any (from, until) window, in order.
    Compares real time (aware datetimes in UTC, review-01 R03), so returned
    gap bounds for aware input are UTC. Mixed naive/aware raises ValueError.
    """
    windows = list(windows)
    require_comparable([("work window start", start), ("work window end", end)]
                       + [(f"window {i} from", f) for i, (f, _) in enumerate(windows)]
                       + [(f"window {i} until", u) for i, (_, u) in enumerate(windows)])
    start, end = instant(start), instant(end)
    windows = [(instant(f), instant(u)) for f, u in windows]
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
