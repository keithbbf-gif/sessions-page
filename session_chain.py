"""Resume arrow on the session band inside the ledger.

Resume launches the source harness. Hand off exports the transcript and
starts a different installed harness, then records the new session as a
child. Neither opens a page.
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
    _button(row, "Hand off", desk._on_handoff).pack(side="left")
    _mount_target(row, desk)


def _installed(desk) -> list[str]:
    """Harness names with a binary on this machine. Uninstalled ones stay hidden."""
    try:
        import engine

        return [str(name) for name, _path in engine.installed_launchers() if str(name).strip()]
    except Exception:
        return []


def _mount_target(row, desk) -> None:
    tk = desk.tk
    var = getattr(desk, "app_var", None)
    if var is None or not hasattr(var, "set"):
        return
    try:
        menu = tk.OptionMenu(row, var, "")
        menu.configure(
            bg=_ELEVATED, fg=_INK, activebackground="#1E2430", activeforeground=_INK,
            relief="flat", highlightthickness=1, highlightbackground=_LINE,
            highlightcolor=_ACCENT, font=_FONT, bd=0, padx=10, pady=4,
        )
        menu["menu"].configure(
            bg=_CARD, fg=_INK, activebackground=_ACCENT, activeforeground=_BG, bd=0, font=_FONT,
        )
    except Exception:
        return
    menu.pack(side="left", padx=(6, 0))
    desk.ledger_target_box = menu
    _fill_targets(desk)


def _fill_targets(desk) -> None:
    menu = getattr(desk, "ledger_target_box", None)
    var = getattr(desk, "app_var", None)
    if menu is None or var is None or not hasattr(var, "set"):
        return
    hit = None
    rows = getattr(desk, "hits", None) or []
    index = getattr(desk, "selected_index", None)
    if isinstance(index, int) and 0 <= index < len(rows) and isinstance(rows[index], dict):
        hit = rows[index]
    harness = str((hit or {}).get("harness") or "")
    choices = _installed(desk)
    if harness and harness not in choices:
        choices = choices + [harness]
    if not choices:
        return
    try:
        popup = menu["menu"]
        popup.delete(0, "end")
        for choice in choices:
            popup.add_command(label=choice, command=lambda c=choice: var.set(c))
    except Exception:
        return
    painting = getattr(desk, "_painting", False)
    desk._painting = True
    try:
        var.set(harness if harness in choices else choices[0])
    except Exception:
        pass
    finally:
        desk._painting = painting


def fill(desk, hit) -> None:
    if not isinstance(hit, dict):
        hit = {}
    desk.ledger_chain_harness.configure(text=f"{hit.get('harness') or 'harness'} / harness")
    desk.ledger_chain_model.configure(text=str(hit.get("model") or "Model / agent"))
    _fill_targets(desk)


def refresh(desk, hits) -> None:
    return None
