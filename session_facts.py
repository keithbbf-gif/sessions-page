"""Ledger-band session header. One wrapping label. No window."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

_BG = "#07080A"
_FG = "#A7B0C3"
_DASH = "—"

_START_KEYS = (
    "started", "start", "started_at", "start_time",
    "created", "created_at", "updated",
)
_END_KEYS = ("ended", "end", "ended_at", "end_time", "finished_at")
_AGE_KEYS = ("updated", "last_activity", "ended", "started")


def build(parent, desk) -> None:
    """Put the header in the ledger band. Does not open a window."""
    import tkinter as tk

    label = tk.Label(
        parent,
        text="",
        bg=_BG,
        fg=_FG,
        anchor="w",
        justify="left",
        font=("Segoe UI", 11),
        wraplength=720,
        relief="flat",
        bd=0,
        highlightthickness=0,
    )
    label.pack(side="top", fill="x", anchor="w", padx=12, pady=4)
    desk.ledger_session_facts = label

    def _fit(event, widget=label, host=parent):
        if event.widget is not host:
            return
        width = int(getattr(event, "width", 0) or 0) - 24
        if width < 40:
            return
        try:
            current = int(float(widget.cget("wraplength")))
        except (TypeError, ValueError):
            current = 0
        if abs(current - width) < 8:
            return
        widget.configure(wraplength=width)

    try:
        parent.bind("<Configure>", _fit, add="+")
    except tk.TclError:
        parent.bind("<Configure>", _fit)


def fill(desk, hit) -> None:
    label = getattr(desk, "ledger_session_facts", None)
    if label is None:
        return
    label.configure(text=_line(hit if isinstance(hit, dict) else {}))


def refresh(desk, hits) -> None:
    """No-op. The manager calls fill."""
    return


def _epoch(stamp):
    if isinstance(stamp, bool) or stamp is None:
        return None
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return None
    if n != n or n <= 0:
        return None
    if n > 100000000000:
        n = n / 1000.0
    if n < 1000000000:
        return None
    return n


def _first_epoch(hit: dict, keys: tuple[str, ...]):
    for key in keys:
        if key not in hit:
            continue
        found = _epoch(hit.get(key))
        if found is not None:
            return found
    return None


def _clock(epoch):
    if epoch is None:
        return None
    try:
        return datetime.fromtimestamp(epoch)
    except (OSError, OverflowError, ValueError):
        return None


def _age(stamp) -> str:
    n = _epoch(stamp)
    if n is None:
        return _DASH
    mins = max(0, int((datetime.now().timestamp() - n) / 60))
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    if hours < 24:
        return f"{hours}hr"
    days = hours // 24
    if days < 14:
        return f"{days} day" if days == 1 else f"{days} days"
    weeks = days // 7
    if weeks < 8:
        return f"{weeks} wks"
    months = max(1, days // 30)
    return f"{months} month" if months == 1 else f"{months} months"


def _size_kb(hit: dict) -> str:
    size = hit.get("bytes")
    if isinstance(size, bool) or size is None:
        return _DASH
    try:
        nbytes = int(size)
    except (TypeError, ValueError):
        return _DASH
    if nbytes <= 0:
        return _DASH
    return f"{max(1, nbytes // 1024)} KB"


def _topic(hit: dict) -> str:
    if hit.get("legal"):
        return _DASH
    for key in ("cwd", "project"):
        raw = hit.get(key)
        if not isinstance(raw, str):
            continue
        name = Path(raw.strip()).name
        if name and name not in (".", ".."):
            return name
    return _DASH


def _path(hit: dict) -> str:
    for key in ("path", "location", "cwd"):
        raw = hit.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _line(hit: dict) -> str:
    started = _clock(_first_epoch(hit, _START_KEYS))
    ended = _clock(_first_epoch(hit, _END_KEYS))
    age_stamp = None
    for key in _AGE_KEYS:
        if key in hit and _epoch(hit.get(key)) is not None:
            age_stamp = hit.get(key)
            break
    parts = [
        f"Date {started.date().isoformat() if started else _DASH}",
        f"Start {started.strftime('%H:%M') if started else _DASH}",
        f"End {ended.strftime('%H:%M') if ended else _DASH}",
        f"Size {_size_kb(hit)}",
        f"Tokens input / output / total {_DASH}",
        f"Time {_age(age_stamp)}",
        f"Topic {_topic(hit)}",
    ]
    if hit.get("legal"):
        parts.append("Legal session")
    else:
        parts.append(f"Path {_path(hit) or _DASH}")
    return "    ".join(parts)
