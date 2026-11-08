"""Lower-right projects region of the one ledger window.

Not a page. No Toplevel, browser, or port. Stdlib and tkinter only.
"""

from __future__ import annotations

import importlib
import sys
from datetime import datetime
from pathlib import Path

_BG = "#07080A"
_CARD = "#12151C"
_INK = "#E8ECF4"
_QUIET = "#6B7386"
_SECONDARY = "#A7B0C3"
_SELECT = "#1E2430"
_EM = "\u2014"
_MS_CUT = 100_000_000_000
_PIECES = (
    "proj_titles",
    "proj_cards",
    "proj_counts",
    "proj_span",
    "proj_checkout",
    "proj_cross",
)


def build(parent, desk) -> None:
    """Lay the projects region into parent. Does not open a window."""
    tk = _tk(desk)
    try:
        parent.configure(bg=_BG)
    except tk.TclError:
        pass
    for child in list(parent.winfo_children()):
        child.destroy()

    desk.ledger_open_project_title = lambda index, bound=desk: _open_title(bound, index)

    shell = tk.Frame(parent, bg=_BG, highlightthickness=0, bd=0)
    shell.pack(fill="both", expand=True)

    head = tk.Frame(shell, bg=_BG, highlightthickness=0, bd=0)
    head.pack(fill="x", padx=16, pady=(12, 4))
    titles = tk.Frame(head, bg=_BG, highlightthickness=0, bd=0)
    titles.pack(side="left", fill="x", expand=True)
    tk.Label(
        titles, text="Check for projects", fg=_QUIET, bg=_BG, anchor="w",
        font=("Segoe UI", -13),
    ).pack(anchor="w")
    tk.Label(
        titles, text="Projects view", fg=_INK, bg=_BG, anchor="w",
        font=("Segoe UI", 18, "bold"),
    ).pack(anchor="w")

    right_head = tk.Frame(head, bg=_BG, highlightthickness=0, bd=0)
    right_head.pack(side="right", anchor="ne")
    tk.Label(
        right_head, text="Check out  \u00b7  cross-harness", fg=_QUIET, bg=_BG,
        anchor="e", font=("Segoe UI", -13),
    ).pack(anchor="e")
    actions = tk.Frame(right_head, bg=_BG, highlightthickness=0, bd=0)
    check_slot = tk.Frame(actions, bg=_BG, highlightthickness=0, bd=0)
    check_slot.pack(side="left")
    cross_slot = tk.Frame(actions, bg=_BG, highlightthickness=0, bd=0)
    cross_slot.pack(side="left", padx=(6, 0))
    checkout_on = _mount("proj_checkout", check_slot, desk)
    cross_on = _mount("proj_cross", cross_slot, desk)
    if checkout_on or cross_on:
        actions.pack(anchor="e", pady=(4, 0))

    body = tk.Frame(shell, bg=_BG, highlightthickness=0, bd=0)
    body.pack(fill="both", expand=True, padx=16, pady=(8, 12))
    left = tk.Frame(body, bg=_BG, highlightthickness=0, bd=0)
    left.pack(side="left", fill="y")
    cards_host = tk.Frame(body, bg=_BG, highlightthickness=0, bd=0)
    cards_host.pack(side="left", fill="both", expand=True, padx=(12, 0))

    # counts and span mount an empty frame and do not paint. Keep them off the grid.
    hook = tk.Frame(shell, bg=_BG, highlightthickness=0, bd=0)
    _mount("proj_counts", hook, desk)
    _mount("proj_span", hook, desk)

    state = {"own_titles": False, "own_cards": False}
    desk._ledger_projects_state = state
    if not _mount("proj_titles", left, desk):
        state["own_titles"] = True
        _build_titles(tk, left, desk)
    if not _mount("proj_cards", cards_host, desk):
        state["own_cards"] = True
        _build_cards(tk, cards_host, desk)

    refresh(desk, getattr(desk, "hits", ()) or ())


def refresh(desk, hits) -> None:
    """Group hits by the last cwd folder and repaint the list and the cards."""
    rows = [hit for hit in (hits or []) if isinstance(hit, dict)]
    state = getattr(desk, "_ledger_projects_state", None) or {}
    ordered = _title_order(rows)

    if state.get("own_titles") or not _call_refresh("proj_titles", desk, ordered):
        _fill_titles(desk, ordered)
    if state.get("own_cards") or not _call_refresh("proj_cards", desk, rows):
        _fill_cards(desk, rows)

    for name in ("proj_counts", "proj_span", "proj_checkout", "proj_cross"):
        _call_refresh(name, desk, rows)


def _open_title(desk, index) -> None:
    """Select that row in the ledger list. Does not open a window."""
    try:
        slot = int(index)
    except (TypeError, ValueError):
        return
    shown = getattr(desk, "ledger_proj_hits", None)
    if not isinstance(shown, list) or slot < 0 or slot >= len(shown):
        return
    hit = shown[slot]
    if not isinstance(hit, dict):
        return
    real = _desk_index(desk, hit)
    if real is None:
        return
    select = getattr(desk, "_select", None)
    if callable(select):
        select(real)


def _desk_index(desk, hit: dict) -> int | None:
    rows = getattr(desk, "hits", None)
    if not isinstance(rows, list):
        return None
    for index, row in enumerate(rows):
        if row is hit:
            return index
    ident = hit.get("id")
    if ident in (None, ""):
        return None
    fallback = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("id") != ident:
            continue
        if row.get("cwd") == hit.get("cwd") and row.get("title") == hit.get("title"):
            return index
        if fallback is None:
            fallback = index
    return fallback


def _title_order(rows: list[dict]) -> list[dict]:
    paired = list(enumerate(rows))
    paired.sort(key=lambda item: (_list_project(item[1]).casefold(), item[0]))
    return [hit for _, hit in paired]


def _list_project(hit: dict) -> str:
    if hit.get("legal"):
        return "No project"
    cwd = hit.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        text = cwd
    else:
        project = hit.get("project")
        text = project if isinstance(project, str) else ""
    text = text.replace("/", "\\").rstrip("\\").strip()
    if not text:
        return "No project"
    return text.split("\\")[-1] or "No project"


def _list_title(hit: dict) -> str:
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "")


def _row_text(hit: dict) -> str:
    return f"{_list_project(hit)}  \u00b7  {_list_title(hit)}"


def _build_titles(tk, parent, desk) -> None:
    box = tk.Listbox(
        parent, bg=_CARD, fg=_INK, selectbackground=_SELECT, selectforeground=_INK,
        relief="flat", borderwidth=0, highlightthickness=0, activestyle="none",
        exportselection=False, selectmode="browse", font=("Segoe UI", -15), width=36,
    )
    desk.ledger_proj_list = box
    desk.ledger_proj_hits = []

    def on_select(_event=None, bound=desk, widget=box) -> None:
        picked = widget.curselection()
        if picked:
            _open_title(bound, int(picked[0]))

    box.bind("<<ListboxSelect>>", on_select)
    box.pack(fill="both", expand=True)


def _fill_titles(desk, rows: list[dict]) -> None:
    box = getattr(desk, "ledger_proj_list", None)
    if box is None:
        return
    box.delete(0, "end")
    kept = []
    for hit in rows:
        box.insert("end", _row_text(hit))
        kept.append(hit)
    desk.ledger_proj_hits = kept


def _build_cards(tk, parent, desk) -> None:
    frame = tk.Frame(parent, bg=_BG, highlightthickness=0, bd=0)
    for column in range(3):
        frame.columnconfigure(column, weight=1, uniform="proj")
    frame.pack(fill="both", expand=True)
    desk.ledger_cards = frame


def _fill_cards(desk, rows: list[dict]) -> None:
    frame = getattr(desk, "ledger_cards", None)
    if frame is None:
        return
    tk = _tk(desk)
    for child in list(frame.winfo_children()):
        child.destroy()
    for index, (name, group) in enumerate(_groups(rows)):
        start, end = _span(group)
        card = tk.Frame(frame, bg=_CARD, padx=12, pady=10, highlightthickness=0, bd=0)
        card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=6, pady=6)
        lines = (
            (f"Pr {index + 1}", _INK, ("Segoe UI", 14, "bold")),
            (name, _SECONDARY, ("Segoe UI", -15)),
            (f"{len(group)} sessions", _SECONDARY, ("Segoe UI", -15)),
            (f"Token count {_EM}", _SECONDARY, ("Segoe UI", -15)),
            (f"Project start {start}", _SECONDARY, ("Segoe UI", -15)),
            (f"End {end}", _SECONDARY, ("Segoe UI", -15)),
        )
        for text, color, font in lines:
            tk.Label(card, text=text, fg=color, bg=_CARD, anchor="w", font=font).pack(anchor="w")


def _groups(hits) -> list[tuple[str, list]]:
    mod = _module("proj_counts")
    groups = getattr(mod, "groups", None) if mod is not None else None
    if callable(groups):
        try:
            found = groups(hits)
        except Exception:
            found = None
        if isinstance(found, list):
            return [(str(name), list(bucket)) for name, bucket in found if isinstance(bucket, list)]
    buckets: dict[str, list] = {}
    order: list[str] = []
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        name = _folder_name(hit)
        if name not in buckets:
            buckets[name] = []
            order.append(name)
        buckets[name].append(hit)
    order.sort(key=lambda name: (name == "No project", name.casefold()))
    return [(name, buckets[name]) for name in order]


def _folder_name(hit: dict) -> str:
    """Last folder of cwd. A blank cwd is No project. Legal cwd stays closed."""
    if hit.get("legal"):
        return "No project"
    raw = hit.get("cwd")
    if raw is None:
        return "No project"
    text = str(raw).strip().replace("/", "\\").rstrip("\\")
    if not text:
        return "No project"
    return text.split("\\")[-1] or "No project"


def _span(rows: list) -> tuple[str, str]:
    mod = _module("proj_span")
    span = getattr(mod, "span", None) if mod is not None else None
    if callable(span):
        try:
            found = span(rows)
        except Exception:
            found = None
        if isinstance(found, tuple) and len(found) == 2:
            return str(found[0]), str(found[1])
    stamps = [_stamp(hit.get("updated")) for hit in rows if isinstance(hit, dict)]
    stamps = [item for item in stamps if item is not None]
    if not stamps:
        return _EM, _EM
    return min(stamps).date().isoformat(), max(stamps).date().isoformat()


def _stamp(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    if number > _MS_CUT:
        number = number / 1000.0
    try:
        return datetime.fromtimestamp(number)
    except (OverflowError, OSError, ValueError):
        return None


def _mount(name: str, parent, desk) -> bool:
    mod = _module(name)
    build = getattr(mod, "build", None) if mod is not None else None
    if not callable(build):
        return False
    before = _child_count(parent)
    try:
        build(parent, desk)
    except Exception:
        return _child_count(parent) > before
    return _child_count(parent) > before


def _call_refresh(name: str, desk, hits) -> bool:
    mod = _module(name)
    refresh = getattr(mod, "refresh", None) if mod is not None else None
    if not callable(refresh):
        return False
    try:
        refresh(desk, hits)
    except Exception:
        return False
    return True


def _child_count(parent) -> int:
    try:
        return len(parent.winfo_children())
    except Exception:
        return 0


def _module(name: str):
    if name not in _PIECES and not name.startswith("proj_"):
        return None
    try:
        return importlib.import_module(name)
    except ImportError:
        folder = str(Path(__file__).resolve().parent)
        if folder not in sys.path:
            sys.path.insert(0, folder)
        try:
            return importlib.import_module(name)
        except ImportError:
            return None


def _tk(desk):
    module = getattr(desk, "tk", None)
    if getattr(module, "Frame", None) is not None and getattr(module, "Label", None) is not None:
        return module
    import tkinter as tk
    return tk
