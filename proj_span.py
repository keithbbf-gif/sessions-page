"""Earliest and latest session dates for the projects view.

Stdlib only. Does not bind a port or open a window.
"""

from __future__ import annotations

import math
from datetime import datetime

# Same cutoff as sheets._stamp_dt and desk._hit_date: above this, the stamp is ms.
_MS_CUTOFF = 100_000_000_000
_EMPTY = ("\u2014", "\u2014")


def _when(stamp):
    if isinstance(stamp, bool):
        return None
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n) or n <= 0:
        return None
    seconds = n / 1000.0 if n > _MS_CUTOFF else n
    try:
        return datetime.fromtimestamp(seconds)
    except (OSError, OverflowError, ValueError):
        return None


def span(hits) -> tuple[str, str]:
    """ISO start and end dates from the min and max updated stamps in hits."""
    if not hits:
        return _EMPTY
    try:
        rows = iter(hits)
    except TypeError:
        return _EMPTY
    found = []
    for hit in rows:
        if not isinstance(hit, dict):
            continue
        when = _when(hit.get("updated"))
        if when is not None:
            found.append(when)
    if not found:
        return _EMPTY
    return (min(found).date().isoformat(), max(found).date().isoformat())


def build(parent, desk) -> None:
    """Empty frame. The dates are computed by span(), not painted here."""
    tk = getattr(desk, "tk", None)
    if tk is None or parent is None:
        return
    tk.Frame(parent, bg="#07080A")


def refresh(desk, hits) -> None:
    """No-op."""
    return None
