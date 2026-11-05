"""
Shared input validation: non-blank identifiers and a single time contract.

review-01 R05/R11: blank or whitespace IDs passed validation and then
matched each other (an empty package ID joined an empty certificate ID).
`NonBlankStr` strips and rejects them at construction.

review-01 R03/R13: Python compares two aware datetimes that share a
tzinfo object by wall-clock time, ignoring `fold`, so a permit that
expired in the first repeated hour of a daylight-saving fall-back passed
coverage for a job in the second. And mixing naive and aware datetimes
raised a bare TypeError with no assessment. The contract here:

- every comparison goes through `instant()`, which turns an aware
  datetime into UTC (real elapsed time) and leaves a naive one alone;
- a set of times that mixes naive and aware is refused with a ValueError
  naming the fields, never silently compared.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Iterable, Optional

from pydantic import AfterValidator


def _non_blank(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be blank")
    return v


NonBlankStr = Annotated[str, AfterValidator(_non_blank)]


def instant(t: datetime) -> datetime:
    """Aware -> UTC so comparisons use real time; naive -> unchanged."""
    return t.astimezone(timezone.utc) if t.tzinfo is not None else t


def require_comparable(named: Iterable[tuple[str, Optional[datetime]]]) -> None:
    """Raise ValueError if the non-None times mix naive and aware."""
    present = [(n, t) for n, t in named if t is not None]
    aware = [n for n, t in present if t.tzinfo is not None]
    naive = [n for n, t in present if t.tzinfo is None]
    if aware and naive:
        raise ValueError(
            "cannot compare timezone-naive and timezone-aware times: "
            f"naive={sorted(set(naive))}, aware={sorted(set(aware))}. "
            "Use one convention for every schedule, window, and due date."
        )


def fmt_time(t: datetime) -> str:
    """Minutes normally; seconds when non-zero, so a 20-second gap never reads '07:00 to 07:00'."""
    return t.strftime("%Y-%m-%d %H:%M:%S" if t.second or t.microsecond else "%Y-%m-%d %H:%M")
