"""The four paper screens, hosted by the native desk.

Table, one session, calendar, and projects. The desk still owns find,
load, resume, and launch. This module only lays those out.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta


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


def vendor_color(harness: str) -> str:
    return _VCOLOR.get(str(harness or "").lower(), "#A7B0C3")


def title_of(hit: dict) -> str:
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "")


def project_of(hit: dict) -> str:
    cwd = str(hit.get("cwd") or "").replace("/", "\\").rstrip("\\")
    if not cwd or hit.get("legal"):
        return ""
    return cwd.split("\\")[-1]


def age_text(stamp) -> str:
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


def _stamp_dt(stamp):
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return None
    ms = n if n > 100000000000 else n * 1000
    try:
        return datetime.fromtimestamp(ms / 1000)
    except (OSError, OverflowError, ValueError):
        return None


class Sheets:
    """Four views. Call refresh() when the hit list changes."""

    def __init__(self, desk, stage) -> None:
        self.desk = desk
        self.tk = desk.tk
        self.ttk = desk.ttk
        self.group = "flat"
        self.hits: list[dict] = []
        bg = "#07080A"
        self.table = desk.tk.Frame(stage, bg=bg)
        self.session = desk.tk.Frame(stage, bg=bg)
        self.calendar = desk.tk.Frame(stage, bg=bg)
        self.projects = desk.tk.Frame(stage, bg=bg)
        for frame in (self.table, self.session, self.calendar, self.projects):
            frame.grid(row=2, column=0, sticky="nsew")
            frame.grid_remove()
        self._build_table()
        self._build_session()
        self._build_calendar()
        self._build_projects()

    def frames(self) -> dict:
        return {
            "table": self.table,
            "session": self.session,
            "calendar": self.calendar,
            "projects": self.projects,
        }

    def _build_table(self) -> None:
        tk = self.tk
        bar = tk.Frame(self.table, bg="#0C0E12")
        bar.pack(fill="x")
        tk.Label(bar, text="Session type", fg="#6B7386", bg="#0C0E12").pack(side="left", padx=(12, 6), pady=8)
        for label in ("CLI", "TUI", "Chat"):
            tk.Label(bar, text=label, fg="#7C9CFF", bg="#12151C", padx=8, pady=4).pack(side="left", padx=2)
        self.desk._button(bar, "Create summaries", self._summaries).pack(side="left", padx=(12, 4))
        for mode, label in (
            ("maker", "Group by maker"),
            ("project", "Group by project"),
            ("topic", "Group by topic"),
            ("flat", "Flat"),
        ):
            self.desk._button(bar, label, lambda m=mode: self._set_group(m)).pack(side="left", padx=2)
        body = tk.Frame(self.table, bg="#07080A")
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg="#07080A")
        left.pack(side="left", fill="both", expand=True)
        style = self.ttk.Style()
        style.configure(
            "Sheet.Treeview",
            background="#12151C",
            fieldbackground="#12151C",
            foreground="#E8ECF4",
            rowheight=32,
            borderwidth=0,
        )
        style.configure("Sheet.Treeview.Heading", background="#0C0E12", foreground="#6B7386")
        cols = ("app", "time", "title", "tokens", "topic", "project")
        self.tree = self.ttk.Treeview(left, columns=cols, show="headings", style="Sheet.Treeview")
        headers = (
            ("app", "Source app", 140),
            ("time", "Time last active", 120),
            ("title", "Session title", 320),
            ("tokens", "Size / tokens", 110),
            ("topic", "Session topics", 180),
            ("project", "Project", 140),
        )
        for key, text, width in headers:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="w")
        for name, color in _VCOLOR.items():
            self.tree.tag_configure(name, foreground=color)
        self.tree.tag_configure("other", foreground="#A7B0C3")
        self.tree.tag_configure("group", foreground="#A7B0C3")
        self.tree.pack(fill="both", expand=True, padx=(8, 0), pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree)
        glance = tk.Frame(body, bg="#0C0E12", width=220)
        glance.pack(side="right", fill="y")
        glance.pack_propagate(False)
        tk.Label(glance, text="At a glance", fg="#E8ECF4", bg="#0C0E12").pack(anchor="w", padx=12, pady=(12, 4))
        self.glance = tk.Text(
            glance, bg="#0C0E12", fg="#A7B0C3", relief="flat", wrap="word",
            font=("Segoe UI", 11), height=20,
        )
        self.glance.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.glance.configure(state="disabled")

    def _build_session(self) -> None:
        tk = self.tk
        head = tk.Frame(self.session, bg="#07080A")
        head.pack(fill="x", padx=16, pady=(12, 0))
        self.app_name = tk.Label(head, text="App", fg="#7C9CFF", bg="#07080A", font=("Segoe UI", 16, "bold"))
        self.app_name.pack(anchor="w")
        self.facts = tk.Label(
            head, text="", fg="#A7B0C3", bg="#07080A", justify="left", anchor="w",
            font=("Segoe UI", 11), wraplength=900,
        )
        self.facts.pack(anchor="w", pady=(6, 0))
        chain = tk.Frame(self.session, bg="#07080A")
        chain.pack(fill="x", padx=16, pady=8)
        self.desk._button(chain, "Resume", self.desk._on_launch).pack(side="left")
        tk.Label(chain, text="→", fg="#6B7386", bg="#07080A").pack(side="left", padx=6)
        self.chain_harness = tk.Label(chain, text="TUI / harness", fg="#E8ECF4", bg="#12151C", padx=8, pady=4)
        self.chain_harness.pack(side="left")
        tk.Label(chain, text="→", fg="#6B7386", bg="#07080A").pack(side="left", padx=6)
        self.chain_model = tk.Label(chain, text="Model / agent", fg="#E8ECF4", bg="#12151C", padx=8, pady=4)
        self.chain_model.pack(side="left", padx=(0, 12))
        self.desk._button(chain, "Load", self.desk._on_load).pack(side="left", padx=2)
        self.desk._button(chain, "Hand off", self.desk._on_resume).pack(side="left", padx=2)
        self.desk._button(chain, "Import", self.desk._on_import).pack(side="left", padx=2)
        self.desk._button(chain, "Export", self.desk._on_export).pack(side="left", padx=2)
        self.desk._button(chain, "Anonymize", self.desk._on_anonymize).pack(side="left", padx=2)
        self.desk._button(chain, "Check recovery", self.desk._on_recover).pack(side="left", padx=2)
        self.desk._button(chain, "Restore", self.desk._on_restore).pack(side="left", padx=2)
        panes = tk.Frame(self.session, bg="#07080A")
        panes.pack(fill="both", expand=True, padx=16, pady=8)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(1, weight=1)
        tk.Label(panes, text="Session text", fg="#6B7386", bg="#07080A").grid(row=0, column=0, sticky="w")
        tk.Label(panes, text="Session preview", fg="#6B7386", bg="#07080A").grid(row=0, column=1, sticky="w")
        self.text = tk.Text(panes, bg="#12151C", fg="#E8ECF4", relief="flat", wrap="word")
        self.preview = tk.Text(panes, bg="#12151C", fg="#E8ECF4", relief="flat", wrap="word")
        self.text.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.preview.grid(row=1, column=1, sticky="nsew", padx=(6, 0))

    def _build_calendar(self) -> None:
        tk = self.tk
        tk.Label(self.calendar, text="Calendar view", fg="#E8ECF4", bg="#07080A",
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        span = tk.Frame(self.calendar, bg="#07080A")
        span.pack(fill="x", padx=16)
        tk.Label(span, text="Search terms", fg="#6B7386", bg="#07080A").pack(side="left")
        self.span_q = tk.Entry(span, bg="#12151C", fg="#E8ECF4", insertbackground="#E8ECF4", relief="flat")
        self.span_q.pack(side="left", padx=8, ipady=4)
        self.span_q.bind("<Return>", lambda _e: self._paint_calendar())
        self.grid = tk.Frame(self.calendar, bg="#07080A")
        self.grid.pack(fill="both", expand=True, padx=16, pady=8)
        self.plan = tk.Label(
            self.calendar, text="", fg="#A7B0C3", bg="#07080A", justify="left", anchor="w",
            font=("Segoe UI", 12), wraplength=980,
        )
        self.plan.pack(fill="x", padx=16, pady=(0, 12))

    def _build_projects(self) -> None:
        tk = self.tk
        head = tk.Frame(self.projects, bg="#07080A")
        head.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(head, text="Check for projects", fg="#6B7386", bg="#07080A").pack(anchor="w")
        tk.Label(head, text="Projects view", fg="#E8ECF4", bg="#07080A",
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(head, text="Check out  ·  cross-harness", fg="#6B7386", bg="#07080A").pack(anchor="e")
        body = tk.Frame(self.projects, bg="#07080A")
        body.pack(fill="both", expand=True, padx=16, pady=8)
        self.proj_list = tk.Listbox(
            body, bg="#12151C", fg="#E8ECF4", relief="flat", width=36,
            selectbackground="#1E2430", activestyle="none",
        )
        self.proj_list.pack(side="left", fill="y")
        self.proj_list.bind("<<ListboxSelect>>", self._on_project_title)
        self.cards = tk.Frame(body, bg="#07080A")
        self.cards.pack(side="left", fill="both", expand=True, padx=(12, 0))

    def refresh(self, hits: list[dict]) -> None:
        self.hits = [hit for hit in hits if isinstance(hit, dict)]
        self._paint_table()
        self._paint_calendar()
        self._paint_projects()

    def _set_group(self, mode: str) -> None:
        self.group = mode
        self._paint_table()

    def _group_key(self, hit: dict) -> str:
        if self.group == "maker":
            return str(hit.get("harness") or "other")
        if self.group == "project":
            return project_of(hit) or "No project"
        if self.group == "topic":
            return project_of(hit) or "No topic"
        return ""

    def _paint_table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        rows = list(self.hits)
        if self.group != "flat":
            rows.sort(key=lambda hit: (self._group_key(hit), title_of(hit).lower()))
        last = None
        week = 0
        month = 0
        quarter = 0
        now = datetime.now()
        lines = []
        for index, hit in enumerate(rows):
            key = self._group_key(hit)
            if key and key != last:
                last = key
                self.tree.insert("", "end", values=("", "", key, "", "", ""), tags=("group",))
            harness = str(hit.get("harness") or "other")
            tag = harness if harness in _VCOLOR else "other"
            self.tree.insert(
                "", "end", iid=str(index),
                values=(
                    harness,
                    age_text(hit.get("updated")),
                    title_of(hit),
                    "—" if hit.get("legal") else str(hit.get("bytes") or "—"),
                    project_of(hit) or "—",
                    project_of(hit) or "—",
                ),
                tags=(tag,),
            )
            when = _stamp_dt(hit.get("updated"))
            if when is not None:
                age = now - when
                if age <= timedelta(days=7):
                    week += 1
                    if len(lines) < 8:
                        lines.append(f"{age_text(hit.get('updated'))}  {title_of(hit)}")
                if age <= timedelta(days=30):
                    month += 1
                if age <= timedelta(days=92):
                    quarter += 1
        text = "7 days\n" + ("\n".join(lines) or "None")
        text += f"\n\nWeek\n{week} sessions\n\nMonthly\n{month} sessions\n\nQuarterly\n{quarter} sessions"
        self.glance.configure(state="normal")
        self.glance.delete("1.0", "end")
        self.glance.insert("1.0", text)
        self.glance.configure(state="disabled")

    def _on_tree(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            index = int(sel[0])
        except ValueError:
            return
        ordered = self._ordered()
        if index < 0 or index >= len(ordered):
            return
        hit = ordered[index]
        real = self._index_in_desk(hit)
        if real is None:
            return
        self.desk._select(real)
        self.fill_session(hit)
        self.desk._show_view("session")

    def _ordered(self) -> list[dict]:
        rows = list(self.hits)
        if self.group != "flat":
            rows.sort(key=lambda hit: (self._group_key(hit), title_of(hit).lower()))
        return rows

    def _index_in_desk(self, hit: dict):
        ident = hit.get("id")
        for index, row in enumerate(self.desk.hits):
            if row.get("id") == ident:
                return index
        return None

    def fill_session(self, hit: dict) -> None:
        when = _stamp_dt(hit.get("updated"))
        size = hit.get("bytes")
        size_txt = f"{max(1, int(size) // 1024)} KB" if isinstance(size, int) and size else "—"
        self.app_name.configure(text=str(hit.get("harness") or "App"), fg=vendor_color(str(hit.get("harness") or "")))
        self.facts.configure(text=(
            f"Date {when.date().isoformat() if when else '—'}"
            f"    Start {when.strftime('%H:%M') if when else '—'}"
            f"    End —"
            f"    Size {size_txt}"
            f"    Tokens input / output / total —"
            f"\nTime {age_text(hit.get('updated'))}"
            f"    Topic {project_of(hit) or '—'}"
            f"    Location {'' if hit.get('legal') else (hit.get('path') or hit.get('cwd') or '—')}"
            f"\nKeywords {title_of(hit)}"
        ))
        self.chain_harness.configure(text=f"{hit.get('harness') or 'harness'} / harness")
        self.chain_model.configure(text=str(hit.get("model") or "Model / agent"))
        blurb = "Legal session stays closed." if hit.get("legal") else title_of(hit)
        for widget in (self.text, self.preview):
            widget.delete("1.0", "end")
            widget.insert("1.0", blurb)

    def note_preview(self, text: str) -> None:
        if not hasattr(self, "text"):
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)

    def _paint_calendar(self) -> None:
        tk = self.tk
        for child in self.grid.winfo_children():
            child.destroy()
        term = self.span_q.get().strip().lower()
        now = datetime.now()
        cal = calendar.Calendar(firstweekday=6)
        weeks = cal.monthdayscalendar(now.year, now.month)
        days = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
        for col, name in enumerate(days):
            tk.Label(self.grid, text=name, fg="#6B7386", bg="#07080A").grid(row=0, column=col, padx=2)
        counts = {}
        for hit in self.hits:
            when = _stamp_dt(hit.get("updated"))
            if when is None or when.year != now.year or when.month != now.month:
                continue
            if term and term not in title_of(hit).lower() and term not in project_of(hit).lower():
                continue
            counts[when.day] = counts.get(when.day, 0) + 1
        for row, week in enumerate(weeks, start=1):
            for col, day in enumerate(week):
                label = "" if not day else str(day)
                extra = f"\n{counts[day]}" if day in counts else ""
                tk.Label(
                    self.grid, text=label + extra, fg="#E8ECF4", bg="#12151C",
                    width=12, height=3, anchor="nw", justify="left",
                ).grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
        idle = sum(1 for hit in self.hits if str(hit.get("status") or "") == "idle")
        self.plan.configure(text=(
            "Plans sit on the coming days.\n"
            f"Summary  {len(self.hits)} sessions in the list.\n"
            f"Loose ends  {idle or 'idle sessions are not marked yet'}.\n"
            "Next priorities  crashed first, then the oldest unfinished."
        ))

    def _paint_projects(self) -> None:
        self._projects = {}
        for hit in self.hits:
            key = project_of(hit) or "No project"
            bucket = self._projects.setdefault(key, [])
            bucket.append(hit)
        for child in self.cards.winfo_children():
            child.destroy()
        tk = self.tk
        for index, (name, rows) in enumerate(sorted(self._projects.items())[:12]):
            stamps = [_stamp_dt(hit.get("updated")) for hit in rows]
            stamps = [item for item in stamps if item is not None]
            start = min(stamps).date().isoformat() if stamps else "—"
            end = max(stamps).date().isoformat() if stamps else "—"
            card = tk.Frame(self.cards, bg="#12151C", padx=12, pady=10)
            card.grid(row=index // 3, column=index % 3, padx=6, pady=6, sticky="nsew")
            tk.Label(card, text=f"Pr {index + 1}", fg="#E8ECF4", bg="#12151C",
                     font=("Segoe UI", 14, "bold")).pack(anchor="w")
            tk.Label(card, text=name, fg="#A7B0C3", bg="#12151C").pack(anchor="w")
            tk.Label(card, text=f"{len(rows)} sessions", fg="#A7B0C3", bg="#12151C").pack(anchor="w")
            tk.Label(card, text="Token count —", fg="#A7B0C3", bg="#12151C").pack(anchor="w")
            tk.Label(card, text=f"Project start {start}", fg="#A7B0C3", bg="#12151C").pack(anchor="w")
            tk.Label(card, text=f"End {end}", fg="#A7B0C3", bg="#12151C").pack(anchor="w")
        self.proj_list.delete(0, "end")
        self._proj_titles = []
        for name, rows in sorted(self._projects.items()):
            for hit in rows[:8]:
                self.proj_list.insert("end", f"{name}  ·  {title_of(hit)}")
                self._proj_titles.append(hit)

    def _on_project_title(self, _event=None) -> None:
        sel = self.proj_list.curselection()
        if not sel:
            return
        hit = self._proj_titles[sel[0]]
        real = self._index_in_desk(hit)
        if real is None:
            return
        self.desk._select(real)
        self.fill_session(hit)
        self.desk._show_view("session")

    def _summaries(self) -> None:
        self.desk._say(
            "Create summaries uses the title and project already on the row. A model summary is not part of this pass.",
            "warn",
        )
