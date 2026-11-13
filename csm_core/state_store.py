"""cmSessions UI state store.

Persists the last selected session id and the last view name.
Also remembers the path of var/index.jsonl and the last index time
in var/index_state.json. The index file itself is not written.
Session bodies are not read.
Transcript text is never read into this store and never written to disk.
"""

from __future__ import annotations

import json
import math
import os
import stat
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

VIEWS = ("table", "session", "calendar", "projects")
DEFAULT_VIEW = "table"
SCHEMA = "cmsessions-ui-state/1"

_VIEW_SET = frozenset(VIEWS)
_MAX_SESSION_ID = 512
_SESSION_KEYS = ("selected_session_id", "last_selected_session_id", "session_id")
_VIEW_KEYS = ("view", "view_name", "last_view")
_UNSET = object()

PathLike = Union[str, os.PathLike[str]]


class UiStateError(ValueError):
    """Raised when a session id or view name cannot be stored."""


@dataclass(frozen=True)
class UiState:
    """Last selection and view. Neither field holds transcript text."""

    selected_session_id: Optional[str]
    view: str


def default_path() -> Path:
    """Product var/ui_state.json. Does not create the directory."""
    return Path(__file__).resolve().parents[1] / "var" / "ui_state.json"


def normalize_view(value: Any, *, strict: bool) -> str:
    """Return a known view name. Unknown values raise or fall back to table."""
    if isinstance(value, str):
        name = value.strip().lower()
        if name in _VIEW_SET:
            return name
    if strict:
        raise UiStateError(
            "view must be one of: table, session, calendar, projects"
        )
    return DEFAULT_VIEW


def normalize_session_id(value: Any, *, strict: bool) -> Optional[str]:
    """Keep a single-line session id. Blank clears it. Bodies are refused."""
    if value is None:
        return None
    if not isinstance(value, str):
        if strict:
            raise UiStateError("session id must be a string")
        return None
    text = value.strip()
    if not text:
        return None
    if (
        len(text) > _MAX_SESSION_ID
        or any(ch in text for ch in ("\n", "\r", "\x00"))
        or text[0] in "[{"
    ):
        if strict:
            raise UiStateError("session id must be an id, not transcript text")
        return None
    return text


def _pick(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


class UiStateStore:
    """Load and save the last selected session id and the last view name."""

    def __init__(self, path: Optional[PathLike] = None) -> None:
        self.path = Path(path) if path is not None else default_path()
        self.selected_session_id: Optional[str] = None
        self.view: str = DEFAULT_VIEW
        self._lock = threading.RLock()

    def snapshot(self) -> UiState:
        return UiState(self.selected_session_id, self.view)

    def set_selected_session(self, session_id: Optional[str]) -> None:
        """Remember a session id. None or blank clears it. Text bodies raise."""
        self.selected_session_id = normalize_session_id(session_id, strict=True)

    def set_view(self, view: str) -> None:
        """Remember a view. Only table, session, calendar, or projects."""
        self.view = normalize_view(view, strict=True)

    def load(self) -> UiState:
        """Read the last id and view. Missing or damaged files use defaults.

        Extra keys, including any transcript field, are ignored.
        """
        with self._lock:
            self.selected_session_id = None
            self.view = DEFAULT_VIEW
            try:
                raw = self.path.read_text(encoding="utf-8")
                payload = json.loads(raw)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
                return self.snapshot()
            if not isinstance(payload, dict):
                return self.snapshot()
            self.selected_session_id = normalize_session_id(
                _pick(payload, _SESSION_KEYS), strict=False
            )
            self.view = normalize_view(_pick(payload, _VIEW_KEYS), strict=False)
            return self.snapshot()

    def save(self) -> UiState:
        """Write only schema, selected_session_id, and view. Replaces atomically."""
        with self._lock:
            session_id = normalize_session_id(self.selected_session_id, strict=True)
            view = normalize_view(self.view, strict=True)
            self.selected_session_id = session_id
            self.view = view
            document = {
                "schema": SCHEMA,
                "selected_session_id": session_id,
                "view": view,
            }
            if set(document) != {"schema", "selected_session_id", "view"}:
                raise UiStateError("ui state document has unexpected fields")
            text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            try:
                with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                    handle.write(text)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, self.path)
            except Exception:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                raise
            return self.snapshot()


def load_ui_state(path: Optional[PathLike] = None) -> UiState:
    """Load the last selected session id and the last view name."""
    return UiStateStore(path).load()


def save_ui_state(
    path: Optional[PathLike] = None,
    *,
    selected_session_id: Any = _UNSET,
    view: Any = _UNSET,
) -> UiState:
    """Update and store the last session id, the last view, or both.

    Omitted fields keep the value already on disk. Passed fields replace it.
    """
    store = UiStateStore(path)
    store.load()
    if selected_session_id is not _UNSET:
        store.set_selected_session(selected_session_id)
    if view is not _UNSET:
        store.set_view(view)
    return store.save()


INDEX_RELATIVE = "var/index.jsonl"
INDEX_FILE_NAME = "index.jsonl"
INDEX_STATE_NAME = "index_state.json"
INDEX_STATE_SCHEMA = "cmsessions-index-state/1"

_INDEX_LOCK = threading.RLock()


class IndexStateError(ValueError):
    """Raised when a last-index time cannot be stored."""


@dataclass(frozen=True)
class IndexState:
    """Path of var/index.jsonl and the last index time. No index rows."""

    index_path: str
    location: str
    last_index_time: Optional[float]


def _product_root() -> Path:
    """Same root as engine.product_root. Does not create var/."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def index_jsonl_path(root: Optional[PathLike] = None) -> Path:
    """Absolute path of var/index.jsonl. Does not create or write that file."""
    base = Path(root) if root is not None else _product_root()
    return base / "var" / INDEX_FILE_NAME


def index_state_path(root: Optional[PathLike] = None) -> Path:
    """Sidecar that remembers the index path and time. Not the index."""
    base = Path(root) if root is not None else _product_root()
    return base / "var" / INDEX_STATE_NAME


def _require_time(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IndexStateError("last index time must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise IndexStateError("last index time must be a finite timestamp")
    return number


def _optional_time(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return _require_time(value)
    except IndexStateError:
        return None


def _index_mtime(path: Path) -> Optional[float]:
    """Stat the index file only. Do not follow links or read bytes."""
    try:
        st = path.stat(follow_symlinks=False)
    except OSError:
        return None
    if not stat.S_ISREG(st.st_mode):
        return None
    return _optional_time(st.st_mtime)


def _stored_index(path: Path) -> tuple[Optional[float], bool]:
    """Return (remembered time, whether a record was readable).

    Does not open session bodies or the index file.
    """
    try:
        if path.is_symlink() or not path.is_file():
            return None, False
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return None, False
    if not isinstance(payload, dict):
        return None, False
    return _optional_time(payload.get("last_index_time")), True


def _effective_time(
    stored: Optional[float], observed: Optional[float], explicit: Optional[float]
) -> Optional[float]:
    stamps = [stamp for stamp in (stored, observed, explicit) if stamp is not None]
    if not stamps:
        return None
    return max(stamps)


def load_index_state(root: Optional[PathLike] = None) -> IndexState:
    """Return the index path and the last index time.

    The path is always var/index.jsonl under the product root. A missing
    sidecar falls back to the index file mtime. Session bodies are not read
    and the index is not written.
    """
    with _INDEX_LOCK:
        location = index_jsonl_path(root)
        stored, _found = _stored_index(index_state_path(root))
        when = _effective_time(stored, _index_mtime(location), None)
        return IndexState(INDEX_RELATIVE, str(location), when)


def last_index_time(root: Optional[PathLike] = None) -> Optional[float]:
    """Remembered last index time, else the index file mtime, else None."""
    return load_index_state(root).last_index_time


def remember_index(
    when: Any = None,
    root: Optional[PathLike] = None,
) -> IndexState:
    """Remember var/index.jsonl and the last index time.

    Writes var/index_state.json only. Does not write index.jsonl and does
    not read session bodies. when is a unix timestamp. When omitted, the
    time is the index file mtime if that file is a regular file, else the
    time already remembered.
    """
    explicit = None if when is None else _require_time(when)
    with _INDEX_LOCK:
        location = index_jsonl_path(root)
        sidecar = index_state_path(root)
        if sidecar.name == INDEX_FILE_NAME:
            raise IndexStateError("refusing to write the index")
        stored, _found = _stored_index(sidecar)
        stamp = _effective_time(stored, _index_mtime(location), explicit)
        document = {
            "schema": INDEX_STATE_SCHEMA,
            "index_path": INDEX_RELATIVE,
            "last_index_time": stamp,
        }
        if set(document) != {"schema", "index_path", "last_index_time"}:
            raise IndexStateError("index state document has unexpected fields")
        if document["index_path"] != INDEX_RELATIVE:
            raise IndexStateError("refusing to remember a path other than var/index.jsonl")
        text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        if sidecar.is_symlink():
            raise OSError("index state file is a symlink")
        parent = sidecar.parent
        if parent.is_symlink():
            raise OSError("var directory is a symlink")
        parent.mkdir(parents=True, exist_ok=True)
        tmp = sidecar.with_name(sidecar.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, sidecar)
        except Exception:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        return IndexState(INDEX_RELATIVE, str(location), stamp)
