"""The large ledger sheet. One window. Session, calendar, and projects sit inside it.

No second page, no extra Toplevel, no browser, and no port.
"""

from __future__ import annotations

import importlib
import sys
import weakref
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

BG = "#07080A"
CARD = "#12151C"
INK = "#E8ECF4"
QUIET = "#6B7386"
ACCENT = "#7C9CFF"
LINE = "#2A3140"

_FONT = ("Segoe UI", -15)
_FONT_SMALL = ("Segoe UI", -13)

_PARTS = (
    "ledger_table",
    "ledger_glance",
    "ledger_session",
    "ledger_calendar",
    "ledger_projects",
)

_APP_INK = {
    "claude": "#C4B5FD",
    "claude_desktop": "#C4B5FD",
    "codex": "#86EFAC",
    "grok": "#93C5FD",
    "gemini": "#FDE68A",
    "antigravity": "#FDBA74",
    "antigravity-ide": "#FDBA74",
    "antigravity-cli": "#FDBA74",
    "agy": "#FDBA74",
    "cursor": "#A5B4FC",
    "agent": "#A5B4FC",
    "pi": "#F0ABFC",
    "hermes": "#F9A8D4",
    "openwork": "#F0ABFC",
    "cowork": "#F0ABFC",
}
_EXTRA_INK = ("#C4B5FD", "#93C5FD", "#FDE68A", "#FDBA74", "#F0ABFC", "#A5B4FC", "#F9A8D4", "#67E8F9")

_COLUMNS = (
    ("app", "Source app", 140),
    ("time", "Time last active", 150),
    ("title", "Session title", 360),
    ("size", "Size / tokens", 130),
    ("topics", "Session topics", 200),
)


class _Owned:
    def __init__(self) -> None:
        self.tree = None
        self.glance = None
        self.group_buttons: dict = {}


_owned = weakref.WeakKeyDictionary()


def _state(desk) -> _Owned:
    try:
        found = _owned.get(desk)
    except TypeError:
        found = None
    if found is None:
        found = _Owned()
        try:
            _owned[desk] = found
        except TypeError:
            pass
    return found


def _tk(desk):
    tk = getattr(desk, "tk", None)
    if tk is not None and hasattr(tk, "Frame"):
        return tk
    import tkinter as tk
    return tk


def _ttk(desk):
    ttk = getattr(desk, "ttk", None)
    if ttk is not None and hasattr(ttk, "Treeview"):
        return ttk
    from tkinter import ttk
    return ttk


def _module(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _clear(parent) -> None:
    try:
        children = list(parent.winfo_children())
    except Exception:
        return
    for child in children:
        try:
            child.destroy()
        except Exception:
            pass


def app_ink(name: str) -> str:
    key = str(name or "").strip().lower()
    try:
        from ledger_common import vendor_color
        color = vendor_color(key)
        if color:
            return color
    except Exception:
        pass
    if key in _APP_INK:
        return _APP_INK[key]
    if not key:
        return "#A7B0C3"
    return _EXTRA_INK[sum(ord(ch) for ch in key) % len(_EXTRA_INK)]


def _button(tk, parent, text, command, on=False):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=ACCENT if on else CARD,
        fg=BG if on else INK,
        activebackground=ACCENT,
        activeforeground=BG,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=LINE,
        highlightcolor=ACCENT,
        font=_FONT_SMALL,
        padx=8,
        pady=4,
        cursor="hand2",
    )


def _invoke(desk, name: str):
    def run() -> None:
        fn = getattr(desk, name, None)
        if callable(fn):
            fn()
    return run


def _ensure_query(desk, tk):
    var = getattr(desk, "query", None)
    if var is None or not hasattr(var, "get"):
        desk.query = tk.StringVar(value="" if var is None else str(var))
    return desk.query


def _kick(desk) -> None:
    refresh(desk, getattr(desk, "hits", []) or [])


def _set_group(desk, mode: str) -> None:
    current = str(getattr(desk, "ledger_group", "") or "")
    desk.ledger_group = "flat" if current == mode else mode
    owned = _state(desk)
    for key, button in owned.group_buttons.items():
        on = key == desk.ledger_group
        try:
            button.configure(bg=ACCENT if on else CARD, fg=BG if on else INK)
        except Exception:
            pass
    _kick(desk)


def _create_summaries(desk) -> None:
    hook = getattr(desk, "_on_summaries", None)
    if callable(hook):
        hook()
        return
    say = getattr(desk, "_say", None)
    if callable(say):
        say(
            "Create summaries uses the title and project already on the row. A model summary is not part of this pass.",
            "warn",
        )


def _print_view(desk) -> None:
    hook = getattr(desk, "_on_print", None)
    if callable(hook):
        hook()
        return
    lines = ["Source app\tTime last active\tSession title\tSize / tokens\tSession topics"]
    for hit in _visible(desk, getattr(desk, "hits", ()) or ()):
        lines.append("\t".join((
            _app_name(hit),
            _when(hit),
            _title(hit),
            _size_text(hit),
            _topics(hit),
        )))
    root = getattr(desk, "root", None)
    if root is not None:
        try:
            root.clipboard_clear()
            root.clipboard_append("\n".join(lines))
        except Exception:
            pass
    say = getattr(desk, "_say", None)
    if callable(say):
        say("Printable view is on the clipboard.")


def _post_menu(menu, button) -> None:
    try:
        menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())
    finally:
        try:
            menu.grab_release()
        except Exception:
            pass


def _draw_toolbar(toolbar, desk) -> None:
    tk = _tk(desk)
    toolbar.configure(bg=CARD)
    tk.Label(toolbar, text="Session type", fg=QUIET, bg=CARD, font=_FONT_SMALL).pack(
        side="left", padx=(12, 6), pady=8,
    )
    for mark in ("CLI", "TUI", "Chat"):
        tk.Label(
            toolbar, text=mark, fg=BG, bg=ACCENT, font=_FONT_SMALL, padx=8, pady=4,
        ).pack(side="left", padx=2, pady=8)
    _button(tk, toolbar, "Create summaries", lambda: _create_summaries(desk)).pack(
        side="left", padx=(12, 4), pady=8,
    )
    owned = _state(desk)
    for mode, label in (
        ("maker", "Group by maker"),
        ("project", "Group by project"),
        ("topic", "Group by topic"),
    ):
        button = _button(tk, toolbar, label, lambda m=mode: _set_group(desk, m))
        button.pack(side="left", padx=2, pady=8)
        owned.group_buttons[mode] = button
    tk.Entry(
        toolbar,
        textvariable=_ensure_query(desk, tk),
        bg=BG,
        fg=INK,
        insertbackground=INK,
        relief="flat",
        width=28,
        font=_FONT,
        highlightthickness=1,
        highlightbackground=LINE,
        highlightcolor=ACCENT,
    ).pack(side="left", padx=(12, 4), pady=8, ipady=3)
    _button(tk, toolbar, "Print", lambda: _print_view(desk)).pack(side="left", padx=2, pady=8)
    menu = tk.Menu(
        toolbar, tearoff=0, bg=CARD, fg=INK,
        activebackground=ACCENT, activeforeground=BG,
        relief="flat", bd=0, font=_FONT_SMALL,
    )
    menu.add_command(label="Refresh", command=_invoke(desk, "_load_all"))
    menu.add_command(label="Preview", command=_invoke(desk, "_on_preview"))
    menu.add_command(label="Import", command=_invoke(desk, "_on_import"))
    menu.add_command(label="Export", command=_invoke(desk, "_on_export"))
    menu.add_command(label="Index", command=_invoke(desk, "_on_index"))
    menu.add_command(label="Formats", command=_invoke(desk, "_on_formats"))
    menu.add_command(label="Check recovery", command=_invoke(desk, "_on_recover"))
    menu.add_command(label="Restore", command=_invoke(desk, "_on_restore"))
    menu.add_command(label="Anonymize", command=_invoke(desk, "_on_anonymize"))
    menu.add_command(label="Check strip", command=_invoke(desk, "_on_strip_dry"))
    menu.add_command(label="Write strip", command=_invoke(desk, "_on_strip"))
    menu.add_command(label="Quit", command=_invoke(desk, "_on_quit"))
    more = _button(tk, toolbar, "More", lambda: None)
    more.configure(command=lambda: _post_menu(menu, more))
    more.pack(side="left", padx=(2, 12), pady=8)


def _draw_table(parent, desk):
    tk = _tk(desk)
    ttk = _ttk(desk)
    parent.configure(bg=BG)
    parent.rowconfigure(0, weight=1)
    parent.columnconfigure(0, weight=1)
    master = getattr(desk, "root", parent)
    style = ttk.Style(master)
    style.configure(
        "Ledger.Treeview",
        background=CARD,
        fieldbackground=CARD,
        foreground=INK,
        rowheight=32,
        borderwidth=0,
        font=_FONT,
    )
    style.configure(
        "Ledger.Treeview.Heading",
        background=BG,
        foreground=QUIET,
        relief="flat",
        font=_FONT_SMALL,
    )
    style.map("Ledger.Treeview", background=[("selected", "#1E2430")])
    tree = ttk.Treeview(
        parent,
        columns=tuple(key for key, _text, _width in _COLUMNS),
        show="headings",
        style="Ledger.Treeview",
    )
    for key, text, width in _COLUMNS:
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    tree.tag_configure("group", foreground=QUIET)
    tree._ledger_tags = {"group"}
    tree.grid(row=0, column=0, sticky="nsew")
    bar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    bar.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=bar.set)
    tree.bind("<<TreeviewSelect>>", lambda _event: _on_select(desk))
    return tree


def _draw_glance(parent, desk):
    tk = _tk(desk)
    parent.configure(bg=CARD)
    tk.Label(
        parent, text="At a glance", fg=INK, bg=CARD, font=_FONT, anchor="w",
    ).pack(fill="x", padx=12, pady=(12, 4))
    pane = tk.Text(
        parent, bg=CARD, fg=QUIET, relief="flat", wrap="word",
        font=_FONT_SMALL, highlightthickness=0, padx=2, pady=2,
    )
    pane.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    pane.insert("1.0", "7 days\n\nweek\n\nmonthly\n")
    pane.configure(state="disabled")
    return pane


def _caption(parent, desk, text: str):
    tk = _tk(desk)
    parent.configure(bg=BG)
    label = tk.Label(
        parent, text=text, fg=INK, bg=CARD, anchor="w", font=_FONT, padx=12, pady=8,
    )
    label.pack(fill="x", padx=8, pady=4)
    return label


def _host(frame) -> None:
    try:
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
    except Exception:
        pass


def _use(name: str, parent, desk):
    """Return (used_sibling, built_widget). On failure the parent is empty."""
    mod = _module(name)
    build = getattr(mod, "build", None) if mod is not None else None
    if not callable(build):
        return False, None
    try:
        return True, build(parent, desk)
    except Exception as exc:
        errors = getattr(desk, "_ledger_errors", None)
        if not isinstance(errors, list):
            errors = []
            desk._ledger_errors = errors
        errors.append(f"{name}: {type(exc).__name__}: {exc}")
        _clear(parent)
        return False, None


def mount(desk, stage):
    """The landscape ledger is the window. Table View is only the center pane."""
    import ledger_master
    return ledger_master.mount(desk, stage)


def _mount_stacked(desk, stage):
    """Previous stacked sheet. Not used."""
    tk = _tk(desk)
    if not getattr(desk, "ledger_group", None):
        desk.ledger_group = "flat"
    _ensure_query(desk, tk)
    desk.ledger_refresh = lambda *args, **kwargs: _kick(desk)

    try:
        stage.configure(bg=BG)
    except Exception:
        pass
    stage.columnconfigure(0, weight=1)
    stage.rowconfigure(0, weight=0)
    stage.rowconfigure(1, weight=3)
    stage.rowconfigure(2, weight=2)
    stage.rowconfigure(3, weight=2)

    toolbar = tk.Frame(stage, bg=CARD)
    toolbar.grid(row=0, column=0, sticky="ew")
    used, _built = _use("ledger_toolbar", toolbar, desk)
    if not used:
        _draw_toolbar(toolbar, desk)

    # Glance stays about 220px. The project pane below is not locked to that width.
    body = tk.Frame(stage, bg=BG)
    body.grid(row=1, column=0, sticky="nsew")
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, minsize=220, weight=0)
    body.rowconfigure(0, weight=1)
    left = tk.Frame(body, bg=BG)
    left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
    right = tk.Frame(body, bg=CARD, width=220)
    right.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
    right.grid_propagate(False)
    _host(left)
    _host(right)

    owned = _state(desk)
    used, built = _use("ledger_table", left, desk)
    if used:
        desk.ledger_table = built if built is not None else getattr(desk, "ledger_tree", left)
    else:
        owned.tree = _draw_table(left, desk)
        desk.ledger_table = owned.tree

    used, built = _use("ledger_glance", right, desk)
    if used:
        if built is not None:
            desk.ledger_glance = built
        elif getattr(desk, "ledger_glance", None) is None:
            desk.ledger_glance = right
    else:
        owned.glance = _draw_glance(right, desk)
        desk.ledger_glance = owned.glance

    band = tk.Frame(stage, bg=BG)
    band.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
    _host(band)
    used, built = _use("ledger_session", band, desk)
    if used:
        desk.ledger_session = built if built is not None else band
    else:
        desk.ledger_session = _caption(band, desk, "Session")

    lower = tk.Frame(stage, bg=BG)
    lower.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
    lower.columnconfigure(0, weight=1)
    lower.columnconfigure(1, weight=1)
    lower.rowconfigure(0, weight=1)
    calendar = tk.Frame(lower, bg=BG)
    calendar.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    projects = tk.Frame(lower, bg=BG)
    projects.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
    _host(calendar)
    _host(projects)

    used, built = _use("ledger_calendar", calendar, desk)
    if used:
        desk.ledger_calendar = built if built is not None else calendar
    else:
        desk.ledger_calendar = _caption(calendar, desk, "Calendar")

    used, built = _use("ledger_projects", projects, desk)
    if used:
        desk.ledger_projects = built if built is not None else projects
    else:
        desk.ledger_projects = _caption(projects, desk, "Projects")

    desk.ledger_mounted = True
    return stage


def refresh(desk, hits) -> None:
    """Fill the ledger columns. The center pane is the Table View."""
    import ledger_master
    return ledger_master.refresh(desk, hits)


def _refresh_stacked(desk, hits) -> None:
    """Previous pane refresh. Not used."""
    if getattr(desk, "_ledger_refreshing", False):
        return
    desk._ledger_refreshing = True
    try:
        for name in _PARTS:
            mod = _module(name)
            fn = getattr(mod, "refresh", None) if mod is not None else None
            if not callable(fn):
                continue
            try:
                fn(desk, hits)
            except Exception as exc:
                errors = getattr(desk, "_ledger_errors", None)
                if isinstance(errors, list):
                    errors.append(f"{name}.refresh: {type(exc).__name__}: {exc}")
        _paint(desk, hits)
    finally:
        desk._ledger_refreshing = False


def _rows(hits) -> list:
    if not hits:
        return []
    try:
        return [hit for hit in hits if isinstance(hit, dict)]
    except TypeError:
        return []


def _stamp(hit: dict):
    for key in ("updated", "last_activity", "started"):
        if hit.get(key) not in (None, ""):
            return hit.get(key)
    return None


def _when(hit: dict) -> str:
    try:
        from ledger_common import age_text
        return age_text(_stamp(hit))
    except Exception:
        pass
    from datetime import datetime
    moment = _dt(_stamp(hit))
    if moment is None:
        return "—"
    return moment.strftime("%Y-%m-%d %H:%M")


def _dt(stamp):
    from datetime import datetime
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return None
    ms = n if n > 100_000_000_000 else n * 1000
    try:
        return datetime.fromtimestamp(ms / 1000)
    except (OSError, OverflowError, ValueError):
        return None


def _title(hit: dict) -> str:
    try:
        from ledger_common import title_of
        return title_of(hit)
    except Exception:
        pass
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "")


def _app_name(hit: dict) -> str:
    return str(hit.get("harness") or hit.get("vendor") or "other")


def _project(hit: dict) -> str:
    try:
        from ledger_common import project_of
        named = project_of(hit)
        if named:
            return named
    except Exception:
        pass
    if hit.get("legal"):
        return ""
    named = hit.get("project")
    if isinstance(named, str) and named.strip():
        return named.strip()
    cwd = str(hit.get("cwd") or hit.get("location") or "").replace("/", "\\").rstrip("\\")
    if not cwd:
        return ""
    return cwd.split("\\")[-1]


def _topics(hit: dict) -> str:
    if hit.get("legal"):
        return "—"
    raw = hit.get("topics")
    if raw in (None, ""):
        raw = hit.get("topic")
    if raw in (None, ""):
        raw = hit.get("tags")
    if isinstance(raw, (list, tuple)):
        text = ", ".join(str(item) for item in raw if item)
        return text or (_project(hit) or "—")
    text = str(raw or "").strip()
    return text or (_project(hit) or "—")


def _size_text(hit: dict) -> str:
    if hit.get("legal"):
        return "—"
    parts = []
    size = hit.get("bytes")
    if isinstance(size, int) and not isinstance(size, bool):
        parts.append(f"{max(1, size // 1024)} KB" if size >= 1024 else f"{size} B")
    tokens = hit.get("tokens")
    if isinstance(tokens, (int, float)) and not isinstance(tokens, bool):
        parts.append(f"{int(tokens)} tok")
    return "  ".join(parts) if parts else "—"


def _topic_key(hit: dict) -> str:
    text = _topics(hit)
    if text == "—":
        return "No topic"
    return text.split(",")[0].strip() or "No topic"


def _group_key(mode: str, hit: dict) -> str:
    if mode == "maker":
        return _app_name(hit)
    if mode == "project":
        return _project(hit) or "No project"
    if mode == "topic":
        return _topic_key(hit)
    return ""


def _haystack(hit: dict) -> str:
    parts = [
        hit.get("title"), hit.get("harness"), hit.get("vendor"),
        hit.get("id"), hit.get("vendor_id"), hit.get("cwd"),
        hit.get("path"), hit.get("project"), hit.get("model"),
    ]
    for key in ("topic", "topics", "tags"):
        raw = hit.get(key)
        if isinstance(raw, (list, tuple)):
            parts.extend(raw)
        else:
            parts.append(raw)
    return " ".join(str(part) for part in parts if part).lower()


def _query_text(desk) -> str:
    var = getattr(desk, "query", None)
    if var is None:
        return ""
    try:
        return str(var.get()).strip().lower()
    except Exception:
        return ""


def _visible(desk, hits) -> list:
    query = _query_text(desk)
    rows = _rows(hits)
    if not query:
        return rows
    return [hit for hit in rows if query in _haystack(hit)]


def _tag(tree, app: str) -> str:
    tag = str(app or "other").strip().lower() or "other"
    known = getattr(tree, "_ledger_tags", None)
    if known is None:
        known = set()
        tree._ledger_tags = known
    if tag not in known:
        tree.tag_configure(tag, foreground=app_ink(tag))
        known.add(tag)
    return tag


def _paint(desk, hits) -> None:
    owned = _state(desk)
    if owned.tree is None and owned.glance is None:
        return
    rows = _visible(desk, hits)
    mode = str(getattr(desk, "ledger_group", "") or "")
    if mode in ("maker", "project", "topic"):
        rows = sorted(rows, key=lambda hit: (_group_key(mode, hit).lower(), _title(hit).lower()))
    else:
        mode = ""
    if owned.tree is not None:
        _paint_table(owned.tree, rows, mode)
    if owned.glance is not None:
        _paint_glance(owned.glance, rows)


def _paint_table(tree, rows: list, mode: str) -> None:
    tree.delete(*tree.get_children())
    tree._ledger_iids = {}
    last = None
    for hit in rows:
        key = _group_key(mode, hit)
        if mode and key != last:
            last = key
            tree.insert("", "end", values=("", "", key, "", ""), tags=("group",))
        app = _app_name(hit)
        iid = tree.insert(
            "",
            "end",
            values=(app, _when(hit), _title(hit), _size_text(hit), _topics(hit)),
            tags=(_tag(tree, app),),
        )
        tree._ledger_iids[iid] = hit


def _on_select(desk) -> None:
    owned = _state(desk)
    tree = owned.tree
    if tree is None:
        return
    selected = tree.selection()
    if not selected:
        return
    hit = getattr(tree, "_ledger_iids", {}).get(selected[0])
    if not isinstance(hit, dict):
        return
    ident = hit.get("id")
    rows = getattr(desk, "hits", ()) or ()
    for index, row in enumerate(rows):
        if isinstance(row, dict) and row.get("id") == ident and ident is not None:
            desk.selected_index = index
            break
    else:
        desk.selected_index = None
    mod = _module("ledger_session")
    fill = getattr(mod, "fill", None) if mod is not None else None
    if callable(fill):
        try:
            fill(desk, hit)
        except Exception:
            pass


def _paint_glance(pane, rows: list) -> None:
    from datetime import datetime, timedelta
    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    seven_start = now - timedelta(days=7)
    seven = []
    week = 0
    month = 0
    for hit in rows:
        moment = _dt(_stamp(hit))
        if moment is None:
            continue
        if moment >= seven_start:
            seven.append(hit)
        if moment >= week_start:
            week += 1
        if moment >= month_start:
            month += 1
    pane.configure(state="normal")
    pane.delete("1.0", "end")
    pane.insert("end", "7 days\n")
    if not seven:
        pane.insert("end", "None\n")
    for hit in seven[:8]:
        app = _app_name(hit)
        pane.tag_configure(app, foreground=app_ink(app))
        pane.insert("end", f"{_title(hit)}\n", (app,))
    pane.insert("end", "\nweek\n")
    pane.insert("end", f"{week} sessions\n")
    pane.insert("end", "\nmonthly\n")
    pane.insert("end", f"{month} sessions\n")
    pane.configure(state="disabled")
