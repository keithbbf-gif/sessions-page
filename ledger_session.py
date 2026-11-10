"""Single-session band inside the ledger. Not its own page."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

_BG = "#07080A"
_CARD = "#12151C"
_INK = "#E8ECF4"
_QUIET = "#6B7386"
_ACCENT = "#7C9CFF"
_DASH = "\u2014"
_CLOSED = "Legal session stays closed."
_FONT = ("Segoe UI", -15)
_PIECES = (
    "session_facts",
    "session_chain",
    "session_keywords",
    "session_text",
    "session_preview",
    "session_actions",
)
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
_STATE: dict[int, dict] = {}


def _bag(desk) -> dict:
    return _STATE.setdefault(id(desk), {})


def _tk(desk):
    module = getattr(desk, "tk", None)
    if module is not None and hasattr(module, "Frame") and hasattr(module, "Label"):
        return module
    import tkinter as tk
    return tk


def _load(name: str):
    try:
        return __import__(name)
    except ImportError:
        pass
    except Exception:
        return None
    path = Path(__file__).resolve().parent / f"{name}.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        return None
    return module


def _call(mod, name: str, *args) -> bool:
    fn = getattr(mod, name, None)
    if not callable(fn):
        return False
    try:
        fn(*args)
    except Exception:
        return False
    return True


def _use(name: str, host, desk) -> bool:
    mod = _load(name)
    if mod is None:
        return False
    before = set(host.winfo_children())
    if not _call(mod, "build", host, desk):
        for child in list(host.winfo_children()):
            if child not in before:
                try:
                    child.destroy()
                except Exception:
                    pass
        return False
    return any(child not in before for child in host.winfo_children())


def build(parent, desk) -> None:
    """Facts, chain, and keywords left to right, then the two panes."""
    tk = _tk(desk)
    parent.configure(bg=_BG)
    bag = _bag(desk)
    bag["owned"] = set()
    bag["app"] = None

    top = tk.Frame(parent, bg=_BG)
    top.pack(fill="x")
    line = tk.Frame(top, bg=_BG)
    line.pack(fill="x")
    app = tk.Label(
        line, text="App", fg=_ACCENT, bg=_BG, anchor="w",
        font=("Segoe UI", 14, "bold"),
    )
    app.pack(side="left", padx=(12, 8), pady=4)
    bag["app"] = app
    facts = tk.Frame(top, bg=_BG)
    facts.pack(fill="x")
    chain = tk.Frame(line, bg=_BG)
    chain.pack(side="left", fill="y")
    keys = tk.Frame(top, bg=_BG)
    keys.pack(fill="x")

    panes = tk.Frame(parent, bg=_BG)
    panes.pack(fill="both", expand=True)
    panes.columnconfigure(0, weight=1)
    panes.columnconfigure(1, weight=1)
    panes.rowconfigure(0, weight=1)
    left = tk.Frame(panes, bg=_BG)
    right = tk.Frame(panes, bg=_BG)
    left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=4)
    right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=4)

    hosts = (
        ("session_facts", facts, _draw_facts),
        ("session_chain", chain, _draw_chain),
        ("session_keywords", keys, _draw_keywords),
        ("session_text", left, _draw_text),
        ("session_preview", right, _draw_preview),
    )
    for name, host, draw in hosts:
        if _use(name, host, desk):
            continue
        bag["owned"].add(name)
        draw(host, desk)

    actions = tk.Frame(parent, bg=_BG)
    if _use("session_actions", actions, desk):
        actions.pack(fill="x")
    else:
        actions.destroy()

    _ensure_refs(desk, facts, left, right)


def _ensure_refs(desk, facts, left, right) -> None:
    if getattr(desk, "ledger_session_facts", None) is None:
        _draw_facts(facts, desk)
        _bag(desk)["owned"].add("session_facts")
    if getattr(desk, "ledger_session_text", None) is None:
        _draw_text(left, desk)
        _bag(desk)["owned"].add("session_text")
    if getattr(desk, "ledger_session_preview", None) is None:
        _draw_preview(right, desk)
        _bag(desk)["owned"].add("session_preview")


def _draw_facts(parent, desk) -> None:
    tk = _tk(desk)
    label = tk.Label(
        parent, text=_empty_facts(), fg="#A7B0C3", bg=_BG, anchor="w",
        justify="left", font=("Segoe UI", 11), wraplength=700,
    )
    label.pack(side="left", fill="x", expand=True, padx=8, pady=4)
    desk.ledger_session_facts = label


def _draw_chain(parent, desk) -> None:
    tk = _tk(desk)
    row = tk.Frame(parent, bg=_BG)
    row.pack(fill="x", padx=8, pady=4)
    tk.Button(
        row, text="Resume", command=lambda d=desk: d._on_launch(),
        bg=_CARD, fg=_INK, activebackground="#1E2430", activeforeground=_INK,
        relief="flat", bd=0, highlightthickness=0, font=_FONT, padx=10, pady=4,
        cursor="hand2",
    ).pack(side="left")
    tk.Label(row, text="\u2192", fg=_QUIET, bg=_BG, font=_FONT).pack(side="left", padx=6)
    desk.ledger_chain_harness = tk.Label(
        row, text="TUI / harness", fg=_INK, bg=_CARD, font=_FONT, padx=8, pady=4,
    )
    desk.ledger_chain_harness.pack(side="left")
    tk.Label(row, text="\u2192", fg=_QUIET, bg=_BG, font=_FONT).pack(side="left", padx=6)
    desk.ledger_chain_model = tk.Label(
        row, text="Model / agent", fg=_INK, bg=_CARD, font=_FONT, padx=8, pady=4,
    )
    desk.ledger_chain_model.pack(side="left")


def _draw_keywords(parent, desk) -> None:
    tk = _tk(desk)
    desk.ledger_keywords = tk.Label(
        parent, text=f"Location {_DASH}    Keywords {_DASH}",
        fg="#A7B0C3", bg=_BG, anchor="w", justify="left", font=_FONT,
        wraplength=700, padx=8, pady=4,
    )
    desk.ledger_keywords.pack(fill="x")


def _draw_text(parent, desk) -> None:
    tk = _tk(desk)
    tk.Label(parent, text="Session text", fg=_QUIET, bg=_BG, anchor="w").pack(fill="x", anchor="w")
    text = tk.Text(
        parent, bg=_CARD, fg=_INK, wrap="word", relief="flat",
        highlightthickness=0, bd=0, insertbackground=_INK, font=_FONT,
    )
    text.pack(fill="both", expand=True)
    desk.ledger_session_text = text


def _draw_preview(parent, desk) -> None:
    tk = _tk(desk)
    tk.Label(parent, text="Session preview", fg=_QUIET, bg=_BG, anchor="w").pack(fill="x", anchor="w")
    text = tk.Text(
        parent, bg=_CARD, fg=_INK, wrap="word", relief="flat",
        highlightthickness=0, bd=0, insertbackground=_INK, font=_FONT,
    )
    text.pack(fill="both", expand=True)
    text.configure(state="disabled")
    desk.ledger_session_preview = text


def fill(desk, hit) -> None:
    """Write one hit. A legal hit stays closed and does not show its path."""
    if not isinstance(hit, dict):
        _blank(desk)
        return
    owned = _bag(desk).get("owned") or set()
    for name in _PIECES:
        if name in owned or name == "session_actions":
            continue
        mod = _load(name)
        if mod is not None:
            _call(mod, "fill", desk, hit)
    _paint_owned(desk, hit)
    _paint_app(desk, hit)
    if hit.get("legal"):
        _seal(desk, hit)


def refresh(desk, hits) -> None:
    """Fill the selected hit, or leave every label on an em dash."""
    hit = _selected(desk, hits)
    if hit is not None:
        fill(desk, hit)
        return
    _blank(desk)


def _selected(desk, hits):
    index = getattr(desk, "selected_index", None)
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    own = getattr(desk, "hits", None)
    if isinstance(own, (list, tuple)) and 0 <= index < len(own) and isinstance(own[index], dict):
        return own[index]
    if isinstance(hits, (list, tuple)) and 0 <= index < len(hits) and isinstance(hits[index], dict):
        return hits[index]
    return None


def _blank(desk) -> None:
    facts = getattr(desk, "ledger_session_facts", None)
    if facts is not None:
        try:
            facts.configure(text=_empty_facts())
        except Exception:
            pass
    keys = getattr(desk, "ledger_keywords", None)
    if keys is not None:
        try:
            keys.configure(text=f"Location {_DASH}    Keywords {_DASH}")
        except Exception:
            pass
    for attr in ("ledger_chain_harness", "ledger_chain_model"):
        widget = getattr(desk, attr, None)
        if widget is None:
            continue
        try:
            widget.configure(text=_DASH)
        except Exception:
            pass
    app = _bag(desk).get("app")
    if app is not None:
        try:
            app.configure(text=_DASH, fg=_QUIET)
        except Exception:
            pass
    _write_text(getattr(desk, "ledger_session_text", None), "")
    _write_text(getattr(desk, "ledger_session_preview", None), "")


def _paint_owned(desk, hit: dict) -> None:
    owned = _bag(desk).get("owned") or set()
    if "session_facts" in owned:
        label = getattr(desk, "ledger_session_facts", None)
        if label is not None:
            label.configure(text=_facts_line(hit))
    if "session_keywords" in owned:
        label = getattr(desk, "ledger_keywords", None)
        if label is not None:
            label.configure(text=_keys_line(hit))
    if "session_chain" in owned:
        _paint_chain(desk, hit)
    if "session_text" in owned:
        _write_text(getattr(desk, "ledger_session_text", None), _text_body(hit))
    if "session_preview" in owned:
        _write_text(getattr(desk, "ledger_session_preview", None), _preview_body(hit))


def _paint_chain(desk, hit: dict) -> None:
    harness = getattr(desk, "ledger_chain_harness", None)
    model = getattr(desk, "ledger_chain_model", None)
    name = str(hit.get("harness") or "").strip()
    if harness is not None:
        harness.configure(text=f"{name} / harness" if name else "TUI / harness")
    if model is not None:
        shown = str(hit.get("model") or "").strip()
        model.configure(text=shown or "Model / agent")


def _paint_app(desk, hit: dict) -> None:
    app = _bag(desk).get("app")
    if app is None:
        return
    name = str(hit.get("harness") or hit.get("vendor") or hit.get("app") or "").strip()
    if hit.get("legal") and _looks_path(name):
        name = ""
    if not name:
        app.configure(text="App", fg=_ACCENT)
        return
    app.configure(text=name, fg=_VCOLOR.get(name.lower(), _ACCENT))


def _seal(desk, hit: dict) -> None:
    for attr in ("ledger_session_text", "ledger_session_preview"):
        _write_text(getattr(desk, attr, None), _CLOSED)
    secrets = _secrets(hit)
    if not secrets:
        return
    for attr in (
        "ledger_session_facts", "ledger_keywords",
        "ledger_chain_harness", "ledger_chain_model",
    ):
        _scrub(getattr(desk, attr, None), secrets)
    _scrub(_bag(desk).get("app"), secrets)


def _scrub(widget, secrets: list[str]) -> None:
    if widget is None:
        return
    try:
        kind = widget.winfo_class()
    except Exception:
        return
    if kind not in ("Label", "Message"):
        return
    text = str(widget.cget("text") or "")
    changed = text
    for secret in secrets:
        if secret and secret in changed:
            changed = changed.replace(secret, _DASH)
    if changed != text:
        widget.configure(text=changed)


def _write_text(widget, text: str) -> None:
    if widget is None:
        return
    try:
        if widget.winfo_class() != "Text":
            return
        state = str(widget.cget("state"))
    except Exception:
        return
    if state == "disabled":
        widget.configure(state="normal")
    widget.delete("1.0", "end")
    if text:
        widget.insert("1.0", text)
    if state == "disabled":
        widget.configure(state="disabled")


def _secrets(hit: dict) -> list[str]:
    found = []
    for key in ("path", "location", "cwd", "file"):
        raw = hit.get(key)
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if len(text) >= 3 and _looks_path(text):
            found.append(text)
    return found


def _looks_path(text: str) -> bool:
    return ":\\" in text or text.startswith("\\\\") or text.startswith("/") or "/" in text


def _empty_facts() -> str:
    return "    ".join((
        f"Date {_DASH}",
        f"Start {_DASH}",
        f"End {_DASH}",
        f"Size {_DASH}",
        f"Tokens input / output / total {_DASH}",
        f"Time {_DASH}",
        f"Topic {_DASH}",
        f"Path {_DASH}",
    ))


def _facts_line(hit: dict) -> str:
    legal = bool(hit.get("legal"))
    started = _clock(_first_epoch(hit, ("started", "start", "started_at", "created", "created_at", "updated")))
    ended = _clock(_first_epoch(hit, ("ended", "end", "ended_at", "end_time", "finished_at")))
    parts = [
        f"Date {started.date().isoformat() if started else _DASH}",
        f"Start {started.strftime('%H:%M') if started else _DASH}",
        f"End {ended.strftime('%H:%M') if ended else _DASH}",
        f"Size {_size_kb(hit)}",
        f"Tokens input / output / total {_tokens(hit)}",
        f"Time {_age(hit)}",
        f"Topic {_DASH if legal else _topic(hit)}",
        f"Path {_DASH if legal else (_plain(hit.get('path') or hit.get('location')) or _DASH)}",
    ]
    return "    ".join(parts)


def _keys_line(hit: dict) -> str:
    if hit.get("legal"):
        return f"Location {_DASH}    Keywords {_DASH}"
    loc = _plain(hit.get("path")) or _DASH
    return f"Location {loc}    Keywords {_keywords(hit)}"


def _text_body(hit: dict) -> str:
    if hit.get("legal"):
        return _CLOSED
    title = _plain(hit.get("title") or hit.get("vendor_id") or hit.get("id"))
    cwd = _plain(hit.get("cwd"))
    return f"{title}\n{cwd}"


def _preview_body(hit: dict) -> str:
    if hit.get("legal"):
        return _CLOSED
    app = _plain(hit.get("harness") or hit.get("vendor") or hit.get("app")) or _DASH
    return f"Source app  {app}\nAge  {_age(hit)}\nProject  {_topic(hit)}"


def _keywords(hit: dict) -> str:
    raw = hit.get("keywords")
    if isinstance(raw, (list, tuple)):
        words = [str(item).strip() for item in raw if str(item).strip()]
        if words:
            return " ".join(words[:6])
    if isinstance(raw, str) and raw.strip():
        return " ".join(raw.split()[:6])
    title = _plain(hit.get("title"))
    words = title.split()
    if not words:
        return _DASH
    return " ".join(words[:6])


def _topic(hit: dict) -> str:
    topic = hit.get("topic")
    if isinstance(topic, str) and topic.strip() and not _looks_path(topic.strip()):
        return topic.strip()
    for key in ("cwd", "project"):
        raw = hit.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        name = Path(raw.strip()).name
        if name and name not in (".", ".."):
            return name
    return _DASH


def _tokens(hit: dict) -> str:
    usage = hit.get("usage") if isinstance(hit.get("usage"), dict) else {}
    inn = _num(hit.get("input_tokens"))
    if inn is None:
        inn = _num(usage.get("input"))
    if inn is None:
        inn = _num(usage.get("input_tokens"))
    out = _num(hit.get("output_tokens"))
    if out is None:
        out = _num(usage.get("output"))
    if out is None:
        out = _num(usage.get("output_tokens"))
    total = None
    for key in ("tokens", "token_count", "total_tokens", "tokens_used", "context_tokens"):
        total = _num(hit.get(key))
        if total is not None:
            break
    if total is None:
        total = _num(usage.get("total"))
    if total is None:
        total = _num(usage.get("total_tokens"))
    if total is None and (inn is not None or out is not None):
        total = (inn or 0) + (out or 0)
    return f"{_fmt_tok(inn)} / {_fmt_tok(out)} / {_fmt_tok(total)}"


def _fmt_tok(value) -> str:
    if value is None:
        return _DASH
    return f"{int(round(value)):,}"


def _size_kb(hit: dict) -> str:
    size = hit.get("bytes")
    if isinstance(size, bool) or size is None:
        size = hit.get("size")
    if isinstance(size, bool) or not isinstance(size, (int, float)):
        return _DASH
    if size <= 0:
        return _DASH
    return f"{max(1, int(size) // 1024)} KB"


def _age(hit: dict) -> str:
    for key in ("updated", "last_activity", "ended", "started"):
        if key in hit and _epoch(hit.get(key)) is not None:
            return _age_from(hit.get(key))
    return _DASH


def _age_from(stamp) -> str:
    n = _epoch(stamp)
    if n is None:
        return _DASH
    mins = max(0, int((datetime.now().timestamp() - n) / 60))
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


def _first_epoch(hit: dict, keys: tuple[str, ...]):
    for key in keys:
        if key not in hit:
            continue
        found = _epoch(hit.get(key))
        if found is not None:
            return found
    return None


def _clock(epoch):
    if epoch is None:
        return None
    try:
        return datetime.fromtimestamp(epoch)
    except (OSError, OverflowError, ValueError):
        return None


def _epoch(stamp):
    if isinstance(stamp, datetime):
        return stamp.timestamp()
    if isinstance(stamp, str):
        text = stamp.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    if isinstance(stamp, bool) or stamp is None:
        return None
    try:
        n = float(stamp)
    except (TypeError, ValueError):
        return None
    if n != n or n <= 0:
        return None
    if n > 100000000000:
        n = n / 1000.0
    if n < 1000000000:
        return None
    return n


def _num(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


def _plain(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").strip()
