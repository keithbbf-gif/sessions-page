"""Persist theme, density, and page_size at the product var path.

The file is var/settings.json. Unfrozen, var is beside engine.py
(engine.product_root() / "var"). Frozen, var is beside the executable.
A write lands in a temp file in that directory, is fsynced, then os.replace
swaps it into place (atomic replace on the same volume). Tokens, passwords,
and other secrets are refused and are not stored.

Corrupt JSON is renamed to settings.json.bak once. Later loads and saves
do not replace or delete that backup.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Mapping

SETTINGS_NAME = "settings.json"
FIELDS = ("theme", "density", "page_size")

DEFAULT_THEME = "dark"
DEFAULT_DENSITY = "comfortable"
DEFAULT_PAGE_SIZE = 100

THEMES = ("dark", "light", "clam")
DENSITIES = ("comfortable", "compact", "dense")
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 2000

_IDENT = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_SECRET_KEY = re.compile(
    r"(secret|password|passwd|token|api[_-]?key|credential|"
    r"private[_-]?key|authorization|cookie|bearer)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(AIza[0-9A-Za-z\-_]{10,}|sk-[A-Za-z0-9]{8,}|"
    r"AQ\.[A-Za-z0-9_\-]{10,}|Bearer\s+\S+|-----BEGIN[A-Z ]+-----)",
)

_LOCK = threading.Lock()


def defaults() -> dict[str, Any]:
    return {
        "theme": DEFAULT_THEME,
        "density": DEFAULT_DENSITY,
        "page_size": DEFAULT_PAGE_SIZE,
    }


def _product_root() -> Path:
    """Same root engine.product_root uses. Unfrozen root holds engine.py."""
    try:
        import engine
    except ImportError:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent
    return engine.product_root()


def settings_path() -> Path:
    return _product_root() / "var" / SETTINGS_NAME


def _secret_key(key: object) -> bool:
    return _SECRET_KEY.search(str(key)) is not None


def _ident(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if _SECRET_VALUE.search(value):
        raise ValueError("refusing to store secrets")
    text = value.strip().lower()
    if not _IDENT.fullmatch(text):
        raise ValueError(f"{field} must be a short identifier")
    return text


def _page_size(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("page_size must be an int")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("page_size must be an int")
        value = int(value)
    if not isinstance(value, int):
        raise ValueError("page_size must be an int")
    if value < MIN_PAGE_SIZE or value > MAX_PAGE_SIZE:
        raise ValueError("page_size is out of range")
    return value


def _coerce_field(key: str, value: Any) -> Any:
    if key == "theme":
        return _ident(value, "theme")
    if key == "density":
        return _ident(value, "density")
    if key == "page_size":
        return _page_size(value)
    raise ValueError("unknown settings field")


def _quarantine_once(dest: Path) -> None:
    """Rename a corrupt settings file to settings.json.bak a single time.

    An existing bak is left in place. This never deletes or replaces it.
    """
    if dest.is_symlink():
        return
    backup = dest.with_name("settings.json.bak")
    try:
        if os.path.lexists(backup):
            return
        os.rename(dest, backup)
    except OSError:
        return


def _load_unlocked(path: Path | None) -> dict[str, Any]:
    dest = Path(path) if path is not None else settings_path()
    loaded = defaults()
    try:
        if dest.is_symlink() or not dest.is_file():
            return loaded
        text = dest.read_text(encoding="utf-8")
    except UnicodeError:
        _quarantine_once(dest)
        return loaded
    except OSError:
        return loaded
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        _quarantine_once(dest)
        return loaded
    if not isinstance(data, dict):
        return loaded
    for key in FIELDS:
        if key not in data or _secret_key(key):
            continue
        try:
            loaded[key] = _coerce_field(key, data[key])
        except ValueError:
            continue
    return loaded


def load_settings(path: Path | None = None) -> dict[str, Any]:
    """Return theme, density, and page_size.

    A missing or unreadable file returns defaults. Unknown keys, including
    anything that looks like a secret, are ignored. Corrupt JSON returns
    defaults and is renamed to settings.json.bak once. A bak already on
    disk is not replaced or deleted.
    """
    with _LOCK:
        return _load_unlocked(path)


def save_settings(
    settings: Mapping[str, Any] | None = None,
    path: Path | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Write theme, density, and page_size. Return the stored record.

    Only those three fields are written. A partial update keeps the other
    stored fields. Secret-like keys or values raise ValueError and do not
    touch the file.
    """
    if settings is None and not fields:
        raise TypeError("save_settings requires settings or fields")
    incoming: dict[str, Any] = {}
    if settings is not None:
        if isinstance(settings, (str, bytes)) or not isinstance(settings, Mapping):
            raise TypeError("settings must be a mapping")
        incoming.update(settings)
    incoming.update(fields)
    for key in incoming:
        if _secret_key(key):
            raise ValueError("refusing to store secrets")
    with _LOCK:
        merged = _load_unlocked(path)
        for key in FIELDS:
            if key in incoming:
                merged[key] = _coerce_field(key, incoming[key])
        stored = {key: merged[key] for key in FIELDS}
        payload = json.dumps(stored, indent=2, sort_keys=True) + "\n"
        if _SECRET_VALUE.search(payload):
            raise ValueError("refusing to store secrets")
        _write_unlocked(path, payload)
        return stored


def _fsync_dir(directory: Path) -> None:
    """Best-effort directory fsync so the replaced name survives a crash."""
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(directory, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        return
    finally:
        os.close(fd)


def _replace_same_dir(tmp: Path, dest: Path) -> None:
    """os.replace only when the temp file already sits beside the target."""
    same = os.path.normcase(os.path.abspath(tmp.parent)) == os.path.normcase(
        os.path.abspath(dest.parent)
    )
    if not same:
        raise OSError("temp file is not in the target directory")
    last_exc: OSError | None = None
    for _try in range(8):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(0.05)
    if last_exc is None:
        raise OSError("replace failed")
    raise last_exc


def _write_unlocked(path: Path | None, payload: str) -> None:
    dest = Path(path) if path is not None else settings_path()
    if dest.is_symlink():
        raise OSError("settings file is a symlink")
    parent = dest.parent
    if parent.is_symlink():
        raise OSError("var directory is a symlink")
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=parent)
    tmp = Path(tmp_name)
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_same_dir(tmp, dest)
        replaced = True
    except Exception:
        if not replaced:
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    _fsync_dir(parent)
