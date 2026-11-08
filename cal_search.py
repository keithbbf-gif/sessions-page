"""Search terms bar inside the ledger calendar region. Not a page."""
from __future__ import annotations

import tkinter as tk

_BG = "#07080A"
_CARD = "#12151C"
_LINE = "#2A3140"
_INK = "#E8ECF4"
_QUIET = "#6B7386"
_ACCENT = "#7C9CFF"
_FONT = ("Segoe UI", -15)
_FONT_SMALL = ("Segoe UI", -13)

_FIELDS = (
    ("Search terms", "ledger_cal_q", 28),
    ("Start", "ledger_cal_start", 12),
    ("End", "ledger_cal_end", 12),
)


def _var(desk, parent, name: str) -> tk.Variable:
    current = getattr(desk, name, None)
    if isinstance(current, tk.Variable):
        return current
    initial = current if isinstance(current, str) else ""
    var = tk.StringVar(master=parent, value=initial)
    setattr(desk, name, var)
    return var


def _on_return(_event, desk) -> None:
    try:
        import ledger_calendar
    except ImportError:
        return
    ledger_calendar.refresh(desk, desk.hits)


def build(parent, desk) -> None:
    bar = tk.Frame(parent, bg=_BG)
    bar.pack(fill="x", padx=16, pady=(4, 4))
    for text, name, width in _FIELDS:
        tk.Label(
            bar, text=text, fg=_QUIET, bg=_BG, font=_FONT_SMALL,
        ).pack(side="left", padx=(0, 6))
        entry = tk.Entry(
            bar,
            textvariable=_var(desk, parent, name),
            width=width,
            bg=_CARD,
            fg=_INK,
            insertbackground=_INK,
            relief="flat",
            font=_FONT,
            highlightthickness=1,
            highlightbackground=_LINE,
            highlightcolor=_ACCENT,
            bd=0,
        )
        entry.pack(side="left", padx=(0, 12), ipady=4)
        entry.bind("<Return>", lambda event, bound=desk: _on_return(event, bound))


def refresh(desk, hits) -> None:
    return
