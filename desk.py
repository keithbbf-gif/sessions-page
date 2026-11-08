#!/usr/bin/env python3
"""Sessions desk window. Blackline Craft. Importing this module binds no port and opens no window.

plan_resume and plan_load are pure. The window is built only from main.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import engine

# Command names from the resume table. cursor's binary is agent.
_FAMILY = {
    "grok": "grok",
    "claude": "claude",
    "codex": "codex",
    "cursor": "cursor",
    "agent": "cursor",
    "pi": "pi",
    "hermes": "hermes",
    "cline": "cline",
    "goose": "goose",
    "qwen": "qwen",
    "copilot": "copilot",
    "crush": "crush",
    "openwork": "openwork",
    "cowork": "openwork",
}

RESUME_APPS = (
    "grok", "claude", "codex", "cursor", "agent", "pi", "hermes", "cline",
    "goose", "qwen", "copilot", "crush", "openwork", "cowork",
)


def _family(name: str) -> str:
    return _FAMILY.get(name, name)


def _alias_id(aliases: dict, *keys: str) -> str | None:
    for key in keys:
        val = aliases.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _owned_id(hit: dict, app: str) -> str | None:
    """Vendor id that belongs to app, or None. Does not read a store."""
    harness = str(hit.get("harness") or "")
    aliases = hit.get("aliases") if isinstance(hit.get("aliases"), dict) else {}
    vid = str(hit.get("vendor_id") or "")
    if harness and _family(harness) == _family(app):
        if _family(app) == "openwork":
            return _alias_id(aliases, "opencode_id") or vid
        return vid
    named = _alias_id(aliases, f"{app}_id", app)
    if named:
        return named
    if _family(app) == "openwork":
        return _alias_id(aliases, "opencode_id")
    if _family(app) == "cursor":
        return _alias_id(aliases, "agent_id", "cursor_id")
    return None


def _bare(app: str) -> list[str]:
    """Start the app with no session flag and no foreign id."""
    if app in ("cursor", "agent"):
        return ["agent"]
    if app in ("openwork", "cowork"):
        return []
    return [app]


def _argv_with_id(app: str, owned: str, hit: dict) -> list[str] | None:
    """Same-app argv. None means this flag is not valid for the hit."""
    path = str(hit.get("path") or "")
    if app == "grok":
        return ["grok", "--resume", owned]
    if app == "claude":
        return ["claude", "--resume", owned]
    if app == "codex":
        return ["codex", "resume", owned]
    if app in ("cursor", "agent"):
        return ["agent", "--resume", owned]
    if app == "pi":
        if _family(str(hit.get("harness") or "")) != "pi":
            return None
        return ["pi", "--session", path]
    if app == "hermes":
        return ["hermes", "--resume", owned]
    if app == "cline":
        if not path.endswith(".messages.json"):
            return None
        return ["cline", "--id", owned]
    if app == "goose":
        return ["goose", "session", "--resume", "--session-id", owned]
    if app == "qwen":
        return ["qwen", "--resume", owned]
    if app == "copilot":
        return ["copilot", f"--resume={owned}"]
    if app == "crush":
        return ["crush", "--session", owned]
    if app in ("openwork", "cowork"):
        return []
    return None


def plan_resume(hit: dict, app: str) -> dict:
    """Plan a resume. Pure. Does not launch and does not write a database.

    The default app is the hit harness. A foreign vendor id is not placed
    on another app's resume flag.
    """
    hit = hit or {}
    harness = str(hit.get("harness") or "")
    chosen = str(app or "").strip().lower() or harness
    plan = {
        "kind": "UNMEASURED",
        "app": chosen,
        "harness": harness,
        "id": hit.get("id"),
        "argv": None,
        "launched": False,
    }
    if chosen not in _FAMILY:
        return plan
    owned = _owned_id(hit, chosen)
    same = bool(harness) and _family(harness) == _family(chosen)
    if chosen in ("openwork", "cowork"):
        if owned is None:
            plan["kind"] = "NEED_LOAD"
            plan["argv"] = []
            plan["detail"] = "load turns before focusing OpenWork; no session id is passed"
            return plan
        plan["kind"] = "OPENWORK_FOCUS"
        plan["argv"] = []
        plan["opencode_id"] = owned
        plan["detail"] = "focus this id in OpenWork; this plug does not spawn OpenWork.exe"
        return plan
    if owned is None:
        plan["kind"] = "NEED_LOAD"
        plan["argv"] = _bare(chosen)
        plan["detail"] = "load turns before starting this app; no session id is passed"
        return plan
    argv = _argv_with_id(chosen, owned, hit)
    if argv is None:
        if same:
            return plan
        plan["kind"] = "NEED_LOAD"
        plan["argv"] = _bare(chosen)
        plan["detail"] = "load turns before starting this app; no session id is passed"
        return plan
    plan["kind"] = "OK"
    plan["argv"] = argv
    return plan


def plan_load(hit: dict) -> dict:
    """Load reads the session. The source path is not modified."""
    hit = hit or {}
    return {
        "action": "load",
        "id": str(hit.get("id") or ""),
        "path": str(hit.get("path") or ""),
        "modify_source": False,
    }


def plan_foreign_launch(hit: dict, app: str) -> dict:
    """Plan a cross-app start. Pure. Does not export and does not launch.

    A NEED_LOAD plan becomes a bare handoff. OpenWork and Cowork stay as
    planned and are not started. Any other kind is returned unchanged.
    """
    hit = hit or {}
    plan = plan_resume(hit, app)
    if plan.get("kind") != "NEED_LOAD":
        return plan
    chosen = str(plan.get("app") or "")
    if chosen in ("openwork", "cowork"):
        return plan
    bare = list(plan.get("argv") or [])[:1]
    return {
        "kind": "HANDOFF",
        "app": chosen,
        "harness": plan.get("harness"),
        "id": plan.get("id"),
        "argv": bare,
        "cwd": hit.get("cwd") or "",
        "launched": False,
        "export": True,
        "writes_vendor": False,
        "detail": (
            "the transcript is exported beside the app and the other app "
            "is started in that cwd without a resume id"
        ),
    }


_INSTANCE_HANDLE = None


def instance_name() -> str:
    return "Local\\cmSessionsDesk"


def claim_instance() -> bool:
    """Hold the desk mutex. Call from main only. Import does not call this."""
    global _INSTANCE_HANDLE
    if os.name != "nt":
        return True
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
    handle = kernel.CreateMutexW(None, 0, instance_name())
    # 183 is ERROR_ALREADY_EXISTS, captured as this call's GetLastError.
    if ctypes.get_last_error() == 183:
        if handle:
            kernel.CloseHandle(handle)
        return False
    _INSTANCE_HANDLE = handle
    return True


def _session_label(hit: dict) -> str:
    if hit.get("legal"):
        title = "Legal session"
    else:
        title = str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "")
    return f"{hit.get('harness') or ''}   {title}   {hit.get('id') or ''}"


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


# Blackline Craft. #7EE0C6 is only the Sessions card mark.
_BG = "#07080A"
_RAIL = "#0C0E12"
_CARD = "#12151C"
_ELEVATED = "#181C26"
_LINE = "#2A3140"
_INK = "#E8ECF4"
_SECONDARY = "#A7B0C3"
_QUIET = "#6B7386"
_ACCENT = "#7C9CFF"
_READY = "#3DDC97"
_NOT_READY = "#F5C542"
_BAD = "#FF5C7A"
_MONO = "#D2D8E6"
_TEAL = "#7EE0C6"

_FONT = ("Segoe UI", -15)
_FONT_TITLE = ("Segoe UI", -22)
_FONT_SMALL = ("Segoe UI", -13)
_FONT_TAG = ("Segoe UI", -12)
_FONT_MONO = ("Consolas", -13)
_FONT_LETTER = ("Consolas", -22)


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _space(value) -> str:
    amount = float(value)
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    unit = 0
    while amount >= 1024 and unit < len(units) - 1:
        amount /= 1024.0
        unit += 1
    text = str(int(amount)) if unit == 0 else f"{amount:.1f}"
    return f"{text} {units[unit]}"


def _drive_view(drive: dict) -> dict:
    """Card fields. The bar is the used share, and only when ready."""
    ready = drive.get("ready") is True
    free = drive.get("free")
    total = drive.get("total")
    sized = _num(free) and _num(total)
    used = None
    if ready and sized and float(total) > 0:
        span = (float(total) - float(free)) / float(total)
        used = max(0.0, min(1.0, span))
    return {
        "letter": str(drive.get("id") or drive.get("path") or ""),
        "label": str(drive.get("label") or "").strip(),
        "kind": str(drive.get("kind") or ""),
        "fs": str(drive.get("fs") or ""),
        "free_text": f"{_space(free)} free" if sized else "",
        "status": "READY" if ready else "NOT READY",
        "used": used,
    }


def _home_view(home: dict) -> dict:
    """Presence card. n stays null until a walk and is not shown."""
    present = bool(home.get("present"))
    where = home.get("path") or home.get("candidate") or ""
    return {
        "harness": str(home.get("harness") or ""),
        "where": str(where) if where else "No documented path",
        "status": "PRESENT" if present else "ABSENT",
    }


def _chip_specs(families) -> list[tuple[str, str]]:
    specs = []
    for fam in families or []:
        if not isinstance(fam, dict) or fam.get("n") is None:
            continue
        name = str(fam.get("family") or "")
        if not name:
            continue
        specs.append((f"{name} {fam.get('n')}", name))
    return specs


def _when(stamp) -> str:
    import datetime as dt
    if isinstance(stamp, bool):
        return ""
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    if n > 100000000000:
        n = n / 1000.0
    try:
        return dt.datetime.fromtimestamp(n).strftime("%m/%d/%Y  %I:%M %p")
    except (OverflowError, OSError, ValueError):
        return ""


def _hit_date(hit: dict) -> str:
    import datetime as dt
    stamp = hit.get("updated")
    n = 0.0
    if not isinstance(stamp, bool):
        try:
            n = float(stamp)
        except (TypeError, ValueError):
            n = 0.0
    if n > 100000000000:
        n = n / 1000.0
    if n > 0:
        try:
            return dt.datetime.fromtimestamp(n).date().isoformat()
        except (OverflowError, OSError, ValueError):
            pass
    return dt.date.today().isoformat()


def _tone(rec: dict) -> str:
    kind = str(rec.get("kind") or "")
    if kind in ("TRUNCATED", "OPENWORK_FOCUS", "DRY_RUN", "NEED_LOAD"):
        return "warn"
    if kind in ("OK", "LAUNCHED", "ALREADY_OK", "VERIFIED", "HANDOFF"):
        return "good"
    if kind:
        return "bad"
    return ""


def _sentence(rec: dict) -> str:
    if not isinstance(rec, dict):
        return str(rec)
    kind = str(rec.get("kind") or "")
    gate = rec.get("gate") if isinstance(rec.get("gate"), dict) else {}
    verb = str(rec.get("verb") or "")
    detail = str(gate.get("detail") or rec.get("detail") or "")
    argv = gate.get("argv")
    if not isinstance(argv, list):
        argv = rec.get("argv") if isinstance(rec.get("argv"), list) else None
    if verb == "preview":
        shown = gate.get("shown")
        n = gate.get("n_turns")
        if isinstance(n, int) and not isinstance(n, bool):
            line = f"Showing {shown} of {n} turns."
        else:
            line = f"First {shown} turns."
        if kind == "TRUNCATED":
            return line + " The file ended early."
        return line
    if verb == "load":
        n = gate.get("n_turns")
        if isinstance(n, int) and not isinstance(n, bool):
            return f"Loaded. {n} turns. The source was not modified."
        return kind or "Loaded."
    if verb == "import":
        return "The source was left in place."
    if verb == "export":
        out = gate.get("out") or ""
        return f"{kind} {out}".strip()
    if verb == "strip_dry":
        return (
            f"Strip would keep {gate.get('kept')} turns and drop "
            f"{gate.get('dropped_markers')}. Nothing was written."
        )
    if verb == "strip":
        written = rec.get("written") if isinstance(rec.get("written"), dict) else {}
        path = written.get("jsonl") or ""
        line = "Stripped copy written. Original unchanged."
        return f"{line} {path}".strip()
    if verb == "anonymize":
        n = gate.get("n_redactions")
        line = "Anonymized copy written. Original unchanged."
        if isinstance(n, int) and not isinstance(n, bool):
            return f"Anonymized copy written. {n} redactions. Original unchanged."
        return line
    if verb == "index":
        n = gate.get("n")
        out = gate.get("out") or ""
        if not isinstance(n, int) or isinstance(n, bool):
            return kind or "Index"
        line = f"Index of {n}"
        return f"{line} — {out}" if out else line
    if verb in ("recover", "crash-recover"):
        if kind == "ALREADY_OK":
            return "File checks out. Nothing was changed."
        if kind == "NO_BAK":
            return "File needs a backup. None was found beside it, so it was left alone."
        if kind == "DRY_RUN":
            return "A backup is ready. Nothing was copied."
        if kind == "BUSY":
            return "The file is in use. Nothing was changed."
        if kind == "OK":
            bak = gate.get("bak_path") or ""
            return "Restored from the backup." + (f" {bak}" if bak else "")
        return kind or "Recover"
    if isinstance(argv, list) and argv:
        prefix = "Launched. " if gate.get("launched") or rec.get("launched") else ""
        return prefix + " ".join(str(tok) for tok in argv)
    if detail:
        return f"{kind}: {detail}" if kind and kind not in detail else detail
    return kind or "Done."


def _preview_body(rec: dict) -> str:
    gate = rec.get("gate") if isinstance(rec.get("gate"), dict) else {}
    turns = gate.get("turns") if isinstance(gate.get("turns"), list) else []
    parts = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "turn")
        text = str(turn.get("text") or "").strip()
        parts.append(f"{role}\n{text}" if text else role)
    if not parts:
        return "No dialogue in this preview."
    return "\n\n".join(parts)


def _name_text(result) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("title", "name", "text"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    return str(result).strip()


def _call_maybe_name(fn, payload: dict):
    """Call maybe_name with the safe fields only. No transcript and no path."""
    import inspect
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(**payload)
    params = list(sig.parameters.values())
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params):
        return fn(**payload)
    aliases = {
        "vendor": "vendor",
        "session_id": "session_id",
        "session": "session_id",
        "id": "session_id",
        "harness": "harness",
        "title": "title",
        "placeholder": "title",
        "placeholder_title": "title",
        "turns": "turns",
        "n_turns": "turns",
        "turn_count": "turns",
        "date": "date",
        "when": "date",
    }
    kwargs = {}
    for param in params:
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        source = aliases.get(param.name)
        if source is None or source not in payload:
            continue
        kwargs[param.name] = payload[source]
    if not kwargs and len(params) == 1:
        return fn(payload)
    return fn(**kwargs)


def _index_hits(payload) -> list[dict]:
    """Hits from read_saved_index. Empty means there is nothing to paint yet."""
    rows = None
    if isinstance(payload, dict):
        for key in ("hits", "rows", "sessions"):
            found = payload.get(key)
            if isinstance(found, list):
                rows = found
                break
    elif isinstance(payload, (list, tuple)):
        rows = payload
    if not rows:
        return []
    return [row for row in rows if isinstance(row, dict)]


def _saved_record(payload, hits: list[dict]) -> dict:
    if isinstance(payload, dict) and isinstance(payload.get("hits"), list):
        return payload
    legal = sum(1 for hit in hits if hit.get("legal"))
    return {
        "hits": hits,
        "n": len(hits),
        "n_shown": len(hits),
        "legal_omitted": legal,
    }


class _Desk:
    """Tk widgets exist only after main imports tkinter and constructs this."""

    def __init__(self, tk, ttk) -> None:
        self.tk = tk
        self.ttk = ttk
        self.hits: list[dict] = []
        self.filter_harness = ""
        self.filter_drive = ""
        self.busy = False
        self.strip_ok = ""
        self.selected_index = None
        self.view = "overview"
        self._preview_id = ""
        self._preview_turns = None
        self._painting = False
        self._find_pending = False
        self._job = 0
        self._paint_token = 0
        self._hold_lead = False
        self._formats_ready = False
        self._nav = {}
        self._chips = []
        self._row_widgets = []
        self._drive_cards = []
        self._location_cards = []
        self._drive_width = 0
        self._location_width = 0
        self._chip_width = 0
        self.root = tk.Tk()
        self.root.title("CM Sessions")
        self.root.geometry("1280x720")
        self.root.minsize(1100, 560)
        self.root.configure(bg=_BG)
        self.query = tk.StringVar()
        self.app_var = tk.StringVar(value="")
        self._build()

    def _build(self) -> None:
        tk = self.tk
        rail = tk.Frame(self.root, bg=_RAIL, width=292, height=720)
        rail.pack_propagate(False)
        rail.pack(side="left", fill="y")
        tk.Frame(self.root, bg=_ACCENT, width=2).pack(side="left", fill="y")
        stage = tk.Frame(self.root, bg=_BG)
        stage.pack(side="left", fill="both", expand=True)
        stage.rowconfigure(2, weight=1)
        stage.columnconfigure(0, weight=1)

        self.status = tk.Label(
            rail, text="Ready", fg=_QUIET, bg=_RAIL, font=_FONT_SMALL,
            anchor="w", justify="left", wraplength=250,
        )
        self.status.pack(side="bottom", fill="x", padx=16, pady=16)
        brand = tk.Frame(rail, bg=_RAIL)
        brand.pack(fill="x", padx=16, pady=(18, 10))
        tk.Label(brand, text="cmSessions", fg=_INK, bg=_RAIL, font=_FONT_TITLE).pack(anchor="w")
        tk.Frame(brand, bg=_ACCENT, height=3).pack(fill="x", pady=(8, 0))
        tk.Label(
            brand, text="Local session desk", fg=_QUIET, bg=_RAIL, font=_FONT_SMALL,
        ).pack(anchor="w", pady=(6, 0))
        nav_items = (
            ("table", "Table", "Sessions by app and time"),
            ("session", "Session", "Read and resume one"),
            ("calendar", "Calendar", "Days, plans, loose ends"),
            ("projects", "Projects", "Cards across harnesses"),
            ("overview", "Overview", "Drives and locations"),
            ("sessions", "Sessions", "Search, resume, launch"),
            ("formats", "Formats", "How each app stores chats"),
            ("recover", "Recover", "Check and restore a file"),
            ("tools", "Tools", "Index, export, names"),
        )
        for kind, title, subtitle in nav_items:
            card = self._nav_card(rail, title, subtitle, kind)
            card.pack(fill="x", padx=16, pady=(0, 8))
            self._nav[kind] = card
        self.nav_overview = self._nav["overview"]
        self.nav_sessions = self._nav["sessions"]

        header = tk.Frame(stage, bg=_ELEVATED, padx=16, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        left = tk.Frame(header, bg=_ELEVATED)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="Sessions", fg=_INK, bg=_ELEVATED, font=_FONT_TITLE).pack(anchor="w")
        self.lead = tk.Label(
            left, text="Scanning drives and locations…", fg=_SECONDARY, bg=_ELEVATED,
            font=_FONT, anchor="w", justify="left", wraplength=720,
        )
        self.lead.pack(anchor="w", fill="x")
        self.say = tk.Label(
            left, text="", fg=_SECONDARY, bg=_ELEVATED, font=_FONT_SMALL,
            anchor="w", justify="left", wraplength=720,
        )
        self.say.pack(anchor="w", fill="x")
        buttons = tk.Frame(header, bg=_ELEVATED)
        buttons.pack(side="right", anchor="n")
        self._button(buttons, "Refresh", self._load_all).pack(side="left", padx=(0, 8))
        self._button(buttons, "Build index", self._on_index).pack(side="left", padx=(0, 8))
        self._button(buttons, "Quit", self._on_quit).pack(side="left")

        tk.Frame(stage, bg=_LINE, height=1).grid(row=1, column=0, sticky="ew")
        self.overview = tk.Frame(stage, bg=_BG)
        self.overview.grid(row=2, column=0, sticky="nsew")
        self.sessions = tk.Frame(stage, bg=_BG)
        self.sessions.grid(row=2, column=0, sticky="nsew")
        self.sessions.grid_remove()
        self._build_overview()
        self._build_sessions()
        self.formats = tk.Frame(stage, bg=_BG)
        self.formats.grid(row=2, column=0, sticky="nsew")
        self.formats.grid_remove()
        self.recover = tk.Frame(stage, bg=_BG)
        self.recover.grid(row=2, column=0, sticky="nsew")
        self.recover.grid_remove()
        self.tools = tk.Frame(stage, bg=_BG)
        self.tools.grid(row=2, column=0, sticky="nsew")
        self.tools.grid_remove()
        import sheets as sheet_ui
        self.sheets = sheet_ui.Sheets(self, stage)
        self._views = {
            "overview": self.overview,
            "sessions": self.sessions,
            "formats": self.formats,
            "recover": self.recover,
            "tools": self.tools,
        }
        self._views.update(self.sheets.frames())
        self._build_formats()
        self._build_recover()
        self._build_tools()
        for frame in (self.overview, self.sessions, self.formats, self.recover, self.tools):
            frame.grid_remove()
        if getattr(self, "sheets", None) is not None:
            for frame in self.sheets.frames().values():
                frame.grid_remove()
        import ledger
        self.ledger_host = tk.Frame(stage, bg=_BG)
        self.ledger_host.grid(row=0, column=0, rowspan=3, sticky="nsew")
        ledger.mount(self, self.ledger_host)
        rail.pack_forget()
        self.app_var.trace_add("write", self._on_app_change)

    def _button(self, parent, text, command):
        return self.tk.Button(
            parent, text=text, command=command, bg=_ELEVATED, fg=_INK,
            activebackground="#1E2430", activeforeground=_INK, relief="flat",
            bd=0, highlightthickness=1, highlightbackground=_LINE,
            highlightcolor=_ACCENT, font=_FONT, padx=10, pady=4, cursor="hand2",
        )

    def _nav_card(self, parent, title, subtitle, kind):
        tk = self.tk
        shell = tk.Frame(parent, bg=_LINE, padx=1, pady=1, cursor="hand2")
        inner = tk.Frame(shell, bg=_CARD, cursor="hand2")
        inner.pack(fill="both", expand=True)
        row = tk.Frame(inner, bg=_CARD, cursor="hand2")
        row.pack(fill="x", padx=12, pady=14)
        bar = tk.Frame(row, bg=_CARD, width=3)
        bar.pack_propagate(False)
        bar.pack(side="left", fill="y", padx=(0, 10))
        mark = tk.Frame(row, bg=_CARD, width=44, height=44)
        mark.pack_propagate(False)
        mark.pack(side="left", padx=(0, 10))
        canvas = tk.Canvas(mark, width=44, height=44, bg=_CARD, highlightthickness=0, bd=0)
        canvas.pack()
        self._draw_mark(canvas, kind)
        text = tk.Frame(row, bg=_CARD, cursor="hand2")
        text.pack(side="left", fill="both", expand=True)
        title_l = tk.Label(
            text, text=title, fg=_INK, bg=_CARD, font=("Segoe UI", -17, "bold"), anchor="w",
        )
        title_l.pack(fill="x")
        sub_l = tk.Label(text, text=subtitle, fg=_SECONDARY, bg=_CARD, font=_FONT_SMALL, anchor="w")
        sub_l.pack(fill="x")
        shell._parts = (inner, bar, mark, canvas, text, title_l, sub_l)
        self._bind_click(shell, lambda name=kind: self._show_view(name))
        return shell

    def _draw_mark(self, canvas, kind: str) -> None:
        canvas.delete("all")
        if kind == "sessions":
            color = _TEAL
            canvas.create_line(12, 16, 32, 16, fill=color, width=2, capstyle="round")
            canvas.create_line(12, 22, 32, 22, fill=color, width=2, capstyle="round")
            canvas.create_line(12, 28, 26, 28, fill=color, width=2, capstyle="round")
            return
        if kind == "formats":
            canvas.create_rectangle(12, 12, 32, 32, outline=_ACCENT, width=1)
            canvas.create_line(16, 18, 28, 18, fill=_ACCENT, width=1)
            canvas.create_line(16, 22, 28, 22, fill=_ACCENT, width=1)
            canvas.create_line(16, 26, 24, 26, fill=_ACCENT, width=1)
            return
        if kind == "recover":
            canvas.create_oval(12, 12, 32, 32, outline=_NOT_READY, width=2)
            canvas.create_line(22, 16, 22, 24, fill=_NOT_READY, width=2)
            canvas.create_oval(21, 26, 24, 29, fill=_NOT_READY, outline="")
            return
        if kind == "tools":
            canvas.create_rectangle(14, 14, 22, 30, outline=_ACCENT, width=2)
            canvas.create_rectangle(22, 18, 30, 26, outline=_ACCENT, width=2)
            return
        if kind == "table":
            canvas.create_line(12, 16, 32, 16, fill=_ACCENT, width=2)
            canvas.create_line(12, 22, 32, 22, fill=_ACCENT, width=2)
            canvas.create_line(12, 28, 26, 28, fill=_ACCENT, width=2)
            return
        if kind == "session":
            canvas.create_rectangle(12, 12, 32, 32, outline=_TEAL, width=2)
            return
        if kind == "calendar":
            canvas.create_rectangle(12, 14, 32, 32, outline=_ACCENT, width=1)
            canvas.create_line(12, 20, 32, 20, fill=_ACCENT, width=1)
            return
        if kind == "projects":
            canvas.create_rectangle(10, 16, 20, 32, outline=_ACCENT, width=1)
            canvas.create_rectangle(22, 12, 34, 32, outline=_ACCENT, width=1)
            return
        for x, y in ((12, 12), (24, 12), (12, 24), (24, 24)):
            canvas.create_rectangle(x, y, x + 8, y + 8, outline=_ACCENT, width=1)

    def _style_nav(self, shell, on: bool, kind: str) -> None:
        bg = _ELEVATED if on else _CARD
        shell.configure(bg=_ACCENT if on else _LINE)
        inner, bar, mark, canvas, text, title_l, sub_l = shell._parts
        for widget in (inner, mark, text):
            widget.configure(bg=bg)
        bar.configure(bg=_ACCENT if on else bg)
        title_l.configure(bg=bg, fg=_INK)
        sub_l.configure(bg=bg, fg=_SECONDARY)
        canvas.configure(bg=bg)
        self._draw_mark(canvas, kind)

    def _show_view(self, name: str) -> None:
        if name not in getattr(self, "_views", {}):
            name = "overview"
        self.view = name
        for key, frame in self._views.items():
            if key == name:
                frame.grid(row=2, column=0, sticky="nsew")
            else:
                frame.grid_remove()
        for key, shell in self._nav.items():
            self._style_nav(shell, key == name, key)
        if name == "formats":
            self._fill_formats()

    def _bind_click(self, widget, callback) -> None:
        widget.bind("<Button-1>", lambda _event, fn=callback: fn())
        for child in list(widget.winfo_children()):
            self._bind_click(child, callback)

    def _scroller(self, parent, bg):
        tk = self.tk
        canvas = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0)
        bar = tk.Scrollbar(parent, command=canvas.yview)
        inner = tk.Frame(canvas, bg=bg)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_inner(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas(event):
            canvas.itemconfigure(window, width=event.width)

        inner.bind("<Configure>", on_inner)
        canvas.bind("<Configure>", on_canvas)
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self._wheel(canvas)
        return inner

    def _wheel(self, canvas) -> None:
        def on_wheel(event):
            try:
                canvas.yview_scroll(int(-event.delta / 120), "units")
            except self.tk.TclError:
                pass

        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", on_wheel))
        canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))

    def _panel(self, parent):
        shell = self.tk.Frame(parent, bg=_LINE, padx=1, pady=1)
        inner = self.tk.Frame(shell, bg=_CARD)
        inner.pack(fill="both", expand=True)
        return shell, inner

    def _page_title(self, parent, title: str, body: str):
        tk = self.tk
        tk.Label(parent, text=title, fg=_INK, bg=_BG, font=_FONT_TITLE).pack(anchor="w", padx=20, pady=(18, 4))
        rule = tk.Frame(parent, bg=_ACCENT, height=3, width=72)
        rule.pack_propagate(False)
        rule.pack(anchor="w", padx=20)
        tk.Label(
            parent, text=body, fg=_SECONDARY, bg=_BG, font=_FONT, justify="left",
            wraplength=760,
        ).pack(anchor="w", padx=20, pady=(8, 12))

    def _build_formats(self) -> None:
        inner = self._scroller(self.formats, _BG)
        self._page_title(
            inner, "Formats",
            "Each row is one way an app stores a chat. Measured means Load can read it.",
        )
        self.format_list = self.tk.Frame(inner, bg=_BG)
        self.format_list.pack(fill="x", padx=14, pady=(0, 24))

    def _fill_formats(self) -> None:
        if self._formats_ready:
            return
        try:
            rec = engine.dispatch("formats")
        except engine.PageError as exc:
            self._say(f"{exc.kind}: {exc}", "bad")
            return
        gate = rec.get("gate") if isinstance(rec.get("gate"), dict) else {}
        rows = gate.get("formats") if isinstance(gate.get("formats"), list) else []
        for child in self.format_list.winfo_children():
            child.destroy()
        for row in rows:
            if not isinstance(row, dict):
                continue
            shell, card = self._panel(self.format_list)
            shell.pack(fill="x", padx=6, pady=4)
            name = str(row.get("harness") or "")
            load = str(row.get("load") or "")
            color = _READY if load == "measured" else (_NOT_READY if load == "unmeasured" else _QUIET)
            top = self.tk.Frame(card, bg=_CARD)
            top.pack(fill="x", padx=12, pady=(8, 0))
            self.tk.Label(
                top, text=name, fg=_INK, bg=_CARD, font=("Segoe UI", -15, "bold"),
            ).pack(side="left")
            self.tk.Label(
                top, text=load.upper(), fg=color, bg=_CARD, font=_FONT_TAG,
            ).pack(side="right")
            detail = "  ·  ".join(
                bit for bit in (str(row.get("resume") or ""), str(row.get("home") or "")) if bit
            )
            self.tk.Label(
                card, text=detail, fg=_SECONDARY, bg=_CARD, font=_FONT_SMALL,
                anchor="w", justify="left", wraplength=760,
            ).pack(fill="x", padx=12, pady=(2, 8))
        self._formats_ready = True
        self._say(f"{len(rows)} formats.")

    def _build_recover(self) -> None:
        inner = self._scroller(self.recover, _BG)
        self._page_title(
            inner, "Recover",
            "Check looks at the selected session and does not copy anything. Restore asks first, then copies a verified sibling backup over the file.",
        )
        row = self.tk.Frame(inner, bg=_BG)
        row.pack(anchor="w", padx=20, pady=(0, 12))
        self._button(row, "Check recovery", self._on_recover).pack(side="left", padx=(0, 8))
        self._button(row, "Restore", self._on_restore).pack(side="left")
        self.tk.Label(
            inner,
            text="Select the session on the Sessions tab first. A locked database is left alone. Legal files are refused.",
            fg=_QUIET, bg=_BG, font=_FONT_SMALL, wraplength=760, justify="left",
        ).pack(anchor="w", padx=20)

    def _build_tools(self) -> None:
        inner = self._scroller(self.tools, _BG)
        self._page_title(
            inner, "Tools",
            "Index writes a local list. Import, export, anonymize, and strip write under var and leave the original chat where it is.",
        )
        actions = (
            ("Build index", self._on_index),
            ("Import", self._on_import),
            ("Export", self._on_export),
            ("Anonymize", self._on_anonymize),
            ("Check strip", self._on_strip_dry),
            ("Write strip", self._on_strip),
            ("Name", self._on_name),
            ("Formats", self._on_formats),
        )
        grid = self.tk.Frame(inner, bg=_BG)
        grid.pack(anchor="w", padx=20, pady=(0, 12))
        for index, (label, command) in enumerate(actions):
            self._button(grid, label, command).grid(
                row=index // 2, column=index % 2, padx=(0, 8), pady=(0, 8), sticky="ew",
            )
        self.tk.Label(
            inner,
            text="Name stays off unless CMSESSIONS_NAME is 1 and XAI_API_KEY is set. It sends a header, not the transcript.",
            fg=_QUIET, bg=_BG, font=_FONT_SMALL, wraplength=760, justify="left",
        ).pack(anchor="w", padx=20)

    def _build_overview(self) -> None:
        tk = self.tk
        inner = self._scroller(self.overview, _BG)
        tk.Label(
            inner, text="Drives", fg=_INK, bg=_BG, font=("Segoe UI", -16, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 6))
        self.drive_grid = tk.Frame(inner, bg=_BG)
        self.drive_grid.pack(fill="x", padx=10)
        tk.Label(
            inner, text="Locations", fg=_INK, bg=_BG, font=("Segoe UI", -16, "bold"),
        ).pack(anchor="w", padx=16, pady=(18, 6))
        self.location_grid = tk.Frame(inner, bg=_BG)
        self.location_grid.pack(fill="x", padx=10, pady=(0, 24))
        self.drive_grid.bind(
            "<Configure>",
            lambda event: self._on_grid_configure(
                event, self.drive_grid, self._drive_cards, 270, "_drive_width",
            ),
        )
        self.location_grid.bind(
            "<Configure>",
            lambda event: self._on_grid_configure(
                event, self.location_grid, self._location_cards, 340, "_location_width",
            ),
        )

    def _build_search(self, parent):
        tk = self.tk
        wrap = tk.Frame(parent, bg=_LINE, padx=1, pady=1)
        inner = tk.Frame(wrap, bg=_CARD, height=44)
        inner.pack(fill="x")
        inner.pack_propagate(False)
        entry = tk.Entry(
            inner, textvariable=self.query, bg=_CARD, fg=_INK, insertbackground=_INK,
            relief="flat", font=_FONT, highlightthickness=0, bd=0,
        )
        entry.place(x=10, y=8, relwidth=1.0, width=-20, height=28)
        placeholder = tk.Label(
            inner, text="Search title, id, or folder", fg=_QUIET, bg=_CARD, font=_FONT,
        )

        def sync(*_args):
            if self.query.get():
                placeholder.place_forget()
            else:
                placeholder.place(x=12, y=8)

        self.query.trace_add("write", sync)
        placeholder.bind("<Button-1>", lambda _event: entry.focus_set())
        entry.bind("<Return>", lambda _event: self._run_find())
        sync()
        self.entry = entry
        return wrap

    def _build_sessions(self) -> None:
        tk = self.tk
        self.sessions.columnconfigure(0, weight=1)
        self.sessions.rowconfigure(2, weight=1)
        search = tk.Frame(self.sessions, bg=_BG)
        search.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        search.columnconfigure(0, weight=1)
        self._build_search(search).grid(row=0, column=0, sticky="ew")
        self.chip_frame = tk.Frame(self.sessions, bg=_BG)
        self.chip_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(10, 0))
        self.chip_frame.bind("<Configure>", self._on_chip_configure)

        body = tk.Frame(self.sessions, bg=_BG)
        body.grid(row=2, column=0, sticky="nsew", padx=16, pady=12)
        body.columnconfigure(0, weight=1, minsize=340)
        body.columnconfigure(1, weight=1, minsize=420)
        body.rowconfigure(0, weight=1)

        list_shell, list_inner = self._panel(body)
        list_shell.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.count = tk.Label(
            list_inner, text="Sessions", fg=_SECONDARY, bg=_CARD, font=_FONT_SMALL, anchor="w",
        )
        self.count.pack(fill="x", padx=12, pady=(8, 6))
        tk.Frame(list_inner, bg=_LINE, height=1).pack(fill="x")
        host = tk.Frame(list_inner, bg=_CARD)
        host.pack(fill="both", expand=True)
        self.list_inner = self._scroller(host, _CARD)

        detail_shell, detail = self._panel(body)
        detail_shell.grid(row=0, column=1, sticky="nsew")
        self.detail = detail
        self.d_title = tk.Label(
            detail, text="No session selected", fg=_INK, bg=_CARD,
            font=("Segoe UI", -20, "bold"), anchor="w", justify="left",
        )
        self.d_title.pack(fill="x", padx=12, pady=(12, 0))
        self.d_meta = tk.Label(
            detail, text="Choose one from the list. Legal sessions stay closed.",
            fg=_SECONDARY, bg=_CARD, font=_FONT_SMALL, anchor="w", justify="left",
        )
        self.d_meta.pack(fill="x", padx=12, pady=(4, 0))
        self.name_line = tk.Label(
            detail, text="", fg=_INK, bg=_CARD, font=_FONT, anchor="w", justify="left",
        )
        self.name_line.pack(fill="x", padx=12, pady=(4, 0))

        apps = tk.Frame(detail, bg=_CARD)
        apps.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(apps, text="App", fg=_SECONDARY, bg=_CARD, font=_FONT_SMALL).pack(side="left", padx=(0, 8))
        self.app_box = tk.OptionMenu(apps, self.app_var, "")
        self.app_box.configure(
            bg=_ELEVATED, fg=_INK, activebackground="#1E2430", activeforeground=_INK,
            relief="flat", highlightthickness=1, highlightbackground=_LINE,
            highlightcolor=_ACCENT, font=_FONT, bd=0,
        )
        self.app_box["menu"].configure(
            bg=_CARD, fg=_INK, activebackground=_ACCENT, activeforeground=_BG, bd=0, font=_FONT,
        )
        self.app_box.pack(side="left")

        cmd_shell = tk.Frame(detail, bg=_LINE, padx=1, pady=1)
        cmd_shell.pack(fill="x", padx=12, pady=(8, 0))
        self.cmd = tk.Label(
            cmd_shell, text="", fg=_MONO, bg=_BG, font=_FONT_MONO,
            anchor="w", justify="left", padx=10, pady=8,
        )
        self.cmd.pack(fill="x")
        self.preview = tk.Text(
            detail, height=8, wrap="word", bg=_BG, fg=_MONO, insertbackground=_INK,
            relief="flat", highlightthickness=1, highlightbackground=_LINE,
            highlightcolor=_ACCENT, font=_FONT_MONO, bd=0, padx=10, pady=8,
        )
        self.preview.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        self.preview.bind("<Key>", self._keep_preview)
        actions = tk.Frame(detail, bg=_CARD)
        actions.pack(fill="x", padx=12, pady=(8, 0))
        rows = (
            ("Load", self._on_load),
            ("Resume", self._on_resume),
            ("Launch", self._on_launch),
            ("Preview", self._on_preview),
            ("Name", self._on_name),
            ("Import", self._on_import),
            ("Export", self._on_export),
            ("Index", self._on_index),
            ("Formats", self._on_formats),
            ("Check recovery", self._on_recover),
            ("Restore", self._on_restore),
            ("Anonymize", self._on_anonymize),
            ("Check strip", self._on_strip_dry),
            ("Write strip", self._on_strip),
        )
        for index, (label, command) in enumerate(rows):
            self._button(actions, label, command).grid(
                row=index // 3, column=index % 3, padx=(0, 6), pady=(0, 6), sticky="ew",
            )
        for column in range(3):
            actions.columnconfigure(column, weight=1)
        self.out = tk.Text(
            detail, height=4, wrap="word", bg=_BG, fg=_QUIET, insertbackground=_INK,
            relief="flat", highlightthickness=1, highlightbackground=_LINE,
            highlightcolor=_ACCENT, font=_FONT_MONO, bd=0, padx=8, pady=6,
        )
        self.out.pack(fill="x", padx=12, pady=(4, 12))
        detail.bind("<Configure>", self._fit_detail)
        self._set_preview("Select a session to preview it. Legal sessions stay closed.")
        self._set_out("")

    def _fit_detail(self, event) -> None:
        if event.widget is not self.detail:
            return
        width = max(160, event.width - 36)
        for label in (self.d_title, self.d_meta, self.name_line, self.cmd):
            label.configure(wraplength=width)

    def _on_grid_configure(self, event, frame, cards, min_width: int, memo: str) -> None:
        if event.widget is not frame:
            return
        if abs(event.width - getattr(self, memo)) < 24:
            return
        setattr(self, memo, event.width)
        self._reflow(frame, cards, min_width)

    def _reflow(self, frame, cards, min_width: int) -> None:
        width = frame.winfo_width()
        if width < 80:
            width = 960
        cols = max(1, width // min_width)
        for card in cards:
            card.grid_forget()
        for index in range(8):
            frame.columnconfigure(index, weight=0)
        for index in range(cols):
            frame.columnconfigure(index, weight=1)
        for index, card in enumerate(cards):
            card.grid(row=index // cols, column=index % cols, sticky="nsew", padx=6, pady=6)

    def _on_chip_configure(self, event) -> None:
        if event.widget is not self.chip_frame:
            return
        if abs(event.width - self._chip_width) < 16:
            return
        self._chip_width = event.width
        self._reflow_chips()

    def _reflow_chips(self) -> None:
        width = self.chip_frame.winfo_width()
        if width < 40:
            width = 800
        cursor = 0
        row = 0
        col = 0
        for chip in self._chips:
            chip.grid_forget()
        for chip in self._chips:
            chip.update_idletasks()
            need = chip.winfo_reqwidth() + 8
            if cursor and cursor + need > width:
                row += 1
                col = 0
                cursor = 0
            chip.grid(row=row, column=col, sticky="w", padx=(0, 8), pady=(0, 8))
            col += 1
            cursor += need

    def _chip(self, text: str, on: bool, command):
        bg = _ELEVATED if on else _CARD
        fg = _ACCENT if on else _INK
        shell = self.tk.Frame(self.chip_frame, bg=_ACCENT if on else _LINE, padx=1, pady=1, cursor="hand2")
        label = self.tk.Label(
            shell, text=text, bg=bg, fg=fg, font=_FONT_SMALL, padx=10, pady=4, cursor="hand2",
        )
        label.pack()
        self._bind_click(shell, command)
        return shell

    def run(self) -> None:
        self.root.after(50, self._load_all)
        self.root.mainloop()

    def _say(self, text: str, tone: str = "") -> None:
        label = getattr(self, "say", None)
        if label is None:
            return
        if tone == "good":
            color = _READY
        elif tone == "warn":
            color = _NOT_READY
        elif tone == "bad":
            color = _BAD
        else:
            color = _SECONDARY
        label.configure(text=text, fg=color)
        status = getattr(self, "status", None)
        if status is not None:
            status.configure(text=text or "Ready", fg=color)

    def _set_out(self, text: str) -> None:
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.insert("1.0", text)

    def _keep_preview(self, event):
        ctrl = (event.state & 0x4) != 0
        if ctrl and event.keysym.lower() in ("c", "a", "insert"):
            return None
        if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "Tab"):
            return None
        return "break"

    def _set_preview(self, text: str) -> None:
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        sheets = getattr(self, "sheets", None)
        if sheets is not None:
            sheets.note_preview(text)
        widget = getattr(self, "ledger_session_text", None)
        if widget is not None:
            widget.delete("1.0", "end")
            widget.insert("1.0", text)

    def _show(self, obj: dict) -> None:
        shown = obj
        if isinstance(obj, dict) and isinstance(obj.get("result"), dict):
            shown = obj["result"]
        self._say(_sentence(shown), _tone(shown) if isinstance(shown, dict) else "")
        self._set_out(_dump(obj) if not isinstance(obj, str) else obj)

    def _selected(self) -> dict | None:
        index = self.selected_index
        if index is None or index < 0 or index >= len(self.hits):
            return None
        return self.hits[index]

    def _need_hit(self) -> dict | None:
        hit = self._selected()
        if hit is None:
            self._say("Select a session first.", "warn")
        return hit

    def _guard(self, fn) -> None:
        if self.busy:
            return
        self.busy = True
        self.root.config(cursor="watch")
        try:
            fn()
        except engine.PageError as exc:
            self._say(f"{exc.kind}: {exc}", "bad")
            self._set_out(_dump({"kind": exc.kind, "detail": str(exc)}))
        except Exception as exc:  # noqa: BLE001
            self._say(f"{type(exc).__name__}: {exc}", "bad")
            self._set_out(_dump({"kind": "ERROR", "detail": f"{type(exc).__name__}: {exc}"}))
        finally:
            self.busy = False
            try:
                self.root.config(cursor="")
            except self.tk.TclError:
                pass

    def _load_all(self) -> None:
        self._job += 1
        job = self._job
        query = self.query.get().strip()
        harness = self.filter_harness
        drive = self.filter_drive
        self._say("Reading drives…")
        threading.Thread(
            target=self._bg_load, args=(job, query, harness, drive), daemon=True,
        ).start()

    def _bg_load(self, job: int, query: str, harness: str, drive: str) -> None:
        self._offer_saved(job)
        if job != self._job:
            return
        try:
            placed = engine.places()
            error = ""
        except Exception as exc:  # noqa: BLE001 — show it on the window thread
            placed = None
            error = f"{type(exc).__name__}: {exc}"
        if job != self._job:
            return
        self.root.after(0, lambda j=job, p=placed, e=error: self._apply_places(j, p, e))
        self._bg_find(job, query, harness, drive)

    def _offer_saved(self, job: int) -> None:
        reader = getattr(engine, "read_saved_index", None)
        if not callable(reader):
            return
        try:
            saved = reader()
        except Exception:  # noqa: BLE001 — a missing index must not block the walk
            return
        if job != self._job or not _index_hits(saved):
            return
        self.root.after(0, lambda j=job, s=saved: self._apply_saved(j, s))

    def _apply_saved(self, job: int, saved) -> None:
        if job != self._job:
            return
        hits = _index_hits(saved)
        if not hits:
            return
        self._hold_lead = True
        self._show_found(_saved_record(saved, hits))
        self.lead.configure(text="Showing the last index. Refreshing…")

    def _apply_places(self, job: int, placed, error: str) -> None:
        if job != self._job:
            return
        if error or not isinstance(placed, dict):
            self._say(error or "Drives could not be read.", "bad")
            return
        drives = [row for row in (placed.get("drives") or []) if isinstance(row, dict)]
        homes = [row for row in (placed.get("homes") or []) if isinstance(row, dict)]
        present = sum(1 for row in homes if row.get("present"))
        if not self._hold_lead:
            self.lead.configure(text=f"{len(drives)} drives. {present} locations present.")
        self._replace_cards(self.drive_grid, self._drive_cards, drives, self._drive_card, 270, "_drive_width")
        self._replace_cards(
            self.location_grid, self._location_cards, homes, self._location_card, 340, "_location_width",
        )
        self._say(f"{len(drives)} drives. {present} locations present. Walking sessions in the background.")

    def _fill(self) -> None:
        self._load_all()

    def _on_quit(self) -> None:
        self.root.destroy()

    def _load_places(self) -> None:
        self._load_all()

    def _replace_cards(self, frame, cards, rows, builder, min_width: int, memo: str) -> None:
        for card in cards:
            card.destroy()
        cards.clear()
        for row in rows:
            cards.append(builder(frame, row))
        setattr(self, memo, -1)
        self._reflow(frame, cards, min_width)

    def _drive_card(self, parent, drive: dict):
        view = _drive_view(drive)
        ready = view["status"] == "READY"
        bg = _CARD
        shell = self.tk.Frame(parent, bg=_LINE, padx=1, pady=1, cursor="hand2")
        card = self.tk.Frame(shell, bg=bg, padx=12, pady=10, cursor="hand2")
        card.pack(fill="both", expand=True)
        top = self.tk.Frame(card, bg=bg)
        top.pack(fill="x")
        dot = self.tk.Canvas(top, width=12, height=12, bg=bg, highlightthickness=0, bd=0)
        dot.create_oval(2, 2, 10, 10, fill=_READY if ready else _NOT_READY, outline="")
        dot.pack(side="left", padx=(0, 8), pady=6)
        letter = self.tk.Label(
            top, text=view["letter"], fg=_ACCENT if ready else _QUIET, bg=bg, font=_FONT_LETTER,
        )
        letter.pack(side="left")
        status = self.tk.Label(
            top, text=view["status"], fg=_READY if ready else _NOT_READY, bg=bg, font=_FONT_TAG,
        )
        status.pack(side="right")
        label = view["label"] or (f"{view['letter']} drive" if view["letter"] else "Drive")
        self.tk.Label(
            card, text=label, fg=_INK if ready else _SECONDARY, bg=bg, anchor="w", font=_FONT,
        ).pack(fill="x", pady=(6, 0))
        bits = [bit for bit in (view["kind"], view["fs"], view["free_text"]) if bit]
        self.tk.Label(
            card, text="  ·  ".join(bits), fg=_SECONDARY if ready else _QUIET, bg=bg,
            anchor="w", font=_FONT_SMALL,
        ).pack(fill="x")
        if view["used"] is not None:
            meter = self.tk.Canvas(card, height=6, bg=_BG, highlightthickness=0, bd=0)
            meter.pack(fill="x", pady=(8, 2))
            fraction = view["used"]

            def draw(event, canvas=meter, frac=fraction):
                canvas.delete("all")
                width = max(event.width, 0)
                canvas.create_rectangle(0, 0, width, 6, fill=_BG, outline="")
                canvas.create_rectangle(0, 0, max(0, int(width * frac)), 6, fill=_ACCENT, outline="")

            meter.bind("<Configure>", draw)
        ident = str(drive.get("id") or "")
        self._bind_click(shell, lambda i=ident: self._use_drive(i))
        return shell

    def _location_card(self, parent, home: dict):
        view = _home_view(home)
        present = view["status"] == "PRESENT"
        bg = _CARD
        shell = self.tk.Frame(parent, bg=_LINE, padx=1, pady=1, cursor="hand2")
        card = self.tk.Frame(shell, bg=bg, padx=12, pady=10, cursor="hand2")
        card.pack(fill="both", expand=True)
        top = self.tk.Frame(card, bg=bg)
        top.pack(fill="x")
        dot = self.tk.Canvas(top, width=12, height=12, bg=bg, highlightthickness=0, bd=0)
        dot.create_oval(2, 2, 10, 10, fill=_READY if present else _QUIET, outline="")
        dot.pack(side="left", padx=(0, 8))
        self.tk.Label(
            top, text=view["harness"], fg=_INK if present else _QUIET, bg=bg,
            font=("Segoe UI", -15, "bold"),
        ).pack(side="left")
        self.tk.Label(
            top, text=view["status"], fg=_READY if present else _QUIET, bg=bg, font=_FONT_TAG,
        ).pack(side="right")
        self.tk.Label(
            card, text=view["where"], fg=_MONO if present else _QUIET, bg=bg,
            anchor="w", justify="left", font=_FONT_MONO, wraplength=420,
        ).pack(fill="x", pady=(6, 0))
        harness = view["harness"]
        self._bind_click(shell, lambda name=harness: self._use_home(name))
        return shell

    def _use_drive(self, ident: str) -> None:
        self.filter_drive = ident
        self.filter_harness = ""
        self._show_view("sessions")
        self._run_find()

    def _use_home(self, name: str) -> None:
        self.filter_harness = name
        self.filter_drive = ""
        self._show_view("sessions")
        self._run_find()

    def _clear_drive(self) -> None:
        self.filter_drive = ""
        self.root.after(1, self._run_find)

    def _set_harness(self, name: str) -> None:
        self.filter_harness = name
        self.root.after(1, self._run_find)

    def _run_find(self) -> None:
        self._kick_find()

    def _drain_find(self) -> None:
        self._kick_find()

    def _kick_find(self) -> None:
        self._job += 1
        job = self._job
        query = self.query.get().strip()
        harness = self.filter_harness
        drive = self.filter_drive
        if hasattr(self, "count"):
            self.count.configure(text="Looking…")
        threading.Thread(
            target=self._bg_find, args=(job, query, harness, drive), daemon=True,
        ).start()

    def _bg_find(self, job: int, query: str, harness: str, drive: str) -> None:
        if job != self._job:
            return
        try:
            rec = engine.find(
                query=query, harness=harness, drive=drive,
                limit=engine.DEFAULT_LIMIT, enrich=False,
            )
            error = ""
        except Exception as exc:  # noqa: BLE001
            rec = None
            error = f"{type(exc).__name__}: {exc}"
        if job != self._job:
            return
        self.root.after(0, lambda j=job, r=rec, e=error: self._apply_find(j, r, e))

    def _apply_find(self, job: int, rec, error: str) -> None:
        if job != self._job:
            return
        self._hold_lead = False
        if error or not isinstance(rec, dict):
            self._say(error or "The walk failed.", "bad")
            self.count.configure(text="Walk failed.")
            self.lead.configure(text="Walk failed.")
            return
        self._show_found(rec)
        self.lead.configure(text=self.count.cget("text"))

    def _load_sessions(self) -> None:
        self._kick_find()

    def _show_found(self, rec: dict) -> None:
        previous = None
        if self.selected_index is not None and 0 <= self.selected_index < len(self.hits):
            previous = self.hits[self.selected_index].get("id")
        self.hits = [hit for hit in (rec.get("hits") or []) if isinstance(hit, dict)]
        gate = rec.get("gate") if isinstance(rec.get("gate"), dict) else {}
        n = gate.get("n") if "n" in gate else rec.get("n")
        shown = gate.get("n_shown") if "n_shown" in gate else len(self.hits)
        legal = rec.get("legal_omitted") or 0
        self.count.configure(text=f"{n} sessions. Showing {shown}. Legal left closed: {legal}.")
        self.selected_index = None
        for index, hit in enumerate(self.hits):
            if previous is not None and hit.get("id") == previous:
                self.selected_index = index
                break
        self._paint_hits()
        if getattr(self, "sheets", None) is not None:
            self.sheets.refresh(self.hits)
        if getattr(self, "ledger_mounted", False):
            import ledger
            ledger.refresh(self, self.hits)
        families = gate.get("families") if isinstance(gate.get("families"), list) else []
        self._paint_chips(families)
        if self.selected_index is None:
            self._preview_id = ""
            self._preview_turns = None
            self._paint_detail()
            self._set_preview("Select a session to preview it. Legal sessions stay closed.")

    def _paint_chips(self, families) -> None:
        for chip in self._chips:
            chip.destroy()
        self._chips = []
        if self.filter_drive:
            self._chips.append(self._chip(
                f"Drive {self.filter_drive}  ×", True, self._clear_drive,
            ))
        self._chips.append(self._chip("All", not self.filter_harness, lambda: self._set_harness("")))
        for label, name in _chip_specs(families):
            self._chips.append(self._chip(
                label, self.filter_harness == name, lambda n=name: self._set_harness(n),
            ))
        self._chip_width = -1
        self._reflow_chips()

    def _paint_hits(self) -> None:
        self._paint_token += 1
        token = self._paint_token
        job = self._job
        for child in self.list_inner.winfo_children():
            child.destroy()
        self._row_widgets = []
        self._paint_at = 0
        if not self.hits:
            self.tk.Label(
                self.list_inner, text="No sessions.", fg=_QUIET, bg=_CARD, font=_FONT, anchor="w",
            ).pack(fill="x", padx=12, pady=12)
            return
        self._paint_batch(job, token)

    def _paint_batch(self, job: int, token: int) -> None:
        if job != self._job or token != self._paint_token:
            return
        end = min(len(self.hits), self._paint_at + 30)
        for index in range(self._paint_at, end):
            row = self._hit_row(self.hits[index], index)
            row.pack(fill="x")
            self.tk.Frame(self.list_inner, bg=_LINE, height=1).pack(fill="x")
            self._row_widgets.append(row)
        self._paint_at = end
        self._tint_rows()
        if self._paint_at < len(self.hits):
            self.root.after(1, lambda j=job, t=token: self._paint_batch(j, t))

    def _hit_row(self, hit: dict, index: int):
        tk = self.tk
        row = tk.Frame(self.list_inner, bg=_CARD, cursor="hand2")
        bar = tk.Frame(row, bg=_CARD, width=3)
        bar.pack_propagate(False)
        bar.pack(side="left", fill="y")
        body = tk.Frame(row, bg=_CARD, cursor="hand2")
        body.pack(side="left", fill="both", expand=True, padx=10, pady=8)
        body.columnconfigure(1, weight=1)
        harness = tk.Label(
            body, text=str(hit.get("harness") or "").upper(), fg=_ACCENT, bg=_CARD,
            font=_FONT_TAG, anchor="nw", justify="left", wraplength=110, cursor="hand2",
        )
        title = "Legal session" if hit.get("legal") else str(
            hit.get("title") or hit.get("vendor_id") or hit.get("id") or ""
        )
        title_l = tk.Label(
            body, text=title, fg=_INK, bg=_CARD, font=_FONT, anchor="w",
            justify="left", cursor="hand2",
        )
        when_l = tk.Label(
            body, text=_when(hit.get("updated")), fg=_QUIET, bg=_CARD,
            font=_FONT_MONO, anchor="w", cursor="hand2",
        )
        harness.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 10))
        title_l.grid(row=0, column=1, sticky="ew")
        when_l.grid(row=1, column=1, sticky="ew")

        def fit(event, label=title_l):
            label.configure(wraplength=max(80, event.width - 130))

        body.bind("<Configure>", fit)
        row._bar = bar
        row._surfaces = [row, body, harness, title_l, when_l]
        self._bind_click(row, lambda i=index: self._select(i))
        return row

    def _tint_rows(self) -> None:
        for index, row in enumerate(self._row_widgets):
            on = index == self.selected_index
            bg = _ELEVATED if on else _CARD
            row._bar.configure(bg=_ACCENT if on else bg)
            for widget in row._surfaces:
                widget.configure(bg=bg)

    def _select(self, index: int) -> None:
        if index < 0 or index >= len(self.hits):
            return
        self.selected_index = index
        self._preview_id = ""
        self._preview_turns = None
        self._tint_rows()
        self._paint_detail()
        hit = self.hits[index]
        if hit.get("legal"):
            self._set_preview("Legal session stays closed.")
            self._say("Legal session stays closed.", "bad")
            self._set_out("Legal session stays closed.")
            return
        self._set_preview("Reading a short preview…")
        if getattr(self, "ledger_mounted", False):
            import ledger_session
            ledger_session.fill(self, hit)
        rec_id = str(hit.get("id") or "")
        self.root.after(1, lambda i=index, rid=rec_id: self._fetch_preview(i, rid))

    def _paint_detail(self) -> None:
        hit = self._selected()
        self.name_line.configure(text="")
        if hit is None:
            self.d_title.configure(text="No session selected")
            self.d_meta.configure(text="Choose one from the list. Legal sessions stay closed.")
            self.cmd.configure(text="")
            return
        ident = str(hit.get("id") or "")
        harness = str(hit.get("harness") or "")
        self.d_title.configure(text=ident or "No session selected")
        bits = [harness]
        if hit.get("legal"):
            bits.append("Legal session")
        else:
            title = str(hit.get("title") or "").strip()
            if title:
                bits.append(title)
            path = str(hit.get("path") or "").strip()
            if path:
                bits.append(path)
        self.d_meta.configure(text="   ·   ".join(bit for bit in bits if bit))
        self._set_app_choices(hit)

    def _set_app_choices(self, hit: dict) -> None:
        harness = str(hit.get("harness") or "")
        choices = list(RESUME_APPS)
        if harness and harness not in choices:
            choices.append(harness)
        menu = self.app_box["menu"]
        menu.delete(0, "end")
        for choice in choices:
            menu.add_command(label=choice, command=lambda c=choice: self.app_var.set(c))
        self._painting = True
        try:
            self.app_var.set(harness)
        finally:
            self._painting = False
        self._paint_plan()

    def _on_app_change(self, *_args) -> None:
        if self._painting:
            return
        self._paint_plan()

    def _paint_plan(self) -> None:
        hit = self._selected()
        if hit is None or not hasattr(self, "cmd"):
            return
        plan = plan_resume(hit, self._picked_app(hit))
        argv = plan.get("argv")
        if isinstance(argv, list) and argv:
            text = " ".join(str(tok) for tok in argv)
        elif plan.get("detail"):
            text = str(plan["detail"])
        else:
            text = str(plan.get("kind") or "UNMEASURED")
        self.cmd.configure(text=text)

    def _picked_app(self, hit: dict) -> str:
        return self.app_var.get().strip().lower() or str(hit.get("harness") or "")

    def _fetch_preview(self, index: int, rec_id: str) -> None:
        hit = self._selected()
        if hit is None or self.selected_index != index or str(hit.get("id") or "") != rec_id:
            return
        if hit.get("legal"):
            self._set_preview("Legal session stays closed.")
            self._say("Legal session stays closed.", "bad")
            return
        def work() -> None:
            try:
                rec = engine.dispatch("preview", {"id": rec_id})
                error = None
            except engine.PageError as exc:
                rec = None
                error = exc
            self.root.after(0, lambda: self._finish_preview(index, rec_id, rec, error))

        threading.Thread(target=work, daemon=True).start()

    def _finish_preview(self, index: int, rec_id: str, rec, error) -> None:
        current = self._selected()
        if current is None or self.selected_index != index or str(current.get("id") or "") != rec_id:
            return
        if error is not None:
            self._preview_id = rec_id
            self._preview_turns = None
            self._say(f"{error.kind}: {error}", "bad")
            self._set_out(_dump({"kind": error.kind, "detail": str(error)}))
            self._set_preview(f"{error.kind}\n{error}")
            return
        self._apply_preview(current, rec)

    def _apply_preview(self, hit: dict, rec: dict) -> None:
        gate = rec.get("gate") if isinstance(rec.get("gate"), dict) else {}
        n = gate.get("n_turns")
        self._preview_id = str(hit.get("id") or "")
        self._preview_turns = n if isinstance(n, int) and not isinstance(n, bool) else None
        self._set_preview(_preview_body(rec))
        self._say(_sentence(rec), _tone(rec))
        self._set_out(_sentence(rec))

    def _on_load(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return

        def go() -> None:
            plan = plan_load(hit)
            rec = engine.dispatch("load", {"id": str(hit.get("id") or "")})
            self._show({"plan": plan, "result": rec})

        self._guard(go)

    def _on_resume(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return
        self._show(plan_resume(hit, self._picked_app(hit)))

    def _on_launch(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return
        app = self._picked_app(hit)
        harness = str(hit.get("harness") or "")
        if harness and _family(app) != _family(harness):
            plan = plan_foreign_launch(hit, app)
            if plan.get("kind") != "HANDOFF":
                shown = dict(plan)
                shown["launched"] = False
                self._show(shown)
                return
            self._guard(lambda: self._start_handoff(hit, plan))
            return

        def go() -> None:
            rec = engine.resume(str(hit.get("id") or ""), launch=True)
            self._show(rec)

        self._guard(go)

    def _start_handoff(self, hit: dict, plan: dict) -> None:
        """Export, then start the bare app. No -p and no session id."""
        exported = engine.dispatch("export", {"id": str(hit.get("id") or "")})
        argv = [str(tok) for tok in (plan.get("argv") or [])][:1]
        bare = argv[0] if argv else ""
        binary = shutil.which(bare) if bare else None
        if not binary:
            self._show({"kind": "BINARY_ABSENT", "argv": argv, "export": exported})
            return
        cwd = hit.get("cwd") or None
        flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        proc = subprocess.Popen([binary], cwd=cwd, creationflags=flags, close_fds=True)
        gate = exported.get("gate") if isinstance(exported.get("gate"), dict) else {}
        self._show({
            "kind": "HANDOFF",
            "export": gate.get("out") or "",
            "argv": [binary],
            "pid": proc.pid,
            "export_result": exported,
        })

    def _on_preview(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return
        self._set_preview("Reading a short preview…")
        self._fetch_preview(self.selected_index, str(hit.get("id") or ""))

    def _on_name(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return

        def go() -> None:
            # Imported here, not at module import. No transcript is sent.
            try:
                import name_model
            except ImportError:
                self._say("Naming is off.")
                self._set_out("Naming is off.")
                return
            fn = getattr(name_model, "maybe_name", None)
            if not callable(fn):
                self._say("Naming is off.")
                self._set_out("Naming is off.")
                return
            payload = {
                "vendor": str(hit.get("vendor_id") or ""),
                "session_id": str(hit.get("id") or ""),
                "harness": str(hit.get("harness") or ""),
                "title": "untitled",
                "date": _hit_date(hit),
            }
            if self._preview_id == payload["session_id"] and isinstance(self._preview_turns, int):
                payload["turns"] = self._preview_turns
            result = _call_maybe_name(fn, payload)
            if result is None:
                self._say("Naming is off.")
                self._set_out("Naming is off.")
                return
            text = _name_text(result)
            if not text:
                self._say("Naming is off.")
                self._set_out("Naming is off.")
                return
            self.name_line.configure(text=text)
            self._say(text, "good")
            self._set_out(text)

        self._guard(go)

    def _on_import(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return

        def go() -> None:
            rec = engine.dispatch("import", {"id": str(hit.get("id") or "")})
            self._say("The source was left in place.", _tone(rec))
            self._set_out("The source was left in place.\n\n" + _dump(rec))

        self._guard(go)

    def _on_export(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return

        def go() -> None:
            rec = engine.dispatch("export", {"id": str(hit.get("id") or "")})
            self._show(rec)

        self._guard(go)

    def _on_index(self) -> None:
        def go() -> None:
            rec = engine.dispatch("index")
            gate = rec.get("gate") if isinstance(rec.get("gate"), dict) else {}
            self._say(_sentence(rec), _tone(rec))
            self._set_out(f"n {gate.get('n')}\n\n{_dump(rec)}")

        self._guard(go)

    def _on_formats(self) -> None:
        def go() -> None:
            rec = engine.dispatch("formats")
            gate = rec.get("gate") if isinstance(rec.get("gate"), dict) else {}
            lines = [str(rec.get("kind") or "")]
            for row in gate.get("formats") or []:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"{row.get('harness') or ''}  {row.get('load') or ''}  {row.get('resume') or ''}"
                )
            self._say(lines[0] or "Formats", _tone(rec))
            self._set_out("\n".join(lines))

        self._guard(go)

    def _hit_path(self, hit: dict) -> str:
        return str(hit.get("path") or "").strip()

    def _on_recover(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return
        path = self._hit_path(hit)
        if not path:
            self._set_out("This session has no path.")
            self._say("This session has no path.", "warn")
            return

        def go() -> None:
            rec = engine.dispatch("recover", {"path": path, "apply": False})
            self._show(rec)

        self._guard(go)

    def _on_restore(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return
        path = self._hit_path(hit)
        if not path:
            self._set_out("This session has no path.")
            self._say("This session has no path.", "warn")
            return
        from tkinter import messagebox
        if not messagebox.askyesno(
            "Restore",
            "Replace this file with the backup beside it?",
            parent=self.root,
        ):
            return

        def go() -> None:
            rec = engine.dispatch("recover", {"path": path, "apply": True})
            self._show(rec)

        self._guard(go)

    def _on_anonymize(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return

        def go() -> None:
            rec = engine.dispatch("anonymize", {"id": str(hit.get("id") or "")})
            self._show(rec)

        self._guard(go)

    def _on_strip_dry(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return
        rec_id = str(hit.get("id") or "")

        def go() -> None:
            rec = engine.dispatch("strip_dry", {"id": rec_id})
            if rec.get("kind") == "OK":
                self.strip_ok = rec_id
            elif self.strip_ok == rec_id:
                self.strip_ok = ""
            self._show(rec)

        self._guard(go)

    def _on_strip(self) -> None:
        hit = self._need_hit()
        if hit is None:
            return
        rec_id = str(hit.get("id") or "")
        if self.strip_ok != rec_id:
            self._set_out("Check strip has to succeed first.")
            self._say("Check strip has to succeed first.", "warn")
            return

        def go() -> None:
            rec = engine.dispatch("strip", {"id": rec_id})
            self._show(rec)

        self._guard(go)


def main(argv=None) -> int:
    """Open the desk. Does not bind a socket. argv is accepted and ignored."""
    del argv
    if not claim_instance():
        try:
            import ctypes
            user32 = ctypes.WinDLL("user32")
            user32.MessageBoxW.argtypes = (
                ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
            )
            user32.MessageBoxW.restype = ctypes.c_int
            user32.MessageBoxW(None, "Sessions is already open.", "Sessions", 0)
        except Exception:  # noqa: BLE001
            pass
        return 0
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"Sessions desk needs tkinter ({type(exc).__name__}).\n")
        return 2
    _Desk(tk, ttk).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
