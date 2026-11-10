"""Lower-left calendar region of the one ledger window. Not a page.

No Toplevel, no browser, and no port. Sibling pieces draw the search
bar, the month, the day counts, the plans, and the bottom lines when
they import. If one of them is missing, this module draws the month
and the summary line itself.
"""
from __future__ import annotations

import calendar
import importlib.util
import sys
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

_BG = "#07080A"
_CELL = "#12151C"
_INK = "#E8ECF4"
_QUIET = "#A7B0C3"
_FONT = ("Segoe UI", -15)
_FONT_TITLE = ("Segoe UI", 18, "bold")
_DAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
_ORDER = (
    "cal_month",
    "cal_search",
    "cal_days",
    "cal_plans",
    "cal_loose",
    "cal_priorities",
)
_HOST = {
    "cal_month": "month",
    "cal_search": "search",
    "cal_days": "month",
    "cal_plans": "plans",
    "cal_loose": "foot",
    "cal_priorities": "foot",
}
_FOOT = "Summary / Loose ends / Next priorities"
_NEXT = "crashed first, then the oldest unfinished."


def _load(name: str):
    """Import one sibling. Missing or broken modules return None."""
    existing = sys.modules.get(name)
    if existing is not None:
        mod = existing
    else:
        path = Path(__file__).resolve().parent / f"{name}.py"
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            sys.modules.pop(name, None)
            return None
    if not callable(getattr(mod, "build", None)):
        return None
    return mod


def _tk(desk):
    factory = getattr(desk, "tk", None)
    if factory is not None and hasattr(factory, "Frame") and hasattr(factory, "Label"):
        return factory
    return tk


def _rows(hits) -> list:
    if isinstance(hits, (list, tuple)):
        return list(hits)
    return []


def _query(desk) -> str:
    raw = getattr(desk, "ledger_cal_q", "")
    if raw is None:
        return ""
    get = getattr(raw, "get", None)
    if callable(get):
        try:
            raw = get()
        except tk.TclError:
            return ""
    return str(raw or "").strip().casefold()


def _title(hit: dict) -> str:
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "")


def _project(hit: dict) -> str:
    if hit.get("legal"):
        return ""
    parts: list[str] = []
    named = hit.get("project")
    if isinstance(named, str) and named.strip():
        parts.append(named.strip())
    cwd = str(hit.get("cwd") or "").replace("/", "\\").rstrip("\\")
    if cwd:
        leaf = cwd.split("\\")[-1]
        if leaf and leaf not in parts:
            parts.append(leaf)
    return " ".join(parts)


def _when(hit: dict) -> datetime | None:
    stamp = hit.get("updated")
    if stamp is None:
        stamp = hit.get("last_activity")
    if stamp is None:
        stamp = hit.get("started")
    if isinstance(stamp, bool) or stamp is None:
        return None
    if isinstance(stamp, datetime):
        return stamp
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return None
    ms = n if n > 100_000_000_000 else n * 1000
    try:
        return datetime.fromtimestamp(ms / 1000)
    except (OSError, OverflowError, ValueError):
        return None


def _matches(hit: dict, term: str) -> bool:
    if not term:
        return True
    return term in _title(hit).casefold() or term in _project(hit).casefold()


def _counts(hits, year: int, month: int, term: str) -> dict[int, int]:
    counts: dict[int, int] = {}
    for hit in _rows(hits):
        if not isinstance(hit, dict) or not _matches(hit, term):
            continue
        when = _when(hit)
        if when is None or when.year != year or when.month != month:
            continue
        counts[when.day] = counts.get(when.day, 0) + 1
    return counts


def _idle(hits) -> int:
    found = 0
    for hit in _rows(hits):
        if isinstance(hit, dict) and str(hit.get("status") or "").strip().lower() == "idle":
            found += 1
    return found


def _paint_grid(desk, grid, hits) -> None:
    try:
        if not grid.winfo_exists():
            return
    except tk.TclError:
        return
    for child in list(grid.winfo_children()):
        child.destroy()
    now = datetime.now()
    weeks = calendar.Calendar(firstweekday=calendar.SUNDAY).monthdayscalendar(now.year, now.month)
    counts = _counts(hits, now.year, now.month, _query(desk))
    for col in range(7):
        grid.columnconfigure(col, weight=1, uniform="cal")
    for col, name in enumerate(_DAYS):
        tk.Label(grid, text=name, fg=_INK, bg=_BG, font=_FONT).grid(
            row=0, column=col, padx=2, pady=(0, 4),
        )
    for row, week in enumerate(weeks, start=1):
        grid.rowconfigure(row, weight=1, uniform="week")
        for col, day in enumerate(week):
            text = ""
            if day:
                text = f"{day}\n{counts[day]}" if day in counts else str(day)
            tk.Label(
                grid,
                text=text,
                fg=_INK,
                bg=_CELL,
                anchor="nw",
                justify="left",
                font=_FONT,
                width=8,
                height=3,
                padx=6,
                pady=4,
            ).grid(row=row, column=col, padx=2, pady=2, sticky="nsew")


def _paint_plans(labels) -> None:
    today = datetime.now().date()
    for index, label in enumerate(labels, start=1):
        day = today + timedelta(days=index)
        try:
            label.configure(text=f"Plans  {day.strftime('%a %m/%d')}")
        except tk.TclError:
            return


def _foot_text(hits) -> str:
    rows = _rows(hits)
    return f"Summary {len(rows)} / Loose ends {_idle(rows)} / Next priorities {_NEXT}"


def _paint_foot(label, hits) -> None:
    try:
        label.configure(text=_foot_text(hits))
    except tk.TclError:
        return


def _on_search(_event, desk) -> None:
    refresh(desk, getattr(desk, "hits", ()))


def _fallback(tk_mod, desk, hosts) -> None:
    """Month grid and bottom line used only when a sibling did not build."""
    if getattr(desk, "ledger_cal_q", None) is None:
        bar = tk_mod.Frame(hosts["search"], bg=_BG)
        bar.pack(fill="x", padx=16, pady=(4, 4))
        tk_mod.Label(bar, text="Search terms", fg=_QUIET, bg=_BG, font=_FONT).pack(side="left")
        entry = tk_mod.Entry(
            bar,
            bg=_CELL,
            fg=_INK,
            insertbackground=_INK,
            relief="flat",
            font=_FONT,
            width=28,
        )
        entry.pack(side="left", padx=8, ipady=4)
        entry.bind("<Return>", lambda event, bound=desk: _on_search(event, bound))
        desk.ledger_cal_q = entry
    if getattr(desk, "ledger_cal_grid", None) is None:
        grid = tk_mod.Frame(hosts["month"], bg=_BG)
        grid.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        desk.ledger_cal_grid = grid
        desk._ledger_cal_own_grid = grid
    if getattr(desk, "ledger_plan_row", None) is None:
        row = tk_mod.Frame(hosts["plans"], bg=_BG)
        row.pack(fill="x", padx=16, pady=(4, 4))
        labels = []
        for _index in range(3):
            label = tk_mod.Label(
                row, text="Plans", fg=_INK, bg=_CELL, font=_FONT, padx=8, pady=6, anchor="w",
            )
            label.pack(side="left", padx=3)
            labels.append(label)
        desk._ledger_cal_own_plans = tuple(labels)
        desk.ledger_plan_row = row
    if getattr(desk, "ledger_loose", None) is None or getattr(desk, "ledger_priorities", None) is None:
        foot = tk_mod.Label(
            hosts["foot"],
            text=_FOOT,
            fg=_QUIET,
            bg=_BG,
            anchor="w",
            justify="left",
            font=_FONT,
        )
        foot.pack(fill="x", padx=16, pady=(4, 12))
        desk._ledger_cal_own_foot = foot


def _paint_own(desk, hits) -> None:
    grid = getattr(desk, "_ledger_cal_own_grid", None)
    if grid is not None:
        _paint_grid(desk, grid, hits)
    plans = getattr(desk, "_ledger_cal_own_plans", None)
    if plans:
        _paint_plans(plans)
    foot = getattr(desk, "_ledger_cal_own_foot", None)
    if foot is not None:
        _paint_foot(foot, hits)


def build(parent, desk) -> None:
    """Title, search terms, and the calendar pieces inside parent."""
    tk_mod = _tk(desk)
    try:
        parent.configure(bg=_BG)
    except tk.TclError:
        pass
    try:
        for child in list(parent.winfo_children()):
            child.destroy()
    except tk.TclError:
        pass
    cal_head = tk_mod.Frame(parent, bg=_BG)
    cal_head.pack(fill="x", padx=16, pady=(12, 4))

    def _back():
        show = getattr(desk, "show_ledger_body", None)
        if callable(show):
            show("table")

    btn_back = tk_mod.Button(
        cal_head,
        text="← Back to Table",
        command=_back,
        bg=_CELL,
        fg=_INK,
        activebackground="#1E2430",
        activeforeground=_INK,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground="#2A3140",
        highlightcolor="#7C9CFF",
        font=("Segoe UI", -12, "bold"),
        padx=10,
        pady=3,
        cursor="hand2",
    )
    btn_back.pack(side="right", padx=(8, 0))

    tk_mod.Label(
        cal_head,
        text="Calendar view",
        fg=_INK,
        bg=_BG,
        font=_FONT_TITLE,
        anchor="w",
    ).pack(side="left")
    hosts = {}
    for key in ("search", "month", "plans", "foot"):
        frame = tk_mod.Frame(parent, bg=_BG)
        fill = "both" if key == "month" else "x"
        expand = key == "month"
        frame.pack(fill=fill, expand=expand)
        hosts[key] = frame
    loaded = []
    missing = False
    for name in _ORDER:
        mod = _load(name)
        if mod is None:
            missing = True
            continue
        try:
            mod.build(hosts[_HOST[name]], desk)
        except tk.TclError:
            missing = True
            continue
        loaded.append(mod)
    desk._ledger_cal_parts = tuple(loaded)
    if missing:
        _fallback(tk_mod, desk, hosts)
    refresh(desk, getattr(desk, "hits", ()))


def refresh(desk, hits) -> None:
    """Redraw this month, mark matching days, and state the bottom line."""
    if getattr(desk, "_ledger_cal_busy", False):
        return
    desk._ledger_cal_busy = True
    try:
        rows = _rows(hits)
        for mod in getattr(desk, "_ledger_cal_parts", ()):
            fn = getattr(mod, "refresh", None)
            if not callable(fn):
                continue
            try:
                fn(desk, rows)
            except tk.TclError:
                continue
        _paint_own(desk, rows)
    finally:
        desk._ledger_cal_busy = False
