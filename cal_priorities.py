"""Next priorities inside the ledger calendar region. Not a page."""

from __future__ import annotations

import tkinter as tk

_BG = "#07080A"
_FG = "#A7B0C3"
_FONT = ("Segoe UI", -15)
# Two spaces after the title. Same line the calendar plan already uses.
_LINE = "Next priorities  crashed first, then the oldest unfinished."


def _crashed_count(hits) -> int:
    count = 0
    for hit in hits or ():
        if isinstance(hit, dict) and str(hit.get("status") or "") == "crashed":
            count += 1
    return count


def build(parent, desk) -> None:
    label = tk.Label(
        parent,
        text=_LINE,
        fg=_FG,
        bg=_BG,
        justify="left",
        anchor="w",
        font=_FONT,
        wraplength=980,
    )
    label.pack(fill="x", padx=16, pady=(0, 12))
    desk.ledger_priorities = label


def refresh(desk, hits) -> None:
    count = _crashed_count(hits)
    text = f"{count} {_LINE}" if count else _LINE
    desk.ledger_priorities.configure(text=text)
