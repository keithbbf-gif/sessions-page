"""Month grid inside the ledger. The manager draws the title."""

from __future__ import annotations

import calendar
from datetime import datetime

import tkinter as tk

_BG = "#07080A"
_CELL = "#12151C"
_INK = "#E8ECF4"
_FONT = ("Segoe UI", -15)
_DAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


def _query(desk) -> str:
    raw = getattr(desk, "ledger_cal_q", "")
    if raw is None:
        return ""
    get = getattr(raw, "get", None)
    if callable(get):
        try:
            raw = get()
        except tk.TclError:
            return ""
    return str(raw or "").strip().casefold()


def _title(hit: dict) -> str:
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "")


def _project(hit: dict) -> str:
    parts: list[str] = []
    named = hit.get("project")
    if isinstance(named, str) and named.strip():
        parts.append(named.strip())
    cwd = str(hit.get("cwd") or "").replace("/", "\\").rstrip("\\")
    if cwd and not hit.get("legal"):
        leaf = cwd.split("\\")[-1]
        if leaf and leaf not in parts:
            parts.append(leaf)
    return " ".join(parts)


def _when(hit: dict) -> datetime | None:
    stamp = hit.get("updated")
    if stamp is None:
        stamp = hit.get("last_activity")
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return None
    ms = n if n > 100000000000 else n * 1000
    try:
        return datetime.fromtimestamp(ms / 1000)
    except (OSError, OverflowError, ValueError):
        return None


def _matches(hit: dict, term: str) -> bool:
    if not term:
        return True
    return term in _title(hit).casefold() or term in _project(hit).casefold()


def _counts(hits, year: int, month: int, term: str) -> dict[int, int]:
    counts: dict[int, int] = {}
    rows = hits if isinstance(hits, (list, tuple)) else ()
    for hit in rows:
        if not isinstance(hit, dict) or not _matches(hit, term):
            continue
        when = _when(hit)
        if when is None or when.year != year or when.month != month:
            continue
        counts[when.day] = counts.get(when.day, 0) + 1
    return counts


def build(parent, desk) -> None:
    old = getattr(desk, "ledger_cal_grid", None)
    if old is not None:
        try:
            old.destroy()
        except tk.TclError:
            pass
    grid = tk.Frame(parent, bg=_BG)
    grid.pack(fill="both", expand=True, padx=16, pady=(0, 8))
    for col in range(7):
        grid.columnconfigure(col, weight=1, uniform="cal")
    desk.ledger_cal_grid = grid
    refresh(desk, getattr(desk, "hits", ()))


def refresh(desk, hits) -> None:
    grid = getattr(desk, "ledger_cal_grid", None)
    if grid is None:
        return
    try:
        if not grid.winfo_exists():
            return
    except tk.TclError:
        return
    for child in grid.winfo_children():
        child.destroy()
    now = datetime.now()
    weeks = calendar.Calendar(firstweekday=calendar.SUNDAY).monthdayscalendar(now.year, now.month)
    counts = _counts(hits, now.year, now.month, _query(desk))
    for row in range(7):
        grid.rowconfigure(row, weight=0)
    for col, name in enumerate(_DAYS):
        tk.Label(grid, text=name, fg=_INK, bg=_BG, font=_FONT).grid(row=0, column=col, padx=2, pady=(0, 4))
    for row, week in enumerate(weeks, start=1):
        grid.rowconfigure(row, weight=1, uniform="week")
        for col, day in enumerate(week):
            text = ""
            if day:
                text = f"{day}\n{counts[day]}" if day in counts else str(day)
            tk.Label(
                grid,
                text=text,
                fg=_INK,
                bg=_CELL,
                anchor="nw",
                justify="left",
                font=_FONT,
                width=8,
                height=3,
                padx=6,
                pady=4,
            ).grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
