"""Keywords and full path on the session band inside the ledger.

The desk owns find, load, and resume. This module only paints the line.
"""

from __future__ import annotations

import tkinter as tk

_EM = "\u2014"
_BG = "#07080A"
_FG = "#A7B0C3"
_FONT = ("Segoe UI", -13)


def build(parent, desk) -> None:
    """A label stored as desk.ledger_keywords. Dark colors."""
    desk.ledger_keywords = tk.Label(
        parent,
        text=_line(None),
        fg=_FG,
        bg=_BG,
        anchor="w",
        justify="left",
        font=_FONT,
        padx=12,
        pady=4,
        relief="flat",
        bd=0,
        highlightthickness=0,
    )
    desk.ledger_keywords.pack(fill="x")


def fill(desk, hit) -> None:
    """Location <full path or em dash>    Keywords <up to six words of the title>."""
    label = getattr(desk, "ledger_keywords", None)
    if label is None:
        return
    label.configure(text=_line(hit))


def refresh(desk, hits) -> None:
    """No-op. fill() owns the line."""
    return None


def _line(hit) -> str:
    return f"Location {_location(hit)}    Keywords {_keywords(hit)}"


def _location(hit) -> str:
    if not isinstance(hit, dict) or hit.get("legal"):
        return _EM
    path = hit.get("path")
    if isinstance(path, str):
        text = path.strip()
    elif path is None:
        text = ""
    else:
        text = str(path).strip()
    return text or _EM


def _keywords(hit) -> str:
    if not isinstance(hit, dict):
        return _EM
    title = hit.get("title")
    if not isinstance(title, str):
        title = "" if title is None else str(title)
    words = title.split()
    if not words:
        return _EM
    return " ".join(words[:6])
