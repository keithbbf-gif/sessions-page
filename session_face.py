"""Five regions in one native window. Planning is a second view, not the landing screen."""

from __future__ import annotations

BG = "#07080A"
CARD = "#12151C"
INK = "#E8ECF4"
QUIET = "#6B7386"
ACCENT = "#7C9CFF"
LINE = "#2A3140"
OK = "#3DDC97"
WARN = "#F5C542"
BAD = "#FF5C7A"

VENDORS = (
    ("claude", "Claude", "#C4B5FD"),
    ("codex", "Codex", "#86EFAC"),
    ("grok", "Grok", "#93C5FD"),
    ("antigravity", "Antigravity", "#FDBA74"),
    ("gemini", "Gemini", "#FDE68A"),
    ("other", "Other", "#A7B0C3"),
)
_FAMILY = {
    "claude_desktop": "claude",
    "antigravity-ide": "antigravity",
    "antigravity-cli": "antigravity",
    "agy": "antigravity",
}


def vendor_of(hit: dict) -> str:
    name = str(hit.get("harness") or "").lower()
    name = _FAMILY.get(name, name)
    if name in {item[0] for item in VENDORS if item[0] != "other"}:
        return name
    return "other"


def color_of(vendor: str) -> str:
    for key, _label, color in VENDORS:
        if key == vendor:
            return color
    return "#A7B0C3"


def title_of(hit: dict) -> str:
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "Untitled")


def project_of(hit: dict) -> str:
    if hit.get("legal"):
        return ""
    cwd = str(hit.get("cwd") or "").replace("/", "\\").rstrip("\\")
    if not cwd:
        return ""
    return cwd.split("\\")[-1]


def _stamp(hit: dict):
    for key in ("updated", "last_activity", "started"):
        if hit.get(key) not in (None, ""):
            try:
                n = float(hit.get(key))
            except (TypeError, ValueError):
                continue
            return n / 1000 if n > 100000000000 else n
    return None


def mount(desk, stage):
    tk = desk.tk
    stage.configure(bg=BG)
    desk.face_vendors = {key for key, _label, _color in VENDORS}
    desk.face_status = {"active", "idle", "crashed"}
    desk.face_project = ""
    desk.face_mode = "sessions"
    desk.face_axis = "project"
    root = tk.Frame(stage, bg=BG)
    root.pack(fill="both", expand=True)

    rail = tk.Frame(root, bg=CARD, width=160)
    rail.pack(side="left", fill="y")
    rail.pack_propagate(False)
    desk.face_rail = rail
    _rail(desk, rail)

    center = tk.Frame(root, bg=BG)
    center.pack(side="left", fill="both", expand=True)
    work = tk.Frame(center, bg=BG)
    work.pack(fill="both", expand=True)
    work.columnconfigure(0, weight=1)
    work.columnconfigure(1, weight=1)
    work.rowconfigure(0, weight=1)

    desk.face_list_wrap = tk.Frame(work, bg=BG)
    desk.face_list_wrap.grid(row=0, column=0, sticky="nsew")
    desk.face_detail = tk.Frame(work, bg=CARD)
    desk.face_detail.grid(row=0, column=1, sticky="nsew")
    desk.face_plan = tk.Frame(work, bg=BG)
    desk.face_plan.grid(row=0, column=0, columnspan=2, sticky="nsew")
    desk.face_plan.grid_remove()
    _list(desk)
    _detail(desk)
    _plan(desk)

    status = tk.Label(center, text="", fg=INK, bg=CARD, anchor="w", padx=10, pady=6)
    status.pack(fill="x")
    desk.face_status_label = status
    command = tk.Entry(center, bg=BG, fg=INK, insertbackground=INK, relief="flat")
    command.pack(fill="x", ipady=6, padx=8, pady=6)
    command.bind("<Return>", lambda _e: _command(desk, command.get()))
    desk.face_command = command
    desk.ledger_mounted = True
    return stage


def refresh(desk, hits) -> None:
    rows = [hit for hit in (hits or []) if isinstance(hit, dict)]
    desk.face_rows = _filter(desk, rows)
    _paint_projects(desk, rows)
    _paint_list(desk)
    _paint_detail(desk)
    _paint_status(desk, rows)
    _paint_plan(desk, rows)
    _paint_recents(desk)


def _rail(desk, rail) -> None:
    tk = desk.tk
    tk.Label(rail, text="Search", fg=QUIET, bg=CARD).pack(anchor="w", padx=8, pady=(8, 0))
    entry = tk.Entry(rail, textvariable=desk.query, bg=BG, fg=INK, insertbackground=INK, relief="flat")
    entry.pack(fill="x", padx=8, pady=4)
    entry.bind("<Return>", lambda _e: desk._run_find() if hasattr(desk, "_run_find") else None)
    tk.Label(rail, text="Vendors", fg=QUIET, bg=CARD).pack(anchor="w", padx=8, pady=(8, 0))
    desk.face_vendor_vars = {}
    for key, label, color in VENDORS:
        var = tk.IntVar(value=1)
        desk.face_vendor_vars[key] = var
        tk.Checkbutton(
            rail, text=label, variable=var, fg=color, bg=CARD,
            selectcolor=BG, activebackground=CARD, activeforeground=color,
            command=lambda: _apply_vendor_checks(desk),
        ).pack(anchor="w", padx=8)
    tk.Label(rail, text="Project", fg=QUIET, bg=CARD).pack(anchor="w", padx=8, pady=(8, 0))
    desk.face_projects = tk.Frame(rail, bg=CARD)
    desk.face_projects.pack(fill="x", padx=4)
    tk.Label(rail, text="Status", fg=QUIET, bg=CARD).pack(anchor="w", padx=8, pady=(8, 0))
    desk.face_status_vars = {}
    for name in ("active", "idle", "crashed"):
        var = tk.IntVar(value=1)
        desk.face_status_vars[name] = var
        tk.Checkbutton(
            rail, text=name, variable=var, fg=INK, bg=CARD, selectcolor=BG,
            activebackground=CARD, command=lambda: refresh(desk, getattr(desk, "hits", [])),
        ).pack(anchor="w", padx=8)
    tk.Label(rail, text="Recents", fg=QUIET, bg=CARD).pack(anchor="w", padx=8, pady=(8, 0))
    desk.face_recents = tk.Frame(rail, bg=CARD)
    desk.face_recents.pack(fill="x", padx=4)
    tk.Button(
        rail, text="Planning", bg=CARD, fg=ACCENT, relief="flat",
        command=lambda: _toggle_plan(desk),
    ).pack(side="bottom", fill="x", padx=8, pady=8)
    tk.Button(
        rail, text="Collapse", bg=CARD, fg=QUIET, relief="flat",
        command=lambda: _collapse(desk),
    ).pack(side="bottom", fill="x", padx=8)


def _collapse(desk) -> None:
    rail = desk.face_rail
    wide = rail.winfo_width() > 80
    rail.configure(width=40 if wide else 160)


def _apply_vendor_checks(desk) -> None:
    desk.face_vendors = {key for key, var in desk.face_vendor_vars.items() if var.get()}
    refresh(desk, getattr(desk, "hits", []))


def _list(desk) -> None:
    tk = desk.tk
    wrap = desk.face_list_wrap
    tk.Label(wrap, text="Sessions", fg=INK, bg=BG).pack(anchor="w", padx=8, pady=(8, 0))
    tree = desk.ttk.Treeview(wrap, columns=("vendor", "title", "time", "tokens"), show="headings")
    for key, text, width in (
        ("vendor", "Vendor", 90),
        ("title", "Title", 220),
        ("time", "Time", 110),
        ("tokens", "Tokens", 70),
    ):
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=8)
    tree.bind("<<TreeviewSelect>>", lambda _e: _pick(desk))
    desk.face_tree = tree


def _detail(desk) -> None:
    tk = desk.tk
    box = desk.face_detail
    desk.face_head = tk.Label(box, text="Select a session", fg=INK, bg=CARD, justify="left", anchor="w", wraplength=360)
    desk.face_head.pack(fill="x", padx=10, pady=(10, 4))
    row = tk.Frame(box, bg=CARD)
    row.pack(fill="x", padx=10)
    tk.Button(row, text="Continue", command=lambda: _act(desk, "continue")).pack(side="left", padx=(0, 4))
    tk.Button(row, text="Hand off", command=lambda: _menu(desk, row)).pack(side="left", padx=(0, 4))
    tk.Button(row, text="Cross-check", command=lambda: _act(desk, "check")).pack(side="left")
    desk.face_meter = tk.Canvas(box, height=14, bg=BG, highlightthickness=0)
    desk.face_meter.pack(fill="x", padx=10, pady=8)
    desk.face_meter_label = tk.Label(box, text="Context unknown", fg=QUIET, bg=CARD, anchor="w")
    desk.face_meter_label.pack(fill="x", padx=10)
    desk.face_transcript = tk.Text(box, bg=BG, fg=INK, relief="flat", wrap="word", height=12)
    desk.face_transcript.pack(fill="both", expand=True, padx=10, pady=8)
    actions = tk.Frame(box, bg=CARD)
    actions.pack(fill="x", padx=10, pady=(0, 8))
    for label, name in (
        ("Copy", "_copy_preview"),
        ("Export Markdown", "_on_export"),
        ("Export JSON", "_on_export"),
        ("Tag", None),
        ("Star", None),
    ):
        tk.Button(actions, text=label, command=lambda n=name: _named(desk, n)).pack(side="left", padx=2)


def _plan(desk) -> None:
    tk = desk.tk
    box = desk.face_plan
    tk.Label(box, text="Planning", fg=INK, bg=BG, font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
    desk.face_plan_body = tk.Label(box, text="", fg=INK, bg=BG, justify="left", anchor="nw")
    desk.face_plan_body.pack(fill="both", expand=True, padx=12, pady=8)


def _toggle_plan(desk) -> None:
    show = desk.face_mode != "planning"
    desk.face_mode = "planning" if show else "sessions"
    if show:
        desk.face_list_wrap.grid_remove()
        desk.face_detail.grid_remove()
        desk.face_plan.grid()
    else:
        desk.face_plan.grid_remove()
        desk.face_list_wrap.grid()
        desk.face_detail.grid()
    refresh(desk, getattr(desk, "hits", []))


def _filter(desk, rows: list[dict]) -> list[dict]:
    vendors = getattr(desk, "face_vendors", None) or {key for key, _l, _c in VENDORS}
    statuses = set()
    for name, var in getattr(desk, "face_status_vars", {}).items():
        if var.get():
            statuses.add(name)
    query = ""
    try:
        query = desk.query.get().strip().lower()
    except Exception:
        query = ""
    project = getattr(desk, "face_project", "") or ""
    kept = []
    for hit in rows:
        if vendor_of(hit) not in vendors:
            continue
        status = str(hit.get("status") or "idle")
        if statuses and status in ("active", "idle", "crashed") and status not in statuses:
            continue
        if project and project_of(hit) != project:
            continue
        blob = " ".join([
            title_of(hit), project_of(hit), str(hit.get("path") or ""), str(hit.get("cwd") or ""),
        ]).lower()
        if query and query not in blob:
            continue
        kept.append(hit)
    kept.sort(key=lambda hit: _stamp(hit) or 0, reverse=True)
    return kept


def project_of(hit: dict) -> str:
    if hit.get("legal"):
        return ""
    cwd = str(hit.get("cwd") or "").replace("/", "\\").rstrip("\\")
    return cwd.split("\\")[-1] if cwd else ""


def _paint_projects(desk, rows: list[dict]) -> None:
    host = getattr(desk, "face_projects", None)
    if host is None:
        return
    for child in host.winfo_children():
        child.destroy()
    counts: dict[str, int] = {}
    for hit in rows:
        name = project_of(hit) or "No project"
        counts[name] = counts.get(name, 0) + 1
    tk = desk.tk
    tk.Button(
        host, text=f"All  {len(rows)}", anchor="w", bg=CARD, fg=INK, relief="flat",
        command=lambda: _set_project(desk, ""),
    ).pack(fill="x")
    for name, count in sorted(counts.items()):
        tk.Button(
            host, text=f"{name}  {count}", anchor="w", bg=CARD, fg=INK, relief="flat",
            command=lambda n=name: _set_project(desk, n),
        ).pack(fill="x")


def _set_project(desk, name: str) -> None:
    desk.face_project = "" if name == "No project" else name
    refresh(desk, getattr(desk, "hits", []))


def _paint_list(desk) -> None:
    tree = desk.face_tree
    tree.delete(*tree.get_children())
    for index, hit in enumerate(getattr(desk, "face_rows", [])):
        vendor = vendor_of(hit)
        tree.insert(
            "", "end", iid=f"r{index}",
            values=(vendor, title_of(hit), _when(hit), "—"),
            tags=(vendor,),
        )
        tree.tag_configure(vendor, foreground=color_of(vendor))


def _when(hit: dict) -> str:
    stamp = _stamp(hit)
    if stamp is None:
        return "—"
    from datetime import datetime
    try:
        return datetime.fromtimestamp(stamp).strftime("%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "—"


def _pick(desk) -> None:
    sel = desk.face_tree.selection()
    if not sel:
        return
    try:
        index = int(sel[0][1:])
    except ValueError:
        return
    rows = getattr(desk, "face_rows", [])
    if index < 0 or index >= len(rows):
        return
    hit = rows[index]
    desk.face_selected = hit
    real = None
    for at, item in enumerate(getattr(desk, "hits", []) or []):
        if item.get("id") == hit.get("id"):
            real = at
            break
    if real is not None and hasattr(desk, "_select"):
        desk._select(real)
    _paint_detail(desk)


def _paint_detail(desk) -> None:
    hit = getattr(desk, "face_selected", None)
    if not isinstance(hit, dict):
        desk.face_head.configure(text="Select a session")
        desk.face_meter_label.configure(text="Context unknown")
        return
    vendor = vendor_of(hit)
    desk.face_head.configure(
        text=f"{vendor}   {hit.get('model') or 'model unknown'}\n{title_of(hit)}\n{_when(hit)}   tokens —",
        fg=color_of(vendor),
    )
    desk.face_meter_label.configure(text="Context unknown")
    _meter(desk, None)


def _meter(desk, fraction) -> None:
    canvas = desk.face_meter
    canvas.delete("all")
    width = max(canvas.winfo_width(), 200)
    canvas.create_rectangle(0, 4, width, 10, fill=LINE, outline="")
    if fraction is None:
        return
    fill = OK if fraction < 0.6 else WARN if fraction < 0.85 else BAD
    canvas.create_rectangle(0, 4, int(width * fraction), 10, fill=fill, outline="")
    canvas.create_line(int(width * 0.85), 2, int(width * 0.85), 12, fill=INK)


def _paint_status(desk, rows: list[dict]) -> None:
    active = sum(1 for hit in rows if str(hit.get("status") or "") == "active")
    desk.face_status_label.configure(
        text=f"{len(rows)} sessions indexed    {active} active now    Tokens today —",
    )


def _paint_recents(desk) -> None:
    host = getattr(desk, "face_recents", None)
    if host is None:
        return
    for child in host.winfo_children():
        child.destroy()
    rows = list(getattr(desk, "face_rows", []) or [])[:5]
    tk = desk.tk
    for hit in rows:
        tk.Label(host, text=title_of(hit), fg=color_of(vendor_of(hit)), bg=CARD, anchor="w").pack(fill="x")


def _paint_plan(desk, rows: list[dict]) -> None:
    crashed = [hit for hit in rows if str(hit.get("status") or "") == "crashed"]
    idle = [hit for hit in rows if str(hit.get("status") or "") == "idle"]
    projects = {}
    for hit in rows:
        projects[project_of(hit) or "No project"] = projects.get(project_of(hit) or "No project", 0) + 1
    lines = [
        "Range: the sessions in the current list.",
        f"Done: {len(rows)} sessions.",
        "Loose ends: " + (f"{len(idle)} idle." if idle else "none marked."),
        "Next priorities: crashed first, then the oldest unfinished.",
        f"Crashed: {len(crashed)}.",
        "Projects: " + ", ".join(f"{name} {count}" for name, count in sorted(projects.items())[:8]),
    ]
    desk.face_plan_body.configure(text="\n".join(lines))


def _act(desk, kind: str) -> None:
    if kind == "continue" and hasattr(desk, "_on_launch"):
        desk.app_var.set("")
        desk._on_launch()
        return
    if kind == "check":
        desk._say("Cross-check reviews this transcript. Pick a harness. Nothing launches by itself.", "warn")
        return


def _menu(desk, parent) -> None:
    tk = desk.tk
    menu = tk.Menu(parent, tearoff=0, bg=CARD, fg=INK)
    try:
        import engine
        found = engine.installed_launchers()
    except Exception:
        found = []
    if not found:
        menu.add_command(label="No other harness is installed", state="disabled")
    for harness, _path in found:
        menu.add_command(label=harness, command=lambda name=harness: _choose(desk, name))
    menu.tk_popup(parent.winfo_rootx(), parent.winfo_rooty() + 24)


def _choose(desk, harness: str) -> None:
    desk.app_var.set(harness)
    desk._say(f"Hand off to {harness}. Press Hand off again only after you mean to launch.", "")
    if hasattr(desk, "_on_resume"):
        desk._on_resume()


def _named(desk, name) -> None:
    if name and hasattr(desk, name):
        getattr(desk, name)()
    elif hasattr(desk, "_say"):
        desk._say("That action is on the selected session.", "")


def _command(desk, text: str) -> None:
    words = text.lower().split()
    known = {key for key, _label, _color in VENDORS}
    picked = [word for word in words if word in known]
    if picked and hasattr(desk, "face_vendor_vars"):
        for key, var in desk.face_vendor_vars.items():
            var.set(1 if key in picked else 0)
        desk.face_vendors = set(picked)
    else:
        try:
            desk.query.set(text)
        except Exception:
            pass
    refresh(desk, getattr(desk, "hits", []))
