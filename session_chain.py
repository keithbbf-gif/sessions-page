"""Resume arrow on the session band inside the ledger.

Resume calls desk._on_launch. Hand off calls desk._on_resume.
Both plan or start the real local harness. Neither opens a page.
"""

from __future__ import annotations

import tkinter as tk

_BG = "#07080A"
_CARD = "#12151C"
_INK = "#E8ECF4"
_QUIET = "#6B7386"
_ELEVATED = "#181C26"
_LINE = "#2A3140"
_ACCENT = "#7C9CFF"
_FONT = ("Segoe UI", -15)


def _button(parent, text, command):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=_ELEVATED,
        fg=_INK,
        activebackground="#1E2430",
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


def build(parent, desk) -> None:
    row = tk.Frame(parent, bg=_BG)
    row.pack(fill="x")
    _button(row, "Resume", desk._on_launch).pack(side="left")
    tk.Label(row, text="→", fg=_QUIET, bg=_BG, font=_FONT).pack(side="left", padx=6)
    desk.ledger_chain_harness = tk.Label(
        row,
        text="TUI / harness",
        fg=_INK,
        bg=_CARD,
        font=_FONT,
        padx=8,
        pady=4,
    )
    desk.ledger_chain_harness.pack(side="left")
    tk.Label(row, text="→", fg=_QUIET, bg=_BG, font=_FONT).pack(side="left", padx=6)
    desk.ledger_chain_model = tk.Label(
        row,
        text="Model / agent",
        fg=_INK,
        bg=_CARD,
        font=_FONT,
        padx=8,
        pady=4,
    )
    desk.ledger_chain_model.pack(side="left", padx=(0, 12))
    _button(row, "Hand off", desk._on_resume).pack(side="left")


def fill(desk, hit) -> None:
    if not isinstance(hit, dict):
        hit = {}
    desk.ledger_chain_harness.configure(text=f"{hit.get('harness') or 'harness'} / harness")
    desk.ledger_chain_model.configure(text=str(hit.get("model") or "Model / agent"))


def refresh(desk, hits) -> None:
    return None
