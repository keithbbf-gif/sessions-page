"""Project cards inside the ledger. Stdlib and tkinter only. No Toplevel."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime


_BG = "#07080A"
_CARD = "#12151C"
_LINE = "#2A3140"
_INK = "#E8ECF4"
_SECONDARY = "#A7B0C3"
_ACCENT = "#7C9CFF"
_EM = "\u2014"
_LIMIT = 9
_FONT = ("Segoe UI", -15)
_FONT_PR = ("Segoe UI", -15, "bold")


def _tk(desk):
    module = getattr(desk, "tk", None)
    if getattr(module, "Frame", None) is None:
        return tk
    return module


def build(parent, desk) -> None:
    """Parent a 3-column card grid and store it as desk.ledger_cards."""
    ui = _tk(desk)
    frame = ui.Frame(parent, bg=_BG, highlightthickness=0, bd=0)
    for column in range(3):
        frame.columnconfigure(column, weight=1, uniform="proj")
    frame.pack(fill="both", expand=True)
    desk.ledger_cards = frame


def refresh(desk, hits) -> None:
    """Clear the grid and paint at most nine project cards."""
    frame = getattr(desk, "ledger_cards", None)
    if frame is None:
        return
    ui = _tk(desk)
    for child in list(frame.winfo_children()):
        child.destroy()
    groups = _groups(hits)[:_LIMIT]
    for index, (name, rows) in enumerate(groups):
        card = _card(ui, frame, index + 1, name, rows)
        card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=6, pady=6)


def _groups(hits) -> list[tuple[str, list]]:
    rows = _rows(hits)
    buckets: dict[str, list] = {}
    for hit in rows:
        key = _segment(hit)
        buckets.setdefault(key, []).append(hit)
    ordered = sorted(buckets.items(), key=lambda item: (item[0] == "", item[0].casefold()))
    return [(key or "No project", group) for key, group in ordered]


def _rows(hits) -> list[dict]:
    if not hits:
        return []
    if isinstance(hits, dict):
        for key in ("hits", "rows", "sessions"):
            found = hits.get(key)
            if isinstance(found, list):
                hits = found
                break
        else:
            hits = [hits]
    return [hit for hit in hits if isinstance(hit, dict)]


def _segment(hit: dict) -> str:
    if hit.get("legal"):
        return ""
    raw = hit.get("cwd") or ""
    if not isinstance(raw, str):
        raw = str(raw)
    text = raw.replace("/", "\\").rstrip("\\")
    if not text:
        return ""
    return text.split("\\")[-1]


def _stamp(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    if number > 100_000_000_000:
        number = number / 1000.0
    try:
        return datetime.fromtimestamp(number)
    except (OverflowError, OSError, ValueError):
        return None


def _span(rows: list) -> tuple[str, str]:
    found = [stamp for stamp in (_stamp(hit.get("updated")) for hit in rows) if stamp is not None]
    if not found:
        return _EM, _EM
    return min(found).strftime("%Y-%m-%d"), max(found).strftime("%Y-%m-%d")


def _card(ui, parent, number: int, name: str, rows: list):
    shell = ui.Frame(parent, bg=_LINE, padx=1, pady=1, highlightthickness=0, bd=0)
    card = ui.Frame(shell, bg=_CARD, padx=12, pady=10, highlightthickness=0, bd=0)
    card.pack(fill="both", expand=True)
    body = ui.Frame(card, bg=_CARD, highlightthickness=0, bd=0)
    body.pack(fill="both", expand=True)
    mark = ui.Canvas(body, width=36, height=36, bg=_CARD, highlightthickness=0, bd=0)
    mark.pack(side="left", anchor="n", padx=(0, 10))
    mark.create_rectangle(4, 14, 16, 32, outline=_ACCENT, width=1)
    mark.create_rectangle(18, 8, 32, 32, outline=_ACCENT, width=1)
    start, end = _span(rows)
    lines = (
        (f"Pr {number}", _INK, _FONT_PR),
        (name, _INK, _FONT),
        (f"{len(rows)} sessions", _SECONDARY, _FONT),
        (f"Token count {_EM}", _SECONDARY, _FONT),
        (f"Project start {start}", _SECONDARY, _FONT),
        (f"End {end}", _SECONDARY, _FONT),
    )
    text = ui.Frame(body, bg=_CARD, highlightthickness=0, bd=0)
    text.pack(side="left", anchor="nw", fill="both", expand=True)
    for value, color, font in lines:
        ui.Label(
            text, text=value, fg=color, bg=_CARD, anchor="w", justify="left", font=font,
        ).pack(anchor="w", fill="x")
    return shell
