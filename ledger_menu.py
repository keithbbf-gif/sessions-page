"""Sun menu beside the username. Account and estimated usage."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

# Published list prices, USD per 1M tokens, input then output.
# Used only as an estimate. Not a bill.
_RATES = {
    "grok": ("Grok 4.7", 2.0, 6.0),
    "claude": ("Claude Sonnet 5", 2.0, 10.0),
    "claude-opus": ("Claude Opus 5.5", 4.0, 20.0),
    "claude-haiku": ("Claude Haiku 5.5", 0.10, 0.50),
    "codex": ("GPT-5.1", 1.25, 10.0),
    "gemini": ("Gemini 2.5 Flash", 0.30, 2.50),
    "gemini-pro": ("Gemini 2.5 Pro", 1.25, 10.0),
    "antigravity": ("Gemini 2.5 Flash", 0.30, 2.50),
}

_PERIODS = (
    ("Today", 1),
    ("7 days", 7),
    ("30 days", 30),
    ("90 days", 90),
    ("All", None),
)


def _user() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or "User"


def _stamp(hit: dict):
    try:
        n = float(hit.get("updated"))
    except (TypeError, ValueError):
        return None
    return n / 1000 if n > 100000000000 else n


def _tokens(hit: dict) -> tuple[float, str]:
    for key in ("input_tokens", "output_tokens"):
        if hit.get("input_tokens") or hit.get("output_tokens"):
            inn = float(hit.get("input_tokens") or 0)
            out = float(hit.get("output_tokens") or 0)
            return inn + out, "counted"
    for key in ("tokens", "token_count", "n_tokens"):
        try:
            return float(hit.get(key)), "counted"
        except (TypeError, ValueError):
            continue
    try:
        size = int(hit.get("bytes") or 0)
    except (TypeError, ValueError):
        size = 0
    if size > 0:
        return size / 4.0, "from size"
    return 0.0, "none"


def _rate_key(hit: dict) -> str:
    harness = str(hit.get("harness") or "").lower()
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


def _cost(tokens: float, key: str) -> float | None:
    rate = _RATES.get(key)
    if not rate or tokens <= 0:
        return None
    inn, out = rate[1], rate[2]
    blended = 0.75 * inn + 0.25 * out
    return tokens * blended / 1_000_000


def build(parent, desk) -> None:
    tk = desk.tk
    bar = tk.Frame(parent, bg="#07080A")
    bar.pack(side="left", padx=8, pady=4)
    sun = tk.Canvas(bar, width=22, height=22, bg="#07080A", highlightthickness=0, cursor="hand2")
    sun.pack(side="left")
    sun.create_oval(6, 6, 16, 16, fill="#F5C542", outline="#F5C542")
    for x1, y1, x2, y2 in (
        (10, 1, 12, 5), (10, 17, 12, 21), (1, 10, 5, 12), (17, 10, 21, 12),
        (3, 3, 6, 6), (16, 3, 19, 6), (3, 16, 6, 19), (16, 16, 19, 19),
    ):
        sun.create_line(x1, y1, x2, y2, fill="#F5C542", width=2)
    name = tk.Label(bar, text=_user(), fg="#E8ECF4", bg="#07080A", cursor="hand2")
    name.pack(side="left", padx=(6, 0))
    for widget in (sun, name):
        widget.bind("<Button-1>", lambda event: _popup(desk, event))


def _popup(desk, event) -> None:
    tk = desk.tk
    menu = tk.Menu(desk.root, tearoff=0, bg="#12151C", fg="#E8ECF4", activebackground="#1E2430")
    menu.add_command(label="Account", command=lambda: _account(desk))
    menu.add_command(label="Usage", command=lambda: _usage(desk))
    menu.add_separator()
    menu.add_command(label="General", command=lambda: desk._say("General settings are not in this build.", ""))
    menu.add_command(label="Appearance", command=lambda: desk._say("Appearance settings are not in this build.", ""))
    menu.add_command(label="Notifications", command=lambda: desk._say("Notifications are not in this build.", ""))
    menu.add_command(label="Shortcuts", command=lambda: desk._say("Shortcuts are not in this build.", ""))
    menu.tk_popup(event.x_root, event.y_root)


def _account(desk) -> None:
    tk = desk.tk
    win = tk.Toplevel(desk.root)
    win.title("Account")
    win.configure(bg="#12151C")
    tk.Label(win, text=_user(), fg="#E8ECF4", bg="#12151C", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
    tk.Label(
        win,
        text="This machine only. Token Center is not connected, so there is no separate cmSessions account.",
        fg="#A7B0C3", bg="#12151C", wraplength=360, justify="left",
    ).pack(anchor="w", padx=16, pady=(0, 16))


def _usage(desk) -> None:
    tk = desk.tk
    win = tk.Toplevel(desk.root)
    win.title("Usage")
    win.configure(bg="#12151C")
    win.geometry("640x420")
    top = tk.Frame(win, bg="#12151C")
    top.pack(fill="x", padx=12, pady=8)
    tk.Label(top, text="Period", fg="#A7B0C3", bg="#12151C").pack(side="left")
    period = tk.StringVar(value="30 days")
    tk.OptionMenu(top, period, *[name for name, _days in _PERIODS]).pack(side="left", padx=8)
    tree = desk.ttk.Treeview(win, columns=("source", "model", "tokens", "cost"), show="headings")
    for key, text, width in (
        ("source", "Source", 140),
        ("model", "Model", 180),
        ("tokens", "Tokens", 120),
        ("cost", "Est. cost", 120),
    ):
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    tree.pack(fill="both", expand=True, padx=12, pady=8)
    note = tk.Label(win, text="", fg="#6B7386", bg="#12151C", wraplength=600, justify="left")
    note.pack(fill="x", padx=12, pady=(0, 12))

    def paint(*_args) -> None:
        tree.delete(*tree.get_children())
        days = dict(_PERIODS).get(period.get())
        cutoff = None if days is None else datetime.now() - timedelta(days=days)
        buckets: dict[tuple[str, str], list] = {}
        sized = 0
        for hit in getattr(desk, "hits", []) or []:
            if not isinstance(hit, dict) or hit.get("legal"):
                continue
            when = _stamp(hit)
            if cutoff is not None and when is not None and datetime.fromtimestamp(when) < cutoff:
                continue
            if cutoff is not None and when is None:
                continue
            tokens, how = _tokens(hit)
            if tokens <= 0:
                continue
            if how == "from size":
                sized += 1
            key = _rate_key(hit)
            rate = _RATES.get(key)
            source = str(hit.get("harness") or "other")
            model = rate[0] if rate else (str(hit.get("model") or "unknown"))
            slot = buckets.setdefault((source, model), [0.0, 0.0, key])
            slot[0] += tokens
            price = _cost(tokens, key)
            if price is not None:
                slot[1] += price
        total_tokens = 0.0
        total_cost = 0.0
        for (source, model), (tokens, price, _key) in sorted(buckets.items()):
            total_tokens += tokens
            total_cost += price
            tree.insert("", "end", values=(source, model, f"{tokens:,.0f}", f"${price:,.2f}" if price else "—"))
        tree.insert("", "end", values=("Total", "", f"{total_tokens:,.0f}", f"${total_cost:,.2f}"))
        note.configure(text=(
            "Estimate only. Token counts are used when a session has them. Otherwise tokens are file size divided by 4. "
            "Cost uses published list prices per 1M tokens, about three quarters input and one quarter output, "
            f"because the split is not on the row. {sized} rows used the size estimate. This is not a bill."
        ))

    period.trace_add("write", paint)
    paint()
