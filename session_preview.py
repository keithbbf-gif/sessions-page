"""Right pane of the session band inside the ledger. Not a page.

Shows the source app, the age, and the project. A legal hit stays closed.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk

_BG = "#07080A"
_CARD = "#12151C"
_INK = "#E8ECF4"
_QUIET = "#6B7386"
_CLOSED = "Legal session stays closed."


def build(parent, desk) -> None:
    """Label plus Text. The Text is desk.ledger_session_preview."""
    tk.Label(
        parent, text="Session preview", fg=_QUIET, bg=_BG, anchor="w",
    ).pack(anchor="w", fill="x")
    text = tk.Text(
        parent, bg=_CARD, fg=_INK, insertbackground=_INK, relief="flat",
        wrap="word", highlightthickness=0, bd=0,
    )
    text.pack(fill="both", expand=True)
    text.configure(state="disabled")
    desk.ledger_session_preview = text


def fill(desk, hit) -> None:
    widget = getattr(desk, "ledger_session_preview", None)
    if widget is None:
        return
    if isinstance(hit, dict) and hit.get("legal"):
        body = _CLOSED
    elif isinstance(hit, dict):
        app = str(hit.get("harness") or hit.get("vendor") or hit.get("app") or "").strip()
        body = (
            f"Source app  {app or '—'}\n"
            f"Age  {_age(hit)}\n"
            f"Project  {_project(hit) or '—'}"
        )
    else:
        body = "Source app  —\nAge  —\nProject  —"
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", body)
    widget.configure(state="disabled")


def refresh(desk, hits) -> None:
    return None


def _age(hit: dict) -> str:
    stamp = hit.get("updated")
    if stamp in (None, ""):
        stamp = hit.get("last_activity")
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return "—"
    ms = n if n > 100000000000 else n * 1000
    mins = max(0, int((datetime.now().timestamp() * 1000 - ms) / 60000))
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    if hours < 24:
        return f"{hours}hr"
    days = hours // 24
    if days < 14:
        return f"{days} day" if days == 1 else f"{days} days"
    weeks = days // 7
    if weeks < 8:
        return f"{weeks} wks"
    months = max(1, days // 30)
    return f"{months} month" if months == 1 else f"{months} months"


def _project(hit: dict) -> str:
    raw = hit.get("cwd") if hit.get("cwd") else hit.get("project")
    text = str(raw or "").strip()
    if not text:
        return ""
    return Path(text).name
