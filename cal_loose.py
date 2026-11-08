"""Summary and Loose ends under the calendar. A label in the ledger, not a page."""

from __future__ import annotations


def _text(hits) -> str:
    rows = list(hits) if isinstance(hits, (list, tuple)) else []
    idle = 0
    for hit in rows:
        status = hit.get("status") if isinstance(hit, dict) else None
        if status == "idle":
            idle += 1
    n = len(rows)
    if idle == 0:
        return f"Summary  {n} sessions.  Loose ends  none marked"
    return f"Summary  {n} sessions.  Loose ends  {idle} idle."


def build(parent, desk) -> None:
    tk = desk.tk
    bg = "#07080A"
    try:
        bg = parent.cget("bg")
    except tk.TclError:
        pass
    desk.ledger_loose = tk.Label(
        parent,
        text=_text(()),
        fg="#A7B0C3",
        bg=bg,
        anchor="w",
        justify="left",
        font=("Segoe UI", -15),
    )
    desk.ledger_loose.pack(side="top", fill="x", anchor="w", padx=16, pady=(4, 8))


def refresh(desk, hits) -> None:
    desk.ledger_loose.configure(text=_text(hits))
