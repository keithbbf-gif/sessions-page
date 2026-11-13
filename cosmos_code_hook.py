"""In-process Sessions plugin for COSMOS CODE.

The standalone app is the desk window and does not need this hook.
COSMOS calls the same engine through cosmos_session_tools_kit.py.
This descriptor is the Cosmos Code plug. It does not open a port,
start a process, or write live/. The applied cosmos_code tree has
no plugin list to extend.

A pointer names harness cosmos-code, the attempt directory, and the
door and model on the first session/start line of that worktree's
session.jsonl. That file is not a transcript and is not parsed as one.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "cmsessions-cosmos-code-hook/1"
HARNESS = "cosmos-code"
_SESSION_NAME = "session.jsonl"


def descriptor() -> dict:
    """Name the Sessions plugin. It stays in-process on the desk."""
    return {
        "schema": SCHEMA,
        "name": "sessions",
        "via": "in-process",
        "module": "plugin_api",
        "port": None,
        "window": "desk",
        "writes_live": False,
        "verbs": ["find", "load", "resume", "formats"],
    }


def open_plugin() -> dict:
    """Return plugin_api.snapshot(). A missing module is ENGINE_MISSING."""
    try:
        import plugin_api
    except ImportError:
        return {
            "schema": SCHEMA,
            "kind": "ENGINE_MISSING",
            "module": "plugin_api",
        }
    return plugin_api.snapshot()


class HookError(RuntimeError):
    """kind in {BAD_POINTER, NO_SESSION, NO_START}."""

    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        super().__init__(detail or kind)


def _locate(worktree: str | Path) -> tuple[Path, Path]:
    """Attempt directory and its session.jsonl. Does not create either."""
    if isinstance(worktree, Path):
        raw = worktree
    elif isinstance(worktree, str) and worktree.strip():
        raw = Path(worktree.strip())
    else:
        raise HookError("BAD_POINTER", "attempt directory is required")
    if raw.is_file():
        if raw.name.lower() != _SESSION_NAME:
            raise HookError("BAD_POINTER", "expected the attempt directory or session.jsonl")
        attempt, session = raw.parent, raw
    elif raw.is_dir():
        attempt, session = raw, raw / _SESSION_NAME
    else:
        raise HookError("NO_SESSION", str(raw))
    if not session.is_file():
        raise HookError("NO_SESSION", str(session))
    return attempt.resolve(), session


def _start_line(session: Path) -> dict:
    """First event only, and only when it is session/start. Later lines stay unread."""
    try:
        with session.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise HookError("BAD_POINTER", "session/start line is not json") from exc
                if not isinstance(row, dict) or row.get("ev") != "session/start":
                    raise HookError("NO_START", "first event is not session/start")
                return row
    except HookError:
        raise
    except UnicodeDecodeError as exc:
        raise HookError("BAD_POINTER", "session/start line is not utf-8") from exc
    except OSError as exc:
        raise HookError("NO_SESSION", str(session)) from exc
    raise HookError("NO_START", "no session/start line")


def _text(row: dict, name: str) -> str | None:
    value = row.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise HookError("BAD_POINTER", f"{name} must be a string")
    text = value.strip()
    return text or None


def pointer(worktree: str | Path) -> dict:
    """Harness, attempt directory, door, and model. No port and no live write."""
    attempt, session = _locate(worktree)
    row = _start_line(session)
    return {
        "schema": SCHEMA,
        "harness": HARNESS,
        "attempt": str(attempt),
        "door": _text(row, "door"),
        "model": _text(row, "model"),
        "port": None,
        "writes_live": False,
        "resume": "POINTER",
    }


def main() -> int:
    """Print port and writes_live. Does not bind a socket."""
    desc = descriptor()
    port = "null" if desc.get("port") is None else str(desc.get("port"))
    live = "false" if desc.get("writes_live") is False else str(desc.get("writes_live")).lower()
    print(f"PORT {port}")
    print(f"WRITES_LIVE {live}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
