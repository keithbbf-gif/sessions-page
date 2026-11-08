"""Cross-harness handoff. One ledger button, not a page.

The button calls desk._on_resume. That plans the other app and does not
place a foreign session id on the wrong resume flag. It does not launch.
"""

from __future__ import annotations

_BG = "#181C26"
_INK = "#E8ECF4"
_ACTIVE = "#1E2430"
_LINE = "#2A3140"
_ACCENT = "#7C9CFF"


def build(parent, desk) -> None:
    """Dark Cross-harness button on the ledger parent."""
    if not hasattr(desk, "tk") or not hasattr(desk, "_on_resume"):
        return
    tk = desk.tk
    if not hasattr(tk, "Button"):
        return
    button = tk.Button(
        parent,
        text="Cross-harness",
        command=desk._on_resume,
        bg=_BG,
        fg=_INK,
        activebackground=_ACTIVE,
        activeforeground=_INK,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=_LINE,
        highlightcolor=_ACCENT,
        font=("Segoe UI", -15),
        padx=10,
        pady=4,
        cursor="hand2",
    )
    if hasattr(button, "pack"):
        button.pack(side="left", padx=2)


def refresh(desk, hits) -> None:
    """No-op. The button does not redraw from the hit list."""
    return
