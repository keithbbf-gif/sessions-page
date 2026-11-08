"""Left list of the projects region inside the ledger.

Stdlib and tkinter only. Importing this module opens no window.
"""

from __future__ import annotations

import tkinter as tk


_BG = "#12151C"
_INK = "#E8ECF4"
_SELECT = "#1E2430"
_FONT = ("Segoe UI", -15)


def _project(hit: dict) -> str:
    if hit.get("legal"):
        return ""
    cwd = hit.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        text = cwd
    else:
        project = hit.get("project")
        text = project if isinstance(project, str) else ""
    text = text.replace("/", "\\").rstrip("\\").strip()
    if not text:
        return ""
    return text.split("\\")[-1]


def _title(hit: dict) -> str:
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "")


def _row(hit: dict) -> str:
    return f"{_project(hit) or 'No project'}  ·  {_title(hit)}"


def build(parent, desk) -> None:
    """Dark list. Selection calls desk.ledger_open_project_title(index) when set."""
    box = tk.Listbox(
        parent,
        bg=_BG,
        fg=_INK,
        selectbackground=_SELECT,
        selectforeground=_INK,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        activestyle="none",
        exportselection=False,
        selectmode="browse",
        font=_FONT,
        width=36,
    )
    desk.ledger_proj_list = box
    desk.ledger_proj_hits = []

    def _on_select(_event=None) -> None:
        picked = box.curselection()
        if not picked:
            return
        opener = getattr(desk, "ledger_open_project_title", None)
        if callable(opener):
            opener(int(picked[0]))

    box.bind("<<ListboxSelect>>", _on_select)
    box.pack(fill="both", expand=True)


def refresh(desk, hits) -> None:
    """Rebuild rows as 'Project  ·  title' and keep the same hit dicts."""
    box = desk.ledger_proj_list
    box.delete(0, "end")
    kept: list[dict] = []
    for hit in hits or ():
        if not isinstance(hit, dict):
            continue
        box.insert("end", _row(hit))
        kept.append(hit)
    desk.ledger_proj_hits = kept
