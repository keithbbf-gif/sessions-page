"""Center table of the one ledger window. Not its own page.

Stdlib and tkinter only. Reads the hits it is given and does not invent sessions.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk

_BG = "#12151C"
_FG = "#E8ECF4"
_HEAD = "#6B7386"
_QUIET = "#A7B0C3"
_SELECT = "#1E2430"
_EM = "\u2014"
_SUB = "  \u00b7  sub sessions"
_MS_CUT = 100_000_000_000

_VCOLOR = {
    "claude": "#C4B5FD",
    "claude_desktop": "#C4B5FD",
    "codex": "#86EFAC",
    "grok": "#93C5FD",
    "gemini": "#FDE68A",
    "antigravity": "#FDBA74",
    "antigravity-ide": "#FDBA74",
    "antigravity-cli": "#FDBA74",
    "agy": "#FDBA74",
}
_ANTIGRAVITY = frozenset({
    "antigravity", "antigravity-ide", "antigravity-cli", "agy",
})


def _load_common():
    try:
        import ledger_common
        return ledger_common
    except ImportError:
        pass
    path = Path(__file__).resolve().with_name("ledger_common.py")
    if not path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("ledger_common", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_common = _load_common()


def _use(name: str):
    if _common is None:
        return None
    fn = getattr(_common, name, None)
    return fn if callable(fn) else None


def vendor_color(harness: str) -> str:
    fn = _use("vendor_color")
    if fn is not None:
        return fn(harness)
    return _VCOLOR.get(str(harness or "").lower(), _QUIET)


def _harness(hit: dict) -> str:
    value = hit.get("harness")
    if value is None or str(value).strip() == "":
        value = hit.get("vendor")
    return str(value or "").strip()


def title_of(hit: dict) -> str:
    fn = _use("title_of")
    if fn is not None:
        return str(fn(hit))
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "")


def project_of(hit: dict) -> str:
    fn = _use("project_of")
    if fn is not None:
        text = fn(hit)
        if isinstance(text, str):
            return text
    if hit.get("legal"):
        return ""
    cwd = str(hit.get("cwd") or "").replace("/", "\\").rstrip("\\")
    if not cwd:
        return ""
    return cwd.split("\\")[-1]


def _epoch_seconds(stamp) -> float | None:
    if isinstance(stamp, datetime):
        try:
            return stamp.timestamp()
        except (OSError, OverflowError, ValueError):
            return None
    if stamp is None or isinstance(stamp, bool):
        return None
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return None
    if n != n or n < 0 or n == float("inf"):
        return None
    if n > _MS_CUT:
        n = n / 1000.0
    return n


def _age_text(stamp) -> str:
    seconds = _epoch_seconds(stamp)
    if seconds is None:
        return _EM
    try:
        mins = max(0, int((datetime.now().timestamp() - seconds) // 60))
    except (OSError, OverflowError, ValueError):
        return _EM
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    if hours < 24:
        return f"{hours}hr" if hours < 10 else f"{hours}hrs"
    days = hours // 24
    if days < 14:
        return f"{days} day" if days == 1 else f"{days} days"
    weeks = days // 7
    if weeks < 8:
        return f"{weeks} wks"
    months = max(1, days // 30)
    return f"{months} month" if months == 1 else f"{months} months"


def age_text(stamp) -> str:
    fn = _use("age_text")
    if fn is not None:
        return str(fn(stamp))
    return _age_text(stamp)


def source_label(hit: dict) -> str:
    fn = _use("source_label")
    if fn is not None:
        return str(fn(hit))
    raw = _harness(hit)
    key = raw.lower()
    if key == "grok":
        return "Grok.exe"
    if key in _ANTIGRAVITY:
        return "Antigravity.exe"
    return raw


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _title_cell(hit: dict) -> str:
    if hit.get("legal"):
        return "Legal session"
    base = _one_line(title_of(hit))
    if not base or base == "Legal session":
        return "Legal session" if base == "Legal session" else _SUB.strip()
    return base + _SUB


def _size_cell(hit: dict) -> str:
    n = hit.get("bytes")
    if isinstance(n, bool) or n is None:
        return _EM
    if isinstance(n, (int, float)):
        if n != n or n < 0 or n == float("inf"):
            return _EM
        return str(int(n))
    text = str(n).strip()
    return text or _EM


def _topic_cell(hit: dict) -> str:
    # Legal rows name the session and do not show a path.
    if hit.get("legal"):
        return _EM
    name = project_of(hit).strip()
    return name or _EM


def _real_topic(hit: dict) -> str:
    if hit.get("legal"):
        return ""
    for key in ("topic", "topics"):
        raw = hit.get(key)
        if isinstance(raw, str) and raw.strip():
            return _one_line(raw)
        if isinstance(raw, (list, tuple)):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    return _one_line(item)
    return ""


def _mode(desk) -> str:
    mode = str(getattr(desk, "ledger_group", "flat") or "flat").strip().lower()
    if mode in ("maker", "project", "topic"):
        return mode
    return "flat"


def _group_label(hit: dict, mode: str) -> str:
    if mode == "maker":
        return _harness(hit) or "other"
    if mode == "project":
        return project_of(hit) or "No project"
    # Same project leaf until the hit carries a real topic.
    return _real_topic(hit) or project_of(hit) or "No topic"


def _tag(tree, harness: str) -> str:
    name = str(harness or "").lower()
    tag = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name) or "other"
    tree.tag_configure(tag, foreground=vendor_color(name))
    return tag


def _data_iid(hit: dict, seen: set[str]) -> str:
    ident = str(hit.get("id") or "")
    safe = "".join(ch if ch not in " \t\r\n\\{}" else "_" for ch in ident)
    base = "h-" + safe if safe else ""
    if base and base not in seen:
        seen.add(base)
        return base
    n = 0
    while True:
        iid = f"h-{safe}#{n}" if safe else f"h-row-{n}"
        if iid not in seen:
            seen.add(iid)
            return iid
        n += 1


def _index_of(rows, hit: dict, iid: str) -> int | None:
    for index, row in enumerate(rows):
        if row is hit:
            return index
    ident = hit.get("id")
    if ident is None or str(ident) == "":
        if iid.startswith("h-") and "#" not in iid and not iid.startswith("h-row-"):
            ident = iid[2:]
        else:
            return None
    want = str(ident)
    for index, row in enumerate(rows):
        if isinstance(row, dict) and str(row.get("id") or "") == want:
            return index
    return None


def _on_select(desk) -> None:
    if getattr(_on_select, "busy", False):
        return
    tree = getattr(desk, "ledger_tree", None)
    if tree is None:
        return
    chosen = tree.selection()
    if not chosen:
        return
    iid = str(chosen[0])
    # Group headers are not in this map, so they never call _select.
    hit = getattr(tree, "_ledger_rows", {}).get(iid)
    if not isinstance(hit, dict):
        return
    rows = getattr(desk, "hits", None)
    if not isinstance(rows, (list, tuple)):
        return
    index = _index_of(rows, hit, iid)
    if index is None:
        return
    select = getattr(desk, "_select", None)
    if callable(select):
        select(index)
    show = getattr(desk, "show_ledger_body", None)
    if callable(show):
        show("session")


_on_select.busy = False


def _style(parent) -> None:
    style = ttk.Style(parent)
    style.configure(
        "Ledger.Treeview",
        background=_BG,
        fieldbackground=_BG,
        foreground=_FG,
        borderwidth=0,
        relief="flat",
        rowheight=32,
    )
    style.configure(
        "Ledger.Treeview.Heading",
        background=_BG,
        foreground=_HEAD,
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Ledger.Treeview",
        background=[("selected", _SELECT)],
        foreground=[("selected", _FG)],
    )
    style.configure(
        "Ledger.Vertical.TScrollbar",
        background=_SELECT,
        troughcolor=_BG,
        bordercolor=_BG,
        arrowcolor=_HEAD,
    )


def _drop_previous(desk) -> None:
    old = getattr(desk, "ledger_tree", None)
    if old is None:
        return
    bar = getattr(old, "_scroll", None)
    try:
        old.destroy()
    except tk.TclError:
        pass
    if bar is not None:
        try:
            bar.destroy()
        except tk.TclError:
            pass


def build(parent, desk) -> None:
    try:
        parent.configure(bg=_BG)
    except tk.TclError:
        pass
    _style(parent)
    _drop_previous(desk)
    tree = ttk.Treeview(
        parent,
        columns=("app", "time", "title", "tokens", "topic"),
        show="headings",
        style="Ledger.Treeview",
        selectmode="browse",
    )
    headers = (
        ("app", "Source app", 160),
        ("time", "Time last active", 130),
        ("title", "Session title", 360),
        ("tokens", "Size / tokens", 120),
        ("topic", "Session topics", 180),
    )
    for key, text, width in headers:
        tree.heading(key, text=text, anchor="w")
        tree.column(key, width=width, minwidth=48, anchor="w", stretch=(key == "title"))
    tree.tag_configure("group", foreground=_QUIET)
    tree.tag_configure("other", foreground=vendor_color(""))
    for name in _VCOLOR:
        tree.tag_configure(name, foreground=vendor_color(name))
    scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview, style="Ledger.Vertical.TScrollbar")
    tree.configure(yscrollcommand=scroll.set)
    tree._scroll = scroll
    tree._ledger_rows = {}
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    tree.bind("<<TreeviewSelect>>", lambda _event: _on_select(desk))
    desk.ledger_tree = tree


def _values(hit: dict) -> tuple[str, str, str, str, str]:
    return (
        source_label(hit),
        age_text(hit.get("updated")),
        _title_cell(hit),
        _size_cell(hit),
        _topic_cell(hit),
    )


def _fill(desk, tree, hits) -> None:
    tree._ledger_rows = {}
    kids = tree.get_children("")
    if kids:
        tree.delete(*kids)
    mode = _mode(desk)
    rows = [hit for hit in (hits or ()) if isinstance(hit, dict)]
    if mode != "flat":
        rows = sorted(rows, key=lambda hit: _group_label(hit, mode).casefold())
    seen: set[str] = set()
    last = None
    group_n = 0
    for hit in rows:
        if mode != "flat":
            label = _group_label(hit, mode)
            token = label.casefold()
            if token != last:
                last = token
                tree.insert(
                    "", "end", iid=f"g-{group_n}",
                    values=(label, "", "", "", ""),
                    tags=("group",),
                )
                group_n += 1
        iid = _data_iid(hit, seen)
        tree.insert("", "end", iid=iid, values=_values(hit), tags=(_tag(tree, _harness(hit)),))
        tree._ledger_rows[iid] = hit


def refresh(desk, hits) -> None:
    tree = getattr(desk, "ledger_tree", None)
    if tree is None:
        return
    _on_select.busy = True
    try:
        _fill(desk, tree, hits)
    finally:
        _on_select.busy = False
