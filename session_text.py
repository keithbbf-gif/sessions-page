"""Left pane of the session band. Title and folder only.

The desk preview path writes this same widget later. This module does not
open a transcript.
"""

from __future__ import annotations

import tkinter as tk

_PAGE = "#07080A"
_QUIET = "#6B7386"
_BG = "#12151C"
_FG = "#E8ECF4"
_CLOSED = "Legal session stays closed."


def build(parent, desk) -> None:
    tk.Label(
        parent, text="Session text", fg=_QUIET, bg=_PAGE, anchor="w",
    ).pack(fill="x", anchor="w")
    text = tk.Text(
        parent, bg=_BG, fg=_FG, wrap="word", relief="flat",
        highlightthickness=0, bd=0, insertbackground=_FG,
        font=("Segoe UI", -15),
    )
    text.pack(fill="both", expand=True)
    desk.ledger_session_text = text


def _line(value) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def fill(desk, hit) -> None:
    widget = desk.ledger_session_text
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    if isinstance(hit, dict) and hit.get("legal"):
        widget.insert("1.0", _CLOSED)
        return
    title = ""
    cwd = ""
    if isinstance(hit, dict):
        title = _line(hit.get("title") or hit.get("vendor_id") or hit.get("id"))
        cwd = _line(hit.get("cwd"))
    widget.insert("1.0", title + "\n" + cwd)


def refresh(desk, hits) -> None:
    return None
