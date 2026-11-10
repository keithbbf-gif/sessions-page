"""Table View window, drawn from the 642 scan.

The 642 portrait sketch (rotated to landscape) is the frame of the app:

- Top nav: Home, DRIVES, SESSIONS, a session-tab carousel with < >,
  column toggles, Maker filter, Group menu, Create summaries, More.
- Column heads with a red rule: TOPICS, session Summaries, Proj,
  Token count, cost $, TAG.
- Body: left session list with ages, center TABLE VIEW, right
  Daily / Weekly / Monthly / Quarterly summaries, far-right rail
  (SAVE AS, LOAD OPEN, search, calendar, Project folder View).
- Footer: Solaro sun beside the username, status line, estimate note.

The single-session, calendar, and project drawings live inside the
center column only. The left list, summaries, and rail stay visible.

Stdlib and tkinter only. Reads the hits it is given.
"""

from __future__ import annotations

import importlib.util
import threading
from datetime import datetime, timedelta
from pathlib import Path

BG = "#07080A"
CARD = "#12151C"
INK = "#E8ECF4"
QUIET = "#6B7386"
LINE = "#2A3140"
ACCENT = "#7C9CFF"
RED = "#E5484D"
EM = "\u2014"

_RATES = {
    # key: (usd per 1M input tokens, usd per 1M output tokens).
    # Estimate only. Not a bill. Token Center is not connected.
    "grok": (2.0, 6.0),
    "claude": (2.0, 10.0),
    "claude-opus": (4.0, 20.0),
    "claude-haiku": (0.10, 0.50),
    "codex": (1.25, 10.0),
    "gemini": (0.30, 2.50),
    "gemini-pro": (1.25, 10.0),
    "antigravity": (0.30, 2.50),
}

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
    "cursor": "#A5B4FC",
    "agent": "#A5B4FC",
    "hermes": "#F9A8D4",
    "openwork": "#F0ABFC",
    "cowork": "#F0ABFC",
}


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
        try:
            return fn(harness)
        except Exception:
            pass
    return _VCOLOR.get(str(harness or "").lower(), "#A7B0C3")


def title_of(hit: dict) -> str:
    fn = _use("title_of")
    if fn is not None:
        try:
            return str(fn(hit))
        except Exception:
            pass
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "Untitled")


def project_of(hit: dict) -> str:
    fn = _use("project_of")
    if fn is not None:
        try:
            return str(fn(hit))
        except Exception:
            pass
    if hit.get("legal"):
        return ""
    cwd = str(hit.get("cwd") or "").replace("/", "\\").rstrip("\\")
    return "" if not cwd else cwd.split("\\")[-1]


def source_label(hit: dict) -> str:
    fn = _use("source_label")
    if fn is not None:
        try:
            return str(fn(hit))
        except Exception:
            pass
    name = str(hit.get("harness") or "")
    if name == "grok":
        return "Grok.exe"
    if name.startswith("antigravity") or name == "agy":
        return "Antigravity.exe"
    return name or "App"


def source_kind(hit: dict) -> str:
    fn = _use("source_kind")
    if fn is not None:
        try:
            return str(fn(hit))
        except Exception:
            pass
    name = str(hit.get("harness") or "")
    if name in ("claude_desktop", "openwork", "cowork"):
        return "Chat"
    if name == "antigravity-ide":
        return "TUI"
    return "CLI"


def age_text(stamp) -> str:
    fn = _use("age_text")
    if fn is not None:
        try:
            return str(fn(stamp))
        except Exception:
            pass
    if stamp is None or isinstance(stamp, bool):
        return EM
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return EM
    if n != n or n < 0:
        return EM
    if n > 100_000_000_000:
        n = n / 1000.0
    try:
        mins = max(0, int((datetime.now().timestamp() - n) // 60))
    except (OSError, OverflowError, ValueError):
        return EM
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    if hours < 24:
        return f"{hours}hr" if hours < 10 else f"{hours}hrs"
    days = hours // 24
    if days < 14:
        return "1 day" if days == 1 else f"{days} days"
    weeks = days // 7
    if weeks < 8:
        return f"{weeks} wks"
    months = max(1, days // 30)
    return "1 month" if months == 1 else f"{months} months"


def _harness(hit: dict) -> str:
    raw = hit.get("harness")
    if raw is None or str(raw).strip() == "":
        raw = hit.get("vendor")
    return str(raw or "").strip()


def _topic_text(hit: dict) -> str:
    if hit.get("legal"):
        return ""
    for key in ("topic", "topics"):
        raw = hit.get(key)
        if isinstance(raw, str) and raw.strip():
            return " ".join(raw.split())
        if isinstance(raw, (list, tuple)):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    return " ".join(item.split())
    return ""


def _tokens_of(hit: dict):
    """Return (tokens, basis) where basis is counted, sized, or empty."""
    if hit.get("input_tokens") or hit.get("output_tokens"):
        try:
            total = float(hit.get("input_tokens") or 0) + float(hit.get("output_tokens") or 0)
            return total, "counted"
        except (TypeError, ValueError):
            pass
    for key in ("tokens", "token_count", "n_tokens"):
        try:
            return float(hit[key]), "counted"
        except (TypeError, ValueError, KeyError):
            continue
    try:
        size = int(hit.get("bytes") or 0)
    except (TypeError, ValueError):
        size = 0
    if size > 0 and not isinstance(hit.get("bytes"), bool):
        return size / 4.0, "sized"
    return None, ""


def _rate_key(hit: dict) -> str:
    harness = _harness(hit).lower()
    model = str(hit.get("model") or "").lower()
    if harness in ("claude", "claude_desktop"):
        if "opus" in model:
            return "claude-opus"
        if "haiku" in model:
            return "claude-haiku"
        return "claude"
    if harness == "codex":
        return "codex"
    if harness in ("antigravity", "antigravity-ide", "antigravity-cli", "agy"):
        return "antigravity"
    if harness == "gemini":
        return "gemini-pro" if "pro" in model else "gemini"
    if harness == "grok":
        return "grok"
    return ""


def _cost_text(hit: dict) -> str:
    tokens, _basis = _tokens_of(hit)
    if not tokens or tokens <= 0:
        return EM
    rate = _RATES.get(_rate_key(hit))
    if not rate:
        return EM
    blended = 0.75 * rate[0] + 0.25 * rate[1]
    dollars = tokens * blended / 1_000_000
    if dollars < 0.01:
        return "<$0.01"
    return f"~${dollars:,.2f}"


def _tokens_text(hit: dict) -> str:
    tokens, basis = _tokens_of(hit)
    if tokens and tokens > 0 and basis == "counted":
        return f"{int(tokens)} tok"
    size = hit.get("bytes")
    if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
        if size >= 1024:
            return f"{max(1, size // 1024)} KB"
        return f"{size} B"
    return EM


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
    return " ".join(str(p) for p in parts if p).lower()


def _query(desk) -> str:
    var = getattr(desk, "query", None)
    if var is None:
        return ""
    try:
        return str(var.get()).strip().lower()
    except Exception:
        return ""


def _makers(desk) -> set[str] | None:
    chosen = getattr(desk, "ledger_makers", None)
    if not chosen:
        return None
    return {str(m).lower() for m in chosen}


def _visible(desk, hits) -> list:
    makers = _makers(desk)
    query = _query(desk)
    rows = []
    for hit in hits or ():
        if not isinstance(hit, dict):
            continue
        if makers and _harness(hit).lower() not in makers:
            continue
        if query and query not in _haystack(hit):
            continue
        rows.append(hit)
    return rows


def _mode(desk) -> str:
    mode = str(getattr(desk, "ledger_group", "flat") or "flat").strip().lower()
    return mode if mode in ("maker", "project", "topic") else "flat"


def _group_label(hit: dict, mode: str) -> str:
    if mode == "maker":
        return _harness(hit) or "other"
    if mode == "project":
        return project_of(hit) or "No project"
    return _topic_text(hit) or project_of(hit) or "No topic"


def _sort(rows: list, mode: str) -> list:
    if mode == "flat":
        return list(rows)
    return sorted(rows, key=lambda h: (_group_label(h, mode).casefold(), title_of(h).casefold()))


def _idx_of(desk, hit: dict):
    rows = getattr(desk, "hits", None) or []
    for i, row in enumerate(rows):
        if row is hit:
            return i
    ident = hit.get("id")
    if ident in (None, ""):
        return None
    for i, row in enumerate(rows):
        if isinstance(row, dict) and row.get("id") == ident:
            return i
    return None


def _open_hit(desk, hit: dict) -> None:
    index = _idx_of(desk, hit)
    if index is None:
        return
    select = getattr(desk, "_select", None)
    if callable(select):
        select(index)
    _show_body(desk, "session")


def mount(desk, stage):
    tk = desk.tk
    try:
        ttk_mod = getattr(desk, "ttk", None)
        if ttk_mod is None:
            from tkinter import ttk as ttk_mod
        ttk_mod.Style().theme_use("clam")
    except Exception:
        pass
    stage.configure(bg=BG)
    if not getattr(desk, "ledger_group", None):
        desk.ledger_group = "flat"
    if getattr(desk, "ledger_makers", None) is None:
        desk.ledger_makers = set()
    if not getattr(desk, "ledger_scope", None):
        desk.ledger_scope = "sessions"
    if not getattr(desk, "ledger_colvis", None):
        desk.ledger_colvis = {"proj": True, "tokens": True, "cost": True, "tag": True}
    desk.ledger_tabstart = 0
    desk.ledger_body = "table"
    desk.ledger_body_frames = {}
    desk.ledger_group_buttons = {}

    root = tk.Frame(stage, bg=BG)
    root.pack(fill="both", expand=True)
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(3, weight=1)

    _mount_nav(desk, tk, root).grid(row=0, column=0, sticky="ew")
    _mount_tabs(desk, tk, root).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
    _mount_heads(desk, tk, root).grid(row=2, column=0, sticky="ew")

    body = tk.Frame(root, bg=BG)
    body.grid(row=3, column=0, sticky="nsew")
    body.grid_columnconfigure(0, weight=0, minsize=220)
    body.grid_columnconfigure(1, weight=1, minsize=380)
    body.grid_columnconfigure(2, weight=0, minsize=200)
    body.grid_columnconfigure(3, weight=0, minsize=150)
    body.grid_rowconfigure(0, weight=1)

    left = tk.Frame(body, bg=CARD)
    left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
    center = tk.Frame(body, bg=BG)
    center.grid(row=0, column=1, sticky="nsew", padx=4, pady=8)
    right = tk.Frame(body, bg=CARD)
    right.grid(row=0, column=2, sticky="nsew", padx=(4, 4), pady=8)
    rail = tk.Frame(body, bg=CARD)
    rail.grid(row=0, column=3, sticky="nsew", padx=(4, 8), pady=8)
    desk.ledger_center = center
    desk.ledger_right = right
    desk.ledger_rail = rail

    _mount_left(desk, tk, left)
    _mount_table_frame(desk, tk, center)
    _mount_right(desk, tk, right)
    _mount_rail(desk, tk, rail)
    _mount_foot(desk, tk, root).grid(row=4, column=0, sticky="ew")

    desk.show_ledger_body = lambda name="table": _show_body(desk, name)
    _mirror_say(desk)
    desk.ledger_mounted = True
    desk.ledger_refresh = lambda *a, **k: refresh(desk, getattr(desk, "hits", []) or [])
    _show_body(desk, "table")
    refresh(desk, getattr(desk, "hits", []) or [])
    return stage


def _btn(tk, parent, text, command, on=False, small=False):
    return tk.Button(
        parent, text=text, command=command,
        bg=ACCENT if on else "#1E2430", fg=BG if on else INK,
        activebackground=ACCENT, activeforeground=BG,
        relief="flat", bd=0, highlightthickness=1,
        highlightbackground=LINE, highlightcolor=ACCENT,
        font=("Segoe UI", -12 if small else -13),
        padx=8, pady=3, cursor="hand2",
    )


def _mount_nav(desk, tk, root):
    bar = tk.Frame(root, bg=CARD)
    _btn(tk, bar, "\u2302 Home", lambda: _show_body(desk, "table")).pack(side="left", padx=(8, 2), pady=8)
    desk.ledger_scope_buttons = {}
    for scope, label in (("drives", "DRIVES"), ("sessions", "SESSIONS")):
        btn = _btn(tk, bar, label, lambda s=scope: _set_scope(desk, s),
                   on=(getattr(desk, "ledger_scope", "sessions") == scope))
        btn.pack(side="left", padx=2, pady=8)
        desk.ledger_scope_buttons[scope] = btn
    tk.Frame(bar, bg=LINE, width=1).pack(side="left", fill="y", padx=6, pady=10)
    desk.ledger_maker_btn = _btn(tk, bar, "Maker: All \u25be",
                                 lambda: _popup_makers(desk), small=True)
    desk.ledger_maker_btn.pack(side="left", padx=2, pady=8)
    desk.ledger_group_btn = _btn(tk, bar, "Group: Flat \u25be",
                                 lambda: _popup_group(desk), small=True)
    desk.ledger_group_btn.pack(side="left", padx=2, pady=8)
    desk.ledger_col_buttons = {}
    for key, label in (("proj", "Proj"), ("tokens", "Tokens"),
                       ("cost", "Cost"), ("tag", "TAG")):
        on = bool(desk.ledger_colvis.get(key, True))
        btn = _btn(tk, bar, label, lambda k=key: _toggle_col(desk, k),
                   on=on, small=True)
        btn.pack(side="left", padx=2, pady=8)
        desk.ledger_col_buttons[key] = btn

    _btn(tk, bar, "Create summaries",
         lambda: _create_summaries(desk)).pack(side="right", padx=(4, 8), pady=8)
    try:
        import ledger_more

        if hasattr(ledger_more, "build"):
            more_host = tk.Frame(bar, bg=CARD)
            more_host.pack(side="right", padx=4, pady=8)
            ledger_more.build(more_host, desk)
    except Exception:
        pass
    return bar


def _mount_tabs(desk, tk, root):
    tabrow = tk.Frame(root, bg=CARD)
    tk.Label(tabrow, text="Sessions", fg=QUIET, bg=CARD,
             font=("Segoe UI", -12)).pack(side="left", padx=(8, 4))
    _btn(tk, tabrow, "<", lambda: _page_tabs(desk, -1), small=True).pack(side="left", padx=2)
    strip = tk.Frame(tabrow, bg=CARD)
    strip.pack(side="left", fill="x", expand=True, padx=2)
    desk.ledger_tabstrip = strip
    _btn(tk, tabrow, ">", lambda: _page_tabs(desk, 1), small=True).pack(side="left", padx=2)
    return tabrow


def _mount_heads(desk, tk, root):
    wrap = tk.Frame(root, bg=BG)
    grid = tk.Frame(wrap, bg=BG)
    grid.pack(fill="x", padx=8)
    grid.grid_columnconfigure(0, weight=0, minsize=248)
    grid.grid_columnconfigure(1, weight=1, minsize=420)
    grid.grid_columnconfigure(2, weight=0, minsize=212)
    grid.grid_columnconfigure(3, weight=0, minsize=150)
    tk.Label(grid, text="TOPICS", fg=INK, bg=BG, anchor="w",
             font=("Segoe UI", -13, "bold")).grid(row=0, column=0, sticky="ew", padx=(0, 4))
    tk.Label(grid, text="Summaries", fg=INK, bg=BG, anchor="w",
             font=("Segoe UI", -13, "bold")).grid(row=0, column=2, sticky="ew", padx=(4, 0))
    tk.Frame(wrap, bg=RED, height=2).pack(fill="x", padx=8, pady=(2, 0))
    return wrap


class _Bar:
    """Minimal dark scrollbar. ttk.Scrollbar would not take the theme."""

    def __init__(self, tk, parent, tree):
        self.tk = tk
        self.tree = tree
        self.lo, self.hi = 0.0, 1.0
        self._grab_y = None
        self._grab_lo = 0.0
        cv = tk.Canvas(parent, width=14, bg=CARD, highlightthickness=0, bd=0,
                       relief="flat", cursor="hand2")
        cv.pack(side="right", fill="y")
        self.cv = cv
        self.trough = cv.create_rectangle(0, 0, 14, 8, fill=CARD, outline="")
        self.thumb = cv.create_rectangle(2, 0, 12, 24, fill="#1E2430", outline="")
        cv.bind("<Configure>", lambda _e: self.paint())
        cv.bind("<Button-1>", self._click)
        cv.bind("<B1-Motion>", self._drag)
        cv.bind("<Enter>", lambda _e: self._hover(True))
        cv.bind("<Leave>", lambda _e: self._hover(False))
        tree.configure(yscrollcommand=self._set)
        tree.bind("<MouseWheel>", lambda e: self._wheel(e), add="+")

    def _set(self, lo, hi):
        try:
            self.lo, self.hi = float(lo), float(hi)
        except (TypeError, ValueError):
            self.lo, self.hi = 0.0, 1.0
        self.paint()

    def paint(self):
        try:
            h = self.cv.winfo_height()
        except Exception:
            return
        if h < 8:
            return
        self.cv.coords(self.trough, 0, 0, 14, h)
        if self.hi - self.lo >= 0.999:
            self.cv.itemconfigure(self.thumb, state="hidden")
            return
        self.cv.itemconfigure(self.thumb, state="normal")
        top = max(0, int(self.lo * h))
        bot = min(h, max(top + 24, int(self.hi * h)))
        self.cv.coords(self.thumb, 2, top, 12, bot)

    def _hover(self, on: bool) -> None:
        try:
            self.cv.itemconfigure(self.thumb, fill=ACCENT if on else "#1E2430")
        except Exception:
            pass

    def _click(self, event) -> None:
        try:
            y = event.y
            h = self.cv.winfo_height() or 1
            top = self.lo * h
            bot = self.hi * h
            if top <= y <= bot:
                self._grab_y = y
                self._grab_lo = self.lo
            elif y < top:
                self.tree.yview("scroll", -1, "pages")
            else:
                self.tree.yview("scroll", 1, "pages")
        except Exception:
            pass

    def _drag(self, event) -> None:
        if self._grab_y is None:
            return
        try:
            h = self.cv.winfo_height() or 1
            frac = self._grab_lo + (event.y - self._grab_y) / h
            self.tree.yview("moveto", max(0.0, min(1.0, frac)))
        except Exception:
            pass

    def _wheel(self, event) -> None:
        try:
            steps = int(event.delta // 120) if event.delta else 0
            if steps:
                self.tree.yview_scroll(-steps, "units")
        except Exception:
            pass


class _Tip:
    """Hover tooltip showing the full row text that the column clips."""

    def __init__(self, tk, tree, text_of):
        self.tk = tk
        self.tree = tree
        self.text_of = text_of
        self.win = None
        self.after = None
        tree.bind("<Motion>", self._motion, add="+")
        tree.bind("<Leave>", lambda _e: self.hide(), add="+")
        tree.bind("<Button-1>", lambda _e: self.hide(), add="+")
        tree.bind("<MouseWheel>", lambda _e: self.hide(), add="+")

    def hide(self) -> None:
        if self.after is not None:
            try:
                self.tree.after_cancel(self.after)
            except Exception:
                pass
            self.after = None
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None

    def _motion(self, event) -> None:
        self.hide()
        try:
            iid = self.tree.identify_row(event.y)
        except Exception:
            return
        if not iid or iid.startswith("g-") or iid.startswith("d-"):
            return
        hit = getattr(self.tree, "_ledger_rows", {}).get(iid)
        if hit is None:
            return
        try:
            text = self.text_of(hit)
        except Exception:
            return
        if not text:
            return
        try:
            x, y = event.x_root + 14, event.y_root + 12
            self.after = self.tree.after(350, lambda: self._show(text, x, y))
        except Exception:
            pass

    def _show(self, text: str, x: int, y: int) -> None:
        self.after = None
        self.hide()
        try:
            win = self.tk.Toplevel(self.tree)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            label = self.tk.Label(win, text=text, fg=INK, bg="#1E2430",
                                  font=("Segoe UI", -12), padx=10, pady=6,
                                  wraplength=420, justify="left")
            label.pack()
            win.after(3000, self.hide)
            self.win = win
        except Exception:
            pass


def _left_tip_text(hit) -> str:
    if isinstance(hit, dict):
        bits = [title_of(hit), age_text(hit.get("updated"))]
        proj = project_of(hit)
        if proj:
            bits.append(proj)
        return "  ·  ".join(b for b in bits if b)
    return str(hit or "")


def _table_tip_text(hit) -> str:
    if not isinstance(hit, dict):
        return ""
    return "  ·  ".join(part for part in (
        title_of(hit), project_of(hit), _tokens_text(hit),
        _cost_text(hit), source_label(hit)) if part and part != EM)


def _mount_left(desk, tk, parent):
    ttk = getattr(desk, "ttk", None)
    if ttk is None:
        from tkinter import ttk
    style = ttk.Style(parent)
    _style_tree(style)
    tree = ttk.Treeview(parent, columns=("title", "age"), show="", style="Cm.Left.Treeview",
                        selectmode="browse")
    tree.column("title", anchor="w", stretch=True, minwidth=60)
    tree.column("age", anchor="e", stretch=False, width=64, minwidth=56)
    tree.tag_configure("group", foreground=QUIET)
    _Bar(tk, parent, tree)
    tree.pack(side="left", fill="both", expand=True)
    tree._ledger_rows = {}
    tree.bind("<<TreeviewSelect>>", lambda _e: _open_left(desk))
    _Tip(tk, tree, _left_tip_text)
    desk.ledger_left = tree
    desk.ledger_ran = parent
    desk.ledger_times = parent


def _mount_table_frame(desk, tk, center):
    frame = tk.Frame(center, bg=BG)
    frame.pack(fill="both", expand=True)
    ttk = getattr(desk, "ttk", None)
    if ttk is None:
        from tkinter import ttk
    style = ttk.Style(frame)
    _style_tree(style)
    tree = ttk.Treeview(
        frame,
        columns=("title", "proj", "tokens", "cost", "tag"),
        show="headings", style="Cm.Table.Treeview", selectmode="browse",
    )
    heads = (("title", "session Summaries", 280), ("proj", "Proj", 125),
             ("tokens", "Tokens", 90), ("cost", "cost $", 80), ("tag", "TAG", 130))
    for key, text, width in heads:
        tree.heading(key, text=text, anchor="w")
        tree.column(key, width=width, minwidth=40, anchor="w", stretch=(key == "title"))
    tree.tag_configure("group", foreground=QUIET)
    _Bar(tk, frame, tree)
    tree.pack(side="left", fill="both", expand=True)
    tree._ledger_rows = {}
    tree.bind("<<TreeviewSelect>>", lambda _e: _open_table(desk))
    _Tip(tk, tree, _table_tip_text)
    desk.ledger_tree = tree
    desk.ledger_table_frame = frame
    desk.ledger_body_frames["table"] = frame
    desk.ledger_size = frame
    desk.ledger_topics = frame
    _apply_cols(desk)


def _style_tree(style) -> None:
    style.configure("Cm.Left.Treeview", background=CARD, fieldbackground=CARD,
                    foreground=INK, borderwidth=0, relief="flat", rowheight=30,
                    bordercolor=CARD, lightcolor=CARD, darkcolor=CARD,
                    font=("Segoe UI", -13))
    style.configure("Cm.Table.Treeview", background=CARD, fieldbackground=CARD,
                    foreground=INK, borderwidth=0, relief="flat", rowheight=30,
                    bordercolor=CARD, lightcolor=CARD, darkcolor=CARD,
                    font=("Segoe UI", -13))
    style.configure("Cm.Left.Treeview.Heading", background=BG, foreground=QUIET,
                    relief="flat", borderwidth=0, font=("Segoe UI", -12))
    style.configure("Cm.Table.Treeview.Heading", background=BG, foreground=QUIET,
                    relief="flat", borderwidth=0, font=("Segoe UI", -12))
    style.map("Cm.Left.Treeview", background=[("selected", "#1E2430")],
              foreground=[("selected", INK)])
    style.map("Cm.Table.Treeview", background=[("selected", "#1E2430")],
              foreground=[("selected", INK)])


def _mount_right(desk, tk, parent):
    tk.Label(parent, text="Daily Summary of tasks", fg=INK, bg=CARD, anchor="w",
             font=("Segoe UI", -13, "bold")).pack(fill="x", padx=10, pady=(10, 0))
    desk.ledger_daily_days = _daily_block(tk, parent)
    tk.Label(parent, text="Weekly Summary", fg=INK, bg=CARD, anchor="w",
             font=("Segoe UI", -13, "bold")).pack(fill="x", padx=10, pady=(8, 0))
    desk.ledger_daily_week = _daily_block(tk, parent)
    tk.Frame(parent, bg=LINE, height=1).pack(fill="x", padx=10, pady=8)
    tk.Label(parent, text="Monthly summary", fg=INK, bg=CARD, anchor="w",
             font=("Segoe UI", -13, "bold")).pack(fill="x", padx=10, pady=(0, 0))
    desk.ledger_daily_month = _daily_block(tk, parent)
    tk.Frame(parent, bg=LINE, height=1).pack(fill="x", padx=10, pady=8)
    tk.Label(parent, text="Quarterly", fg=INK, bg=CARD, anchor="w",
             font=("Segoe UI", -13, "bold")).pack(fill="x", padx=10, pady=(0, 0))
    desk.ledger_daily_quarter = _daily_block(tk, parent)


def _daily_block(tk, parent):
    box = tk.Text(parent, height=4, width=22, bg=CARD, fg="#A7B0C3", relief="flat",
                  wrap="word", font=("Segoe UI", -12),
                  highlightthickness=0, bd=0, padx=4, pady=2)
    box.pack(fill="x", padx=10, pady=(2, 0))
    box.configure(state="disabled")
    return box


def _mount_rail(desk, tk, parent):
    _btn(tk, parent, "SAVE AS", lambda: _invoke(desk, "_on_export")).pack(
        fill="x", padx=10, pady=(10, 4))
    _btn(tk, parent, "LOAD OPEN", lambda: _invoke(desk, "_on_load")).pack(
        fill="x", padx=10, pady=4)
    row = tk.Frame(parent, bg=CARD)
    row.pack(fill="x", padx=10, pady=4)
    tk.Label(row, text="search", fg=QUIET, bg=CARD,
             font=("Segoe UI", -12)).pack(anchor="w")
    var = getattr(desk, "query", None)
    if var is None or not hasattr(var, "get"):
        var = tk.StringVar(value="")
        desk.query = var
    entry = tk.Entry(row, textvariable=var, bg="#1E2430", fg=INK, insertbackground=INK,
                     relief="flat", font=("Segoe UI", -13),
                     highlightthickness=1, highlightbackground=LINE,
                     highlightcolor=ACCENT)
    entry.pack(fill="x", ipady=4)
    entry.bind("<Return>", lambda _e: refresh(desk, getattr(desk, "hits", []) or []))
    try:
        var.trace_add("write", lambda *_a: _schedule_refresh(desk))
    except Exception:
        pass
    _btn(tk, parent, "\U0001f4c5 calendar",
         lambda: _show_body(desk, "calendar")).pack(fill="x", padx=10, pady=4)
    _btn(tk, parent, "Project folder View",
         lambda: _show_body(desk, "projects")).pack(fill="x", padx=10, pady=4)
    _btn(tk, parent, "Print", lambda: _print_view(desk)).pack(fill="x", padx=10, pady=4)
    tk.Label(parent, text="Table View", fg=ACCENT, bg=CARD, anchor="w",
             font=("Segoe UI", -12, "bold")).pack(fill="x", padx=10, pady=(10, 2))
    tk.Label(parent, text="Rows open the session\nin the center column.", fg=QUIET, bg=CARD,
             anchor="w", justify="left",
             font=("Segoe UI", -12)).pack(fill="x", padx=10, pady=(0, 10))


def _mount_foot(desk, tk, root):
    foot = tk.Frame(root, bg=BG)
    try:
        import ledger_menu

        sun_host = tk.Frame(foot, bg=BG)
        sun_host.pack(side="left", padx=(8, 0), pady=4)
        ledger_menu.build(sun_host, desk)
    except Exception:
        tk.Label(foot, text="User", fg=INK, bg=BG).pack(side="left", padx=(8, 0), pady=4)
    desk.ledger_say = tk.Label(foot, text="Ready", fg=QUIET, bg=BG, anchor="w",
                               font=("Segoe UI", -12))
    desk.ledger_say.pack(side="left", padx=12, pady=4)
    tk.Label(foot, text="Costs are estimates, not a bill. Token Center is not connected.",
             fg=QUIET, bg=BG, anchor="e",
             font=("Segoe UI", -12)).pack(side="right", padx=8, pady=4)
    return foot


def _mirror_say(desk) -> None:
    orig = getattr(desk, "_say", None)
    if not callable(orig):
        return
    try:
        bound = orig.__get__(desk, type(desk))
    except Exception:
        return

    def say(text: str, tone: str = "") -> None:
        try:
            bound(text, tone)
        except Exception:
            pass
        label = getattr(desk, "ledger_say", None)
        if label is not None:
            try:
                label.configure(text=str(text or ""))
            except Exception:
                pass

    desk._say = say


def _invoke(desk, name: str) -> None:
    fn = getattr(desk, name, None)
    if callable(fn):
        fn()


def _create_summaries(desk) -> None:
    hook = getattr(desk, "_on_summaries", None)
    if callable(hook):
        hook()
        return
    say = getattr(desk, "_say", None)
    if callable(say):
        say("Create summaries uses the title and project already on the row. "
            "A model summary is not part of this pass.", "warn")


def _set_scope(desk, scope: str) -> None:
    desk.ledger_scope = scope
    for key, btn in (getattr(desk, "ledger_scope_buttons", None) or {}).items():
        try:
            on = key == scope
            btn.configure(bg=ACCENT if on else "#1E2430", fg=BG if on else INK)
        except Exception:
            pass
    if scope == "drives":
        _load_drives(desk)
    refresh(desk, getattr(desk, "hits", []) or [])


def _set_group(desk, mode: str) -> None:
    desk.ledger_group = mode if mode in ("maker", "project", "topic") else "flat"
    try:
        labels = {"flat": "Flat", "maker": "Maker", "project": "Project", "topic": "Topic"}
        desk.ledger_group_btn.configure(
            text=f"Group: {labels.get(desk.ledger_group, 'Flat')} \u25be")
    except Exception:
        pass
    refresh(desk, getattr(desk, "hits", []) or [])


def _popup_group(desk) -> None:
    tk = desk.tk
    try:
        menu = tk.Menu(desk.root, tearoff=0, bg=CARD, fg=INK,
                       activebackground="#1E2430", activeforeground=INK)
        current = _mode(desk)
        for mode, label in (("flat", "Flat"), ("maker", "By maker"),
                            ("project", "By project"), ("topic", "By topic")):
            menu.add_radiobutton(label=label, value=mode,
                                 variable=_group_var(desk, current),
                                 command=lambda m=mode: _set_group(desk, m))
        btn = desk.ledger_group_btn
        menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
    except Exception:
        pass


def _group_var(desk, current: str):
    tk = desk.tk
    var = getattr(desk, "_ledger_group_var", None)
    if var is None:
        var = tk.StringVar(value=current)
        desk._ledger_group_var = var
    try:
        var.set(current)
    except Exception:
        pass
    return var


def _popup_makers(desk) -> None:
    tk = desk.tk
    try:
        hits = getattr(desk, "hits", []) or []
        names = sorted({_harness(h) for h in hits if isinstance(h, dict) and _harness(h)})
        menu = tk.Menu(desk.root, tearoff=0, bg=CARD, fg=INK,
                       activebackground="#1E2430", activeforeground=INK)
        menu.add_command(label="All makers",
                         command=lambda: _set_makers(desk, set()))
        menu.add_separator()
        chosen = set(getattr(desk, "ledger_makers", None) or set())
        for name in names:
            menu.add_checkbutton(
                label=f"{'✓ ' if name in chosen or not chosen else ''}{name}",
                command=lambda n=name: _flip_maker(desk, n, names))
        btn = desk.ledger_maker_btn
        menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
    except Exception:
        pass


def _set_makers(desk, names: set) -> None:
    desk.ledger_makers = set(names)
    _paint_maker_btn(desk)
    refresh(desk, getattr(desk, "hits", []) or [])


def _flip_maker(desk, name: str, all_names: list) -> None:
    chosen = set(getattr(desk, "ledger_makers", None) or set())
    if not chosen:
        chosen = set(all_names)
    if name in chosen:
        chosen.discard(name)
        if not chosen or chosen == set(all_names):
            chosen = set()
    else:
        chosen.add(name)
        if chosen == set(all_names):
            chosen = set()
    _set_makers(desk, chosen)


def _paint_maker_btn(desk) -> None:
    try:
        chosen = set(getattr(desk, "ledger_makers", None) or set())
        text = "Maker: All \u25be" if not chosen else f"Maker: {len(chosen)} \u25be"
        desk.ledger_maker_btn.configure(text=text)
    except Exception:
        pass


def _toggle_col(desk, key: str) -> None:
    vis = getattr(desk, "ledger_colvis", None) or {}
    vis[key] = not vis.get(key, True)
    desk.ledger_colvis = vis
    try:
        btn = (getattr(desk, "ledger_col_buttons", None) or {}).get(key)
        if btn is not None:
            on = bool(vis[key])
            btn.configure(bg=ACCENT if on else "#1E2430", fg=BG if on else INK)
    except Exception:
        pass
    _apply_cols(desk)


def _apply_cols(desk) -> None:
    tree = getattr(desk, "ledger_tree", None)
    if tree is None:
        return
    vis = getattr(desk, "ledger_colvis", None) or {}
    cols = ["title"]
    for key in ("proj", "tokens", "cost", "tag"):
        if vis.get(key, True):
            cols.append(key)
    try:
        tree.configure(displaycolumns=cols)
    except Exception:
        pass


def _popup_more(desk) -> None:
    tk = desk.tk
    try:
        menu = tk.Menu(desk.root, tearoff=0, bg=CARD, fg=INK,
                       activebackground="#1E2430", activeforeground=INK)
        for label, name in (("Refresh", "_load_all"), ("Build index", "_on_index"),
                            ("Quit", "_on_quit")):
            fn = getattr(desk, name, None)
            if callable(fn):
                menu.add_command(label=label, command=fn)
        menu.tk_popup(desk.root.winfo_pointerx(), desk.root.winfo_pointery())
    except Exception:
        pass


def _page_tabs(desk, step: int) -> None:
    desk.ledger_tabstart = max(0, getattr(desk, "ledger_tabstart", 0) + step * 8)
    refresh(desk, getattr(desk, "hits", []) or [])


def _schedule_refresh(desk) -> None:
    try:
        root = desk.root
    except Exception:
        return
    old = getattr(desk, "_ledger_search_after", None)
    if old is not None:
        try:
            root.after_cancel(old)
        except Exception:
            pass
    try:
        desk._ledger_search_after = root.after(
            250, lambda: refresh(desk, getattr(desk, "hits", []) or []))
    except Exception:
        pass


def _print_view(desk) -> None:
    rows = _sort(_visible(desk, getattr(desk, "hits", []) or ()), _mode(desk))
    lines = ["TOPICS\tsession Summaries\tProj\tToken count\tcost $\tTAG"]
    for hit in rows:
        lines.append("\t".join((
            title_of(hit), title_of(hit), project_of(hit) or EM,
            _tokens_text(hit), _cost_text(hit), source_label(hit))))
    try:
        desk.root.clipboard_clear()
        desk.root.clipboard_append("\n".join(lines))
    except Exception:
        pass
    say = getattr(desk, "_say", None)
    if callable(say):
        say("Printable view is on the clipboard.")


def _load_drives(desk) -> None:
    if getattr(desk, "ledger_drives_loading", False):
        return
    desk.ledger_drives_loading = True

    def work():
        try:
            import engine

            placed = engine.places()
            error = ""
        except Exception as exc:  # noqa: BLE001
            placed, error = None, f"{type(exc).__name__}: {exc}"
        try:
            desk.root.after(0, lambda: _finish_drives(desk, placed, error))
        except Exception:
            desk.ledger_drives_loading = False

    threading.Thread(target=work, daemon=True).start()


def _finish_drives(desk, placed, error: str) -> None:
    desk.ledger_drives_loading = False
    if error or not isinstance(placed, dict):
        desk.ledger_drives = []
        say = getattr(desk, "_say", None)
        if callable(say):
            say(error or "Drives could not be read.", "bad")
        return
    drives = [r for r in (placed.get("drives") or []) if isinstance(r, dict)]
    homes = [r for r in (placed.get("homes") or []) if isinstance(r, dict)]
    desk.ledger_drives = drives
    desk.ledger_homes = homes
    paint_left(desk, _visible(desk, getattr(desk, "hits", []) or ()))
    say = getattr(desk, "_say", None)
    if callable(say) and getattr(desk, "ledger_scope", "") == "drives":
        present = sum(1 for h in homes if h.get("present"))
        say(f"{len(drives)} drives. {present} locations present.")


def _show_body(desk, name: str) -> None:
    if name not in ("table", "session", "calendar", "projects"):
        name = "table"
    desk.ledger_body = name
    center = getattr(desk, "ledger_center", None)
    if center is None:
        return
    tk = desk.tk
    frames = getattr(desk, "ledger_body_frames", None) or {}
    desk.ledger_body_frames = frames
    if name not in frames:
        frame = tk.Frame(center, bg=BG)
        frame.pack(fill="both", expand=True)
        builder = {"session": "ledger_session", "calendar": "ledger_calendar",
                   "projects": "ledger_projects"}.get(name)
        if builder:
            try:
                mod = __import__(builder)
                build = getattr(mod, "build", None)
                if callable(build):
                    build(frame, desk)
            except Exception as exc:  # noqa: BLE001
                errors = getattr(desk, "_ledger_errors", None)
                if not isinstance(errors, list):
                    errors = []
                    desk._ledger_errors = errors
                errors.append(f"{builder}: {type(exc).__name__}: {exc}")
        frames[name] = frame
    for key, frame in frames.items():
        try:
            if key == name:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        except Exception:
            pass
    if name in ("calendar", "projects"):
        builder = {"calendar": "ledger_calendar", "projects": "ledger_projects"}.get(name)
        if builder:
            try:
                import sys

                mod = sys.modules.get(builder) or __import__(builder)
                fn = getattr(mod, "refresh", None)
                if callable(fn):
                    fn(desk, getattr(desk, "hits", []) or [])
            except Exception:
                pass
    elif name == "session":
        hit = None
        rows = getattr(desk, "hits", None) or []
        index = getattr(desk, "selected_index", None)
        if isinstance(index, int) and 0 <= index < len(rows):
            hit = rows[index]
        if isinstance(hit, dict):
            try:
                import ledger_session

                if hasattr(ledger_session, "fill"):
                    ledger_session.fill(desk, hit)
            except Exception:
                pass


def _open_table(desk) -> None:
    if getattr(desk, "_ledger_select_busy", False):
        return
    tree = getattr(desk, "ledger_tree", None)
    if tree is None:
        return
    try:
        chosen = tree.selection()
    except Exception:
        return
    if not chosen:
        return
    iid = str(chosen[0])
    if iid.startswith("g-"):
        return
    hit = getattr(tree, "_ledger_rows", {}).get(iid)
    if isinstance(hit, dict):
        _open_hit(desk, hit)


def _open_left(desk) -> None:
    if getattr(desk, "_ledger_select_busy", False):
        return
    tree = getattr(desk, "ledger_left", None)
    if tree is None:
        return
    try:
        chosen = tree.selection()
    except Exception:
        return
    if not chosen:
        return
    iid = str(chosen[0])
    rows = getattr(tree, "_ledger_rows", {})
    if iid.startswith("d-"):
        info = rows.get(iid)
        say = getattr(desk, "_say", None)
        if callable(say):
            say(str(info) if info else "Drive.", "")
        return
    hit = rows.get(iid)
    if isinstance(hit, dict):
        _open_hit(desk, hit)


def refresh(desk, hits) -> None:
    tree = getattr(desk, "ledger_tree", None)
    if tree is None:
        return
    desk._ledger_select_busy = True
    try:
        rows = _sort(_visible(desk, hits), _mode(desk))
        _paint_table(desk, tree, rows)
        paint_left(desk, rows)
        _paint_tabs(desk, rows)
        _fill_daily(desk, rows)
        _paint_maker_btn(desk)
        for mod_name in ("ledger_calendar", "ledger_projects"):
            try:
                import sys

                mod = sys.modules.get(mod_name) or __import__(mod_name)
                fn = getattr(mod, "refresh", None)
                frames = getattr(desk, "ledger_body_frames", None) or {}
                if callable(fn) and any(k in frames for k in ("calendar", "projects")):
                    fn(desk, rows)
            except Exception:
                pass
        say_label = getattr(desk, "ledger_say", None)
        if say_label is not None:
            try:
                makers = {_harness(h) for h in rows if _harness(h)}
                say_label.configure(text=f"{len(rows)} sessions · {len(makers)} makers")
            except Exception:
                pass
    finally:
        desk._ledger_select_busy = False


def _values(hit: dict):
    if hit.get("legal"):
        return ("Legal session", "", EM, EM, source_label(hit))
    return (title_of(hit), project_of(hit) or EM, _tokens_text(hit),
            _cost_text(hit), source_label(hit))


def _paint_table(desk, tree, rows: list) -> None:
    tree._ledger_rows = {}
    try:
        kids = tree.get_children("")
        if kids:
            tree.delete(*kids)
    except Exception:
        pass
    try:
        selected_id = None
        index = getattr(desk, "selected_index", None)
        full = getattr(desk, "hits", None) or []
        if isinstance(index, int) and 0 <= index < len(full):
            selected_id = full[index].get("id") if isinstance(full[index], dict) else None
    except Exception:
        selected_id = None
    mode = _mode(desk)
    seen: set[str] = set()
    group_n = 0
    last = None
    want_iid = None
    for hit in rows:
        if mode != "flat":
            label = _group_label(hit, mode)
            if label.casefold() != (last or ""):
                last = label.casefold()
                try:
                    tree.insert("", "end", iid=f"g-{group_n}",
                                values=(label, "", "", "", ""), tags=("group",))
                except Exception:
                    pass
                group_n += 1
        ident = "".join(ch for ch in str(hit.get("id") or "") if ch not in " \t\r\n\\{}")
        base = f"h-{ident}" if ident else ""
        if not base or base in seen:
            n = 0
            base = f"h-{ident}#{n}" if ident else f"h-row-{n}"
            while base in seen:
                n += 1
                base = f"h-{ident}#{n}" if ident else f"h-row-{n}"
        seen.add(base)
        tag = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in _harness(hit).lower()) or "other"
        try:
            tree.tag_configure(tag, foreground=vendor_color(_harness(hit)))
        except Exception:
            pass
        try:
            tree.insert("", "end", iid=base, values=_values(hit), tags=(tag,))
        except Exception:
            continue
        tree._ledger_rows[base] = hit
        if selected_id is not None and hit.get("id") == selected_id:
            want_iid = base
    if want_iid is not None:
        try:
            tree.selection_set(want_iid)
            tree.see(want_iid)
        except Exception:
            pass


def paint_left(desk, rows: list) -> None:
    """Left TOPICS list. Session scope shows titles with ages, drive scope shows drives."""
    tree = getattr(desk, "ledger_left", None)
    if tree is None:
        return
    tree._ledger_rows = {}
    try:
        kids = tree.get_children("")
        if kids:
            tree.delete(*kids)
    except Exception:
        pass
    if getattr(desk, "ledger_scope", "sessions") == "drives":
        for n, drive in enumerate(getattr(desk, "ledger_drives", None) or []):
            if not isinstance(drive, dict):
                continue
            letter = str(drive.get("id") or drive.get("path") or "Drive")
            label = str(drive.get("label") or "").strip()
            free = ""
            try:
                size = drive.get("free")
                if isinstance(size, (int, float)) and size > 0:
                    free = f"  {int(size // (1024 ** 3))} GB free"
            except Exception:
                pass
            text = f"{letter}  {label}{free}".strip()
            iid = f"d-{n}"
            try:
                tree.insert("", "end", iid=iid, values=(text, ""))
            except Exception:
                continue
            tree._ledger_rows[iid] = text or "Drive."
        if not getattr(desk, "ledger_drives", None):
            try:
                tree.insert("", "end", iid="d-hint", values=("Reading drives…", ""))
            except Exception:
                pass
        return
    seen: set[str] = set()
    for hit in rows[:200]:
        ident = "".join(ch for ch in str(hit.get("id") or "") if ch not in " \t\r\n\\{}")
        base = f"h-{ident}" if ident else ""
        if not base or base in seen:
            n = 0
            base = "h-row-0"
            while base in seen:
                n += 1
                base = f"h-row-{n}"
        seen.add(base)
        text = title_of(hit)
        tag = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in _harness(hit).lower()) or "other"
        try:
            tree.tag_configure(tag, foreground=vendor_color(_harness(hit)))
        except Exception:
            pass
        try:
            tree.insert("", "end", iid=base, values=(text, age_text(hit.get("updated"))), tags=(tag,))
        except Exception:
            continue
        tree._ledger_rows[base] = hit


def _short(text: str, width: int = 24) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


def _paint_tabs(desk, rows: list) -> None:
    strip = getattr(desk, "ledger_tabstrip", None)
    if strip is None:
        return
    tk = desk.tk
    try:
        for child in list(strip.winfo_children()):
            child.destroy()
    except Exception:
        pass
    start = max(0, getattr(desk, "ledger_tabstart", 0))
    if start >= len(rows) and rows:
        start = max(0, len(rows) - 8)
        desk.ledger_tabstart = start
    for hit in rows[start: start + 8]:
        try:
            chip = tk.Button(
                strip, text=_short(title_of(hit)), bg="#1E2430", fg=INK,
                activebackground=ACCENT, activeforeground=BG,
                relief="flat", bd=0, font=("Segoe UI", -12), padx=8, pady=3,
                cursor="hand2", command=lambda h=hit: _open_hit(desk, h))
            chip.pack(side="left", padx=2)
        except Exception:
            pass


def _fill_daily(desk, rows: list) -> None:
    now = datetime.now()
    days, week, month, quarter = [], 0, 0, 0
    for hit in rows:
        try:
            n = float(hit.get("updated"))
        except (TypeError, ValueError):
            continue
        ms = n / 1000 if n > 100000000000 else n
        try:
            when = datetime.fromtimestamp(ms)
        except (OSError, OverflowError, ValueError):
            continue
        age = now - when
        if age <= timedelta(days=7):
            week += 1
            if len(days) < 8:
                days.append(title_of(hit))
        if age <= timedelta(days=30):
            month += 1
        if age <= timedelta(days=90):
            quarter += 1
    _set(getattr(desk, "ledger_daily_days", None), "\n".join(days) or EM)
    _set(getattr(desk, "ledger_daily_week", None), f"{week} sessions")
    _set(getattr(desk, "ledger_daily_month", None), f"{month} sessions")
    _set(getattr(desk, "ledger_daily_quarter", None), f"{quarter} sessions")


def _set(widget, text: str) -> None:
    if widget is None:
        return
    try:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")
    except Exception:
        pass


def _group(desk, mode: str) -> None:
    """Compat: the old header called this. The Group menu calls _set_group."""
    _set_group(desk, mode)


def _open(desk) -> None:
    tree = getattr(desk, "ledger_tree", None)
    if tree is None:
        return
    try:
        chosen = tree.selection()
    except Exception:
        return
    if not chosen or not str(chosen[0]).startswith("h-"):
        return
    hit = getattr(tree, "_ledger_rows", {}).get(str(chosen[0]))
    if isinstance(hit, dict):
        _open_hit(desk, hit)
