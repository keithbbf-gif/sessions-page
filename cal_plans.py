"""Seven-day row inside the ledger calendar region. Not a page."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta

_BG = "#07080A"
_CARD = "#12151C"
_TODAY = "#181C26"
_LINE = "#2A3140"
_INK = "#E8ECF4"
_QUIET = "#6B7386"
_ACCENT = "#7C9CFF"
_FONT = ("Segoe UI", -15)
_FONT_SMALL = ("Segoe UI", -13)
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _day_text(day: date) -> str:
    return f"{_WEEKDAYS[day.weekday()]} {day.isoformat()}"


def _role(day: date, today: date) -> str:
    if day < today:
        return "sessions"
    if day > today:
        return "Plans"
    return "today"


def build(parent, desk) -> None:
    """Dark seven-cell row: three past days, today, and three coming days."""
    old = getattr(desk, "ledger_plan_row", None)
    if old is not None:
        try:
            old.destroy()
        except tk.TclError:
            pass
    row = tk.Frame(parent, bg=_BG)
    row.pack(fill="x", padx=16, pady=(4, 4))
    cells = []
    for index in range(7):
        row.columnconfigure(index, weight=1)
        cell = tk.Frame(
            row,
            bg=_CARD,
            highlightthickness=1,
            highlightbackground=_LINE,
            highlightcolor=_ACCENT,
        )
        cell.grid(row=0, column=index, padx=3, pady=2, sticky="nsew")
        when = tk.Label(
            cell, text="", fg=_QUIET, bg=_CARD, font=_FONT_SMALL, anchor="w",
        )
        when.pack(fill="x", padx=8, pady=(8, 0))
        role = tk.Label(
            cell, text="", fg=_INK, bg=_CARD, font=_FONT, anchor="w",
        )
        role.pack(fill="x", padx=8, pady=(2, 8))
        cells.append((cell, when, role))
    row._cells = cells
    desk.ledger_plan_row = row
    refresh(desk, getattr(desk, "hits", None))


def refresh(desk, hits) -> None:
    """Fill seven cells with real dates. Past says sessions, today says today, later says Plans."""
    del hits
    row = getattr(desk, "ledger_plan_row", None)
    if row is None:
        return
    try:
        if not row.winfo_exists():
            return
    except tk.TclError:
        return
    cells = getattr(row, "_cells", None)
    if not cells:
        return
    today = date.today()
    start = today - timedelta(days=3)
    for offset, (cell, when, role) in enumerate(cells):
        day = start + timedelta(days=offset)
        word = _role(day, today)
        bg = _TODAY if word == "today" else _CARD
        edge = _ACCENT if word == "today" else _LINE
        cell.configure(bg=bg, highlightbackground=edge)
        when.configure(text=_day_text(day), bg=bg)
        role.configure(text=word, bg=bg)
