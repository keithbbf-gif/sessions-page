"""Right edge of the one ledger window. Not a separate page."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta

_BG = "#0C0E12"
_FG = "#A7B0C3"
_TITLE = "#E8ECF4"

_WEEK = timedelta(days=7)
_MONTH = timedelta(days=30)
_QUARTER = timedelta(days=92)


def build(parent, desk) -> None:
    """Fill parent with the glance panel. Stores the Text on desk.ledger_glance."""
    panel = tk.Frame(parent, bg=_BG)
    panel.pack(fill="both", expand=True)
    tk.Label(
        panel,
        text="At a glance",
        fg=_TITLE,
        bg=_BG,
        anchor="w",
        font=("Segoe UI", 12, "bold"),
    ).pack(fill="x", padx=12, pady=(12, 4))
    text = tk.Text(
        panel,
        bg=_BG,
        fg=_FG,
        relief="flat",
        wrap="word",
        font=("Segoe UI", 11),
        highlightthickness=0,
        borderwidth=0,
        insertbackground=_FG,
        padx=8,
        pady=4,
    )
    text.tag_configure("section", foreground=_TITLE, font=("Segoe UI", 11, "bold"))
    text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    text.configure(state="disabled")
    desk.ledger_glance = text
    refresh(desk, ())


def refresh(desk, hits) -> None:
    """Rewrite plain section lines from hit updated times. Opens no window."""
    widget = desk.ledger_glance
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    _insert(widget, _sections(hits))
    widget.configure(state="disabled")


def _insert(widget, blocks: list[tuple[str, list[str]]]) -> None:
    for index, (label, lines) in enumerate(blocks):
        if index:
            widget.insert("end", "\n\n")
        widget.insert("end", label, "section")
        widget.insert("end", "\n")
        if lines:
            widget.insert("end", "\n".join(lines))


def _sections(hits) -> list[tuple[str, list[str]]]:
    now = datetime.now()
    recent: list[tuple[datetime, dict]] = []
    month = 0
    quarter = 0
    for hit in hits or ():
        if not isinstance(hit, dict):
            continue
        when = _stamp(hit.get("updated"))
        if when is None:
            continue
        try:
            age = now - when
        except TypeError:
            continue
        if age <= _QUARTER:
            quarter += 1
        if age <= _MONTH:
            month += 1
        if age <= _WEEK:
            recent.append((when, hit))
    recent.sort(key=lambda item: item[0], reverse=True)
    titles = [f"{_age_text(when, now)}  {_title(hit)}" for when, hit in recent[:8]]
    count = len(recent)
    day_lines = [_count(count), *titles]
    return [
        ("7 days", day_lines),
        ("week", [_count(count)]),
        ("monthly", [_count(month)]),
        ("quarterly", [_count(quarter)]),
    ]


def _count(n: int) -> str:
    return "1 session" if n == 1 else f"{n} sessions"


def _title(hit: dict) -> str:
    if hit.get("legal"):
        return "Legal session"
    text = hit.get("title") or hit.get("vendor_id") or hit.get("id") or ""
    return str(text) if str(text).strip() else "Untitled"


def _stamp(stamp):
    if isinstance(stamp, datetime):
        return stamp
    if stamp is None or isinstance(stamp, bool):
        return None
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return None
    if n != n or n in (float("inf"), float("-inf")):
        return None
    # Values above 1e11 are epoch milliseconds; smaller values are seconds.
    ms = n if n > 100_000_000_000 else n * 1000
    try:
        return datetime.fromtimestamp(ms / 1000.0)
    except (OSError, OverflowError, ValueError):
        return None


def _age_text(when: datetime, now: datetime) -> str:
    mins = max(0, int((now - when).total_seconds() // 60))
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    if hours < 24:
        return f"{hours}hr"
    days = hours // 24
    if days == 1:
        return "1 day"
    return f"{days} days"
