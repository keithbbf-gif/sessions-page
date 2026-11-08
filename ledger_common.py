"""Ledger display helpers. Stdlib only. No widgets and no session reads."""
from __future__ import annotations

from datetime import datetime

__all__ = (
    "title_of",
    "project_of",
    "age_text",
    "vendor_color",
    "source_label",
    "source_kind",
    "stamp_dt",
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
_ANTIGRAVITY = frozenset({
    "antigravity", "antigravity-ide", "antigravity-cli", "agy",
})
_CHAT = frozenset({"claude_desktop", "openwork", "cowork"})
_EM = "—"
# Seconds above this are epoch milliseconds. Same cut as the desk.
_MS_CUT = 100_000_000_000


def _harness(hit) -> str:
    if not isinstance(hit, dict):
        return ""
    value = hit.get("harness")
    if value is None or str(value).strip() == "":
        value = hit.get("vendor")
    return str(value or "").strip()


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


def title_of(hit) -> str:
    if not isinstance(hit, dict):
        return ""
    if hit.get("legal"):
        return "Legal session"
    return str(hit.get("title") or hit.get("vendor_id") or hit.get("id") or "")


def project_of(hit) -> str:
    if not isinstance(hit, dict) or hit.get("legal"):
        return ""
    cwd = str(hit.get("cwd") or "").replace("/", "\\").rstrip("\\")
    if not cwd:
        return ""
    return cwd.split("\\")[-1]


def stamp_dt(stamp) -> datetime | None:
    seconds = _epoch_seconds(stamp)
    if seconds is None:
        return None
    try:
        return datetime.fromtimestamp(seconds)
    except (OSError, OverflowError, ValueError):
        return None


def age_text(stamp) -> str:
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
        # One digit stays "hr" (8hr). Two digits take the plural (22hrs).
        return f"{hours}hr" if hours < 10 else f"{hours}hrs"
    days = hours // 24
    if days < 14:
        return f"{days} day" if days == 1 else f"{days} days"
    weeks = days // 7
    if weeks < 8:
        return f"{weeks} wks"
    months = max(1, days // 30)
    return f"{months} month" if months == 1 else f"{months} months"


def vendor_color(harness: str) -> str:
    return _VCOLOR.get(str(harness or "").lower(), "#A7B0C3")


def source_kind(hit) -> str:
    name = _harness(hit).lower()
    if name == "antigravity-ide":
        return "TUI"
    if name in _CHAT:
        return "Chat"
    return "CLI"


def _looks_like_app(name: str) -> bool:
    if source_kind({"harness": name}) == "Chat":
        return True
    if name.lower().endswith(".exe"):
        return True
    return any(ch.isupper() for ch in name) or (" " in name)


def source_label(hit) -> str:
    raw = _harness(hit)
    key = raw.lower()
    if key == "grok":
        return "Grok.exe"
    if key in _ANTIGRAVITY:
        return "Antigravity.exe"
    if key == "claude":
        return "claude"
    if not raw:
        return ""
    if key.endswith(".exe"):
        return raw
    if _looks_like_app(raw):
        return f"{raw}.exe"
    return raw
