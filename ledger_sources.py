"""RAN IN: the source app a session ran in. Not a page."""

from __future__ import annotations


_RAIL = "#0C0E12"
_CARD = "#12151C"
_ELEVATED = "#181C26"
_LINE = "#2A3140"
_QUIET = "#6B7386"
_WIDTH = 184

# Display names. Anything not listed keeps its harness id. claude is not an exe.
_LABEL = {
    "grok": "Grok.exe",
    "antigravity": "Antigravity.exe",
    "antigravity-ide": "Antigravity.exe",
    "antigravity-cli": "Antigravity.exe",
    "agy": "Antigravity.exe",
    "claude": "claude",
}

_KIND = {
    "grok": "CLI",
    "codex": "CLI",
    "gemini": "CLI",
    "agy": "CLI",
    "antigravity-cli": "CLI",
    "antigravity-ide": "TUI",
    "claude_desktop": "Chat",
    "openwork": "Chat",
    "cowork": "Chat",
}

_ANTIGRAVITY = ("antigravity", "antigravity-ide", "antigravity-cli", "agy")


def _harness(hit) -> str:
    if not isinstance(hit, dict):
        return ""
    return str(hit.get("harness") or "").strip().lower()


def source_label(hit) -> str:
    name = _harness(hit)
    if not name:
        return ""
    return _LABEL.get(name, name)


def source_kind(hit) -> str:
    return _KIND.get(_harness(hit), "CLI")


def _color(harness: str) -> str:
    if harness == "grok":
        return "#93C5FD"
    if harness == "claude":
        return "#C4B5FD"
    if harness == "codex":
        return "#86EFAC"
    if harness == "gemini":
        return "#FDE68A"
    if harness in _ANTIGRAVITY:
        return "#FDBA74"
    return "#A7B0C3"


def _sources(hits):
    """Distinct source labels, each with one kind.

    The same label with two kinds (Antigravity.exe CLI and TUI) stays two
    rows. The click harness is the first hit of that label and kind, because
    filter_harness matches one harness.
    """
    try:
        sequence = list(hits) if hits is not None else []
    except TypeError:
        return []
    seen = set()
    rows = []
    for hit in sequence:
        name = _harness(hit)
        if not name:
            continue
        label = source_label(hit)
        kind = source_kind(hit)
        key = (label, kind)
        if key in seen:
            continue
        seen.add(key)
        rows.append((name, label, kind))
    return rows


def _ui(desk):
    tk = getattr(desk, "tk", None)
    if getattr(tk, "Frame", None) is not None and getattr(tk, "Label", None) is not None:
        return tk
    import tkinter as tkmod
    return tkmod


def _pick(desk, harness: str) -> None:
    desk.filter_harness = harness
    run = getattr(desk, "_run_find", None)
    if callable(run):
        run()


def _row(tk, parent, desk, harness: str, label: str, kind: str, on: bool) -> None:
    bg = _ELEVATED if on else _CARD
    color = _color(harness)
    shell = tk.Frame(parent, bg=_LINE, padx=1, pady=1, cursor="hand2")
    shell.pack(fill="x", padx=8, pady=(0, 6))
    row = tk.Frame(shell, bg=bg, cursor="hand2")
    row.pack(fill="x")
    bar = tk.Frame(row, bg=color, width=3)
    bar.pack_propagate(False)
    bar.pack(side="left", fill="y")
    text = tk.Frame(row, bg=bg, cursor="hand2")
    text.pack(side="left", fill="both", expand=True, padx=(8, 6), pady=6)

    def fire(_event=None, picked=harness):
        _pick(desk, picked)

    name = tk.Button(
        text,
        text=label,
        command=fire,
        fg=color,
        bg=bg,
        activeforeground=color,
        activebackground=bg,
        relief="flat",
        bd=0,
        highlightthickness=0,
        anchor="w",
        justify="left",
        wraplength=148,
        padx=0,
        pady=0,
        font=("Segoe UI", -13),
        cursor="hand2",
    )
    name.pack(fill="x")
    kind_l = tk.Label(
        text,
        text=kind,
        fg=_QUIET,
        bg=bg,
        font=("Segoe UI", -12),
        anchor="w",
        justify="left",
        cursor="hand2",
    )
    kind_l.pack(fill="x")
    for widget in (shell, row, bar, text, kind_l):
        widget.bind("<Button-1>", fire)
    shell.harness = harness


def _scroller(tk, frame):
    canvas = tk.Canvas(frame, bg=_RAIL, highlightthickness=0, bd=0)
    bar = tk.Scrollbar(frame, command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    inner = tk.Frame(canvas, bg=_RAIL)
    window = canvas.create_window((0, 0), window=inner, anchor="nw")

    def on_inner(_event):
        canvas.configure(scrollregion=canvas.bbox("all") or (0, 0, 0, 0))

    def on_canvas(event):
        canvas.itemconfigure(window, width=event.width)

    inner.bind("<Configure>", on_inner)
    canvas.bind("<Configure>", on_canvas)
    bar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True, pady=(8, 0))
    return inner


def build(parent, desk) -> None:
    tk = _ui(desk)
    old = getattr(desk, "ledger_sources", None)
    destroy = getattr(old, "destroy", None)
    if callable(destroy):
        try:
            destroy()
        except tk.TclError:
            pass
    frame = tk.Frame(parent, bg=_RAIL, width=_WIDTH, height=240, highlightthickness=0, bd=0)
    frame.pack_propagate(False)
    frame.pack(side="left", fill="y")
    tk.Frame(frame, bg=_LINE, width=1).pack(side="right", fill="y")
    tk.Label(
        frame,
        text="RAN IN",
        fg=_QUIET,
        bg=_RAIL,
        font=("Segoe UI", -12),
        anchor="w",
    ).pack(side="top", fill="x", padx=12, pady=(14, 6))
    tk.Frame(frame, bg=_LINE, height=1).pack(side="top", fill="x")
    frame.body = _scroller(tk, frame)
    desk.ledger_sources = frame
    refresh(desk, getattr(desk, "hits", None) or [])


def refresh(desk, hits) -> None:
    frame = getattr(desk, "ledger_sources", None)
    body = getattr(frame, "body", None)
    if body is None:
        return
    tk = _ui(desk)
    try:
        children = list(body.winfo_children())
    except tk.TclError:
        return
    for child in children:
        child.destroy()
    selected = str(getattr(desk, "filter_harness", "") or "").strip().lower()
    for harness, label, kind in _sources(hits):
        _row(tk, body, desk, harness, label, kind, harness == selected)
