"""Day-of-month counts for the calendar.

The month module draws the cells. This module only counts hits.
Stdlib only. build() shows nothing.
"""

from __future__ import annotations

from datetime import datetime, date

_MS = 10**11


def _when(stamp) -> datetime | None:
    """Local datetime for a hit stamp. Missing or unusable values are None."""
    if stamp is None or isinstance(stamp, bool):
        return None
    if isinstance(stamp, datetime):
        if stamp.tzinfo is not None:
            return stamp.astimezone().replace(tzinfo=None)
        return stamp
    if isinstance(stamp, date):
        return datetime(stamp.year, stamp.month, stamp.day)
    if isinstance(stamp, bytes):
        stamp = stamp.decode("utf-8", errors="replace")
    if isinstance(stamp, str):
        text = stamp.strip()
        if not text:
            return None
        parsed = _from_iso(text)
        if parsed is not None:
            return parsed
        try:
            stamp = float(text)
        except ValueError:
            return None
    if isinstance(stamp, (int, float)):
        number = float(stamp)
        if number <= 0:
            return None
        if number > _MS:
            number = number / 1000.0
        try:
            return datetime.fromtimestamp(number)
        except (OSError, OverflowError, ValueError):
            return None
    return None


def _from_iso(text: str) -> datetime | None:
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dot = text.find(".")
    if dot != -1:
        frac = []
        index = dot + 1
        while index < len(text) and text[index].isdigit() and len(frac) < 6:
            frac.append(text[index])
            index += 1
        while index < len(text) and text[index].isdigit():
            index += 1
        text = text[:dot] + "." + "".join(frac) + text[index:]
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _field(hit: dict, key: str) -> str:
    value = hit.get(key)
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def day_counts(hits, year, month, term="") -> dict[int, int]:
    """Map day-of-month to how many hits fall on that day.

    term is a case-insensitive substring of title or cwd. An empty term
    keeps every hit. Hits with no usable timestamp are skipped. Days
    outside year and month are omitted, and days with no hits are omitted.
    """
    try:
        year_n = int(year)
        month_n = int(month)
    except (TypeError, ValueError):
        return {}
    if month_n < 1 or month_n > 12:
        return {}
    needle = "" if term is None else str(term).strip().lower()
    counts: dict[int, int] = {}
    try:
        rows = [] if hits is None else hits
        iterator = iter(rows)
    except TypeError:
        return {}
    for hit in iterator:
        if not isinstance(hit, dict):
            continue
        if needle:
            title = _field(hit, "title").lower()
            cwd = _field(hit, "cwd").lower()
            if needle not in title and needle not in cwd:
                continue
        when = _when(hit.get("updated"))
        if when is None or when.year != year_n or when.month != month_n:
            continue
        counts[when.day] = counts.get(when.day, 0) + 1
    return counts


def build(parent, desk) -> None:
    """Show nothing. The month module draws the cells."""
    return None


def refresh(desk, hits) -> None:
    """No-op. Counts come from day_counts."""
    return None
