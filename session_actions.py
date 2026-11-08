"""Session-band actions from the old desk. Not a separate page."""

from __future__ import annotations


_BG = "#07080A"
_ELEVATED = "#181C26"
_LINE = "#2A3140"
_INK = "#E8ECF4"
_ACCENT = "#7C9CFF"
_FONT = ("Segoe UI", -15)

_ACTIONS = (
    ("Load", "_on_load"),
    ("Import", "_on_import"),
    ("Export", "_on_export"),
    ("Anonymize", "_on_anonymize"),
    ("Check recovery", "_on_recover"),
    ("Restore", "_on_restore"),
    ("Check strip", "_on_strip_dry"),
    ("Write strip", "_on_strip"),
    ("Name", "_on_name"),
)


def build(parent, desk) -> None:
    tk = desk.tk
    row = tk.Frame(parent, bg=_BG)
    row.pack(fill="x")
    for label, name in _ACTIONS:
        if not hasattr(desk, name):
            continue
        tk.Button(
            row,
            text=label,
            command=getattr(desk, name),
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
        ).pack(side="left", padx=(0, 6), pady=4)


def fill(desk, hit) -> None:
    return None


def refresh(desk, hits) -> None:
    return None
