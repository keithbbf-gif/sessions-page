"""Check out on the projects ledger.

One dark button. It resumes the selected session in its own harness
by calling desk._on_launch. Not a page. No browser. No port.
"""

from __future__ import annotations

import tkinter as tk

# Same near-black control as the desk action buttons.
_BG = "#181C26"
_INK = "#E8ECF4"
_ACTIVE = "#1E2430"
_LINE = "#2A3140"
_ACCENT = "#7C9CFF"
_FONT = ("Segoe UI", -15)


def build(parent, desk) -> None:
    """Place Check out on the ledger. Local resume only."""
    factory = getattr(desk, "tk", tk)
    button = factory.Button(
        parent,
        text="Check out",
        command=desk._on_launch,
        bg=_BG,
        fg=_INK,
        activebackground=_ACTIVE,
        activeforeground=_INK,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=_LINE,
        highlightcolor=_ACCENT,
        font=_FONT,
        padx=10,
        pady=4,
        cursor="hand2",
    )
    button.pack(side="left", padx=2)


def refresh(desk, hits) -> None:
    """No-op. The button does not follow the hit list."""
    return None
