#!/usr/bin/env python3
"""Shared session record. Stdlib only. No parser, no store walk, no spawn.

Vendor words stay in the status table. A record stores active, idle,
crashed, or finished, and it does not carry transcript text.
"""
from __future__ import annotations

from pathlib import Path

SCHEMA = "cmsessions-record/1"

_FIELDS = (
    "id", "vendor", "model", "harness", "project", "title",
    "started", "last_activity", "duration", "status", "tokens",
    "parent", "paths", "location", "tags", "favorite",
)

_VENDORS = {
    "claude": "claude",
    "claude_desktop": "claude",
    "codex": "codex",
    "grok": "grok",
    "gemini": "gemini",
    "antigravity": "antigravity",
    "antigravity-ide": "antigravity",
    "antigravity-cli": "antigravity",
    "agy": "antigravity",
}

_STATUS = {
    "active": "active",
    "running": "active",
    "live": "active",
    "busy": "active",
    "in_progress": "active",
    "working": "active",
    "ongoing": "active",
    "current": "active",
    "open": "active",
    "idle": "idle",
    "inactive": "idle",
    "paused": "idle",
    "waiting": "idle",
    "stalled": "idle",
    "suspended": "idle",
    "crashed": "crashed",
    "crash": "crashed",
    "error": "crashed",
    "failed": "crashed",
    "failure": "crashed",
    "aborted": "crashed",
    "killed": "crashed",
    "interrupted": "crashed",
    "corrupt": "crashed",
    "corrupted": "crashed",
    "finished": "finished",
    "complete": "finished",
    "completed": "finished",
    "done": "finished",
    "closed": "finished",
    "archived": "finished",
    "ended": "finished",
    "success": "finished",
    "exited": "finished",
    "terminated": "finished",
}

_MODEL_KEYS = ("model", "model_id", "current_model_id", "current_model", "model_name")
_STARTED_KEYS = ("started", "start", "started_at", "start_time", "created", "created_at")
_TOKEN_KEYS = (
    "tokens", "token_count", "total_tokens", "tokens_used",
    "token_spend", "n_tokens", "usage_tokens",
)
_PARENT_KEYS = (
    "parent", "parent_id", "parent_session_id", "parent_thread", "parent_thread_id",
)
_STATUS_KEYS = ("status", "state", "session_status", "session_state")
_QUERY_KEYS = ("title", "project", "id", "location")


def vendor_of(harness: str) -> str:
    key = str(harness or "").strip().lower()
    return _VENDORS.get(key, "other")


def _token(value) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text


def status_of(hit: dict) -> str:
    """Map one hit onto active, idle, crashed, or finished."""
    if not isinstance(hit, dict):
        return "idle"
    if hit.get("legal") is True:
        return "finished"
    for key in _STATUS_KEYS:
        mapped = _STATUS.get(_token(hit.get(key)))
        if mapped:
            return mapped
    if hit.get("crashed") is True:
        return "crashed"
    if hit.get("active") is True:
        return "active"
    if hit.get("finished") is True:
        return "finished"
    return "idle"


def _opt_str(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
        if number.is_integer():
            return int(number)
        return number
    if isinstance(value, dict):
        for key in ("total_tokens", "total", "tokens"):
            found = _number(value.get(key))
            if found is not None:
                return found
    return None


def _first_number(hit: dict, keys: tuple[str, ...]):
    for key in keys:
        if key not in hit:
            continue
        found = _number(hit.get(key))
        if found is not None:
            return found
    usage = hit.get("usage")
    found = _number(usage)
    if found is not None:
        return found
    return None


def _first_str(hit: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        text = _opt_str(hit.get(key))
        if text:
            return text
    return None


def _when(hit: dict, keys: tuple[str, ...]):
    for key in keys:
        if key not in hit or hit.get(key) in (None, ""):
            continue
        value = hit.get(key)
        number = _number(value)
        if number is not None:
            return number
        text = _opt_str(value)
        if text:
            return text
    return None


def _project(cwd) -> str | None:
    text = _opt_str(cwd)
    if not text:
        return None
    name = Path(text).name
    return name or None


def _strings(value) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    rows = []
    for item in value:
        if isinstance(item, Path):
            text = str(item).strip()
        else:
            text = _opt_str(item) or ""
        if text:
            rows.append(text)
    return rows


def _flag(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    text = _opt_str(value)
    return bool(text) and text.lower() in {"1", "true", "yes", "y"}


def _id_of(hit: dict) -> str:
    for key in ("id", "vendor_id"):
        value = hit.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return ""


def _location(hit: dict) -> str | None:
    value = hit.get("path")
    if value is None:
        value = hit.get("location")
    if isinstance(value, Path):
        text = str(value).strip()
        return text or None
    return _opt_str(value)


def to_record(hit: dict) -> dict:
    if not isinstance(hit, dict):
        raise TypeError("hit must be a dict")
    harness = str(hit.get("harness") or "").strip()
    paths = _strings(hit.get("paths"))
    if not paths:
        paths = _strings(hit.get("files") or hit.get("paths_touched"))
    row = {
        "id": _id_of(hit),
        "vendor": vendor_of(harness),
        "model": _first_str(hit, _MODEL_KEYS),
        "harness": harness,
        "project": _project(hit.get("cwd") if "cwd" in hit else hit.get("project")),
        "title": _opt_str(hit.get("title")),
        "started": _when(hit, _STARTED_KEYS),
        "last_activity": _number(hit.get("updated")) if "updated" in hit else _number(hit.get("last_activity")),
        "duration": None,
        "status": status_of(hit),
        "tokens": _first_number(hit, _TOKEN_KEYS),
        "parent": _first_str(hit, _PARENT_KEYS),
        "paths": paths,
        "location": _location(hit),
        "tags": _strings(hit.get("tags")),
        "favorite": _flag(hit.get("favorite", False)),
    }
    return {key: row[key] for key in _FIELDS}


def records_from_hits(hits: list[dict]) -> list[dict]:
    rows = []
    for hit in hits:
        try:
            rows.append(to_record(hit))
        except Exception:
            continue
    return rows


def filter_records(rows, vendors=None, query="", status="") -> list[dict]:
    """Keep the vendor set, then interleave by last activity. Crashed stays."""
    chosen = None
    if vendors:
        source = [vendors] if isinstance(vendors, str) else vendors
        chosen = {str(item).strip().lower() for item in source if str(item).strip()}
        if not chosen:
            chosen = None
    needle = str(query or "").strip().lower()
    want = str(status or "").strip().lower()
    kept = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        vendor = str(row.get("vendor") or "").strip().lower()
        if chosen is not None and vendor not in chosen:
            continue
        if want and str(row.get("status") or "").strip().lower() != want:
            continue
        if needle:
            matched = False
            for key in _QUERY_KEYS:
                if needle in str(row.get(key) or "").lower():
                    matched = True
                    break
            if not matched:
                continue
        kept.append(row)

    def activity(row: dict):
        stamp = _number(row.get("last_activity"))
        if stamp is None:
            return (1, 0.0)
        return (0, -float(stamp))

    kept.sort(key=activity)
    return kept
