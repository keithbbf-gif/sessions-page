#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sessions-page engine. Stdlib only. No Core, no ledger, no live-tree write.

Find, import, export, index, recover, and resume across the harnesses that
keep a local session store. Legal transcripts are counted and not opened.
Crash recovery replaces a file from a verified backup after staging the
original. It does not repair sqlite or JSONL in place.
"""
from __future__ import annotations

import gc
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

SCHEMA = "cosmos-session-tools-result/1"
TRANSCRIPT = "cosmos-transcript/1"
INDEX_SCHEMA = "sessions-page-index/1"
MAX_BYTES = 48 * 1024 * 1024
HEAD_BYTES = 8192
PREVIEW_WHOLE = 512 * 1024
DEFAULT_LIMIT = 200

VERBS = (
    "find", "preview", "import", "export", "index", "recover", "resume",
    "scan", "load", "convert", "diff", "check", "anonymize",
    "crash-recover", "strip", "strip_dry", "doi",
)

HARNESSES = (
    "grok", "claude", "codex", "cursor", "cowork", "openwork",
    "claude_desktop", "gemini",
    "hermes", "cline", "kilo", "roo", "pi", "copilot", "continue",
    "aider", "goose", "qwen", "amp", "openhands", "crush", "amazonq",
    "dsh", "factory", "windsurf", "augment",
)

_ILLEGAL = ':*?"<>|\\/'
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_ROLLOUT = re.compile(
    r"^rollout-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-"
    r"([0-9a-fA-F-]{36})\.jsonl$"
)
_REDACT = (
    ("slack-webhook", re.compile(r"https://hooks\.slack\.com/services/\S+")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{12,}")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("xai-key", re.compile(r"\bxai-[A-Za-z0-9_\-]{16,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("google-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.=]{12,}")),
    ("secret-assign", re.compile(
        r"(?i)\b(api[_\-]?key|access[_\-]?token|auth[_\-]?token|secret|"
        r"password|passwd|client[_\-]?secret)\b\s*[:=]\s*[\"']?"
        r"([A-Za-z0-9_\-\.\/\+=]{8,})[\"']?")),
    ("long-hex", re.compile(r"\b[0-9a-fA-F]{40,}\b")),
)
_STRIP_TAGS = re.compile(
    r"<(system-reminder|user_info|rules|env|local-command-stdout|"
    r"local-command-stderr|command-name|command-message|command-args|"
    r"function_results|task-notification|todo_reminder)>.*?</\1>",
    re.S | re.I,
)
_TOOL_ROLES = frozenset({"tool_call", "tool_result", "system", "thinking"})
PREFIX = {
    "grok": "grok",
    "claude": "cc",
    "codex": "cdx",
    "cursor": "cur",
    "cowork": "cow",
    "openwork": "ow",
    "claude_desktop": "cd",
    "gemini": "gem",
    "hermes": "hm",
    "cline": "cln",
    "kilo": "kilo",
    "roo": "roo",
    "pi": "pi",
    "copilot": "cop",
    "continue": "con",
    "aider": "aid",
    "goose": "goo",
    "qwen": "qw",
    "amp": "amp",
    "openhands": "oh",
    "crush": "cru",
    "amazonq": "aq",
    "dsh": "dsh",
    "factory": "fac",
    "windsurf": "wnd",
    "augment": "aug",
}
_EDITORS = (
    "Code", "Code - Insiders", "Cursor", "Windsurf", "VSCodium", "Cline", "Kilo",
)
_MESSAGE_HARNESSES = frozenset({
    "claude", "claude_desktop", "cursor", "gemini", "pi", "qwen", "continue",
    "goose", "amp", "crush", "openhands", "factory", "windsurf", "augment",
    "dsh", "amazonq", "cline", "kilo", "roo", "aider",
})


class PageError(RuntimeError):
    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        super().__init__(detail or kind)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def legal_id(prefix: str, vendor_id: str) -> str:
    raw = "".join(c for c in str(vendor_id) if c not in _ILLEGAL)
    return f"{prefix}-{raw}" if raw else f"{prefix}-unnamed"


def _blob(value: str) -> str:
    return str(value or "").replace("/", "\\").lower()


def is_legal(path: str = "", stream: str = "", cwd: str = "", title: str = "") -> bool:
    if str(stream or "").lower() == "legal":
        return True
    blob = " ".join(_blob(x) for x in (path, cwd, title))
    marks = ("\\legal\\", "\\legal", "p:\\legal", "v:\\ai\\legal", "\\abraxas\\")
    return any(m in blob for m in marks)


def product_root() -> Path:
    return Path(__file__).resolve().parent


def var_dir() -> Path:
    d = product_root() / "var"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _existing_file(candidates: list[Path]) -> Path | None:
    for path in candidates:
        try:
            if path.is_file() and not path.is_symlink():
                return path
        except OSError:
            continue
    return None


def _existing_dir(candidates: list[Path]) -> Path | None:
    for path in candidates:
        try:
            if path.is_dir() and not path.is_symlink():
                return path
        except OSError:
            continue
    return None


def _env_or(key: str, fallback: Path | None) -> Path | None:
    raw = os.environ.get(key)
    return Path(raw) if raw else fallback


def _editor_task_dirs(extension_ids: tuple[str, ...], cli_dirs: tuple[Path, ...]) -> list[Path]:
    found: list[Path] = []
    appdata = os.environ.get("APPDATA") or ""
    if appdata:
        base = Path(appdata)
        for editor in _EDITORS:
            storage = base / editor / "User" / "globalStorage"
            for ext in extension_ids:
                tasks = storage / ext / "tasks"
                try:
                    if tasks.is_dir() and not tasks.is_symlink():
                        found.append(tasks)
                except OSError:
                    continue
    for path in cli_dirs:
        try:
            if path.is_dir() and not path.is_symlink():
                found.append(path)
        except OSError:
            continue
    return found


def _is_real_dir(path: Path) -> bool:
    try:
        return path.is_dir() and not path.is_symlink()
    except OSError:
        return False


def _is_real_file(path: Path) -> bool:
    try:
        return path.is_file() and not path.is_symlink()
    except OSError:
        return False


def _same_path(path: Path, peers: list[Path]) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    for peer in peers:
        try:
            if peer.resolve() == resolved:
                return True
        except OSError:
            if peer == path:
                return True
    return False


def _xdg_data() -> Path:
    raw = os.environ.get("XDG_DATA_HOME")
    return Path(raw) if raw else Path.home() / ".local" / "share"


def _jetbrains_task_dirs(extension_ids: tuple[str, ...]) -> list[Path]:
    appdata = os.environ.get("APPDATA") or ""
    if not appdata:
        return []
    base = Path(appdata) / "JetBrains"
    if not _is_real_dir(base):
        return []
    found: list[Path] = []
    try:
        ides = list(base.iterdir())
    except OSError:
        return []
    for ide in ides:
        if not _is_real_dir(ide):
            continue
        for ext in extension_ids:
            tasks = ide / "globalStorage" / ext / "tasks"
            if _is_real_dir(tasks):
                found.append(tasks)
    return found


def _first_existing_dir(paths: list[Path], fallback: Path) -> Path:
    for path in paths:
        if _is_real_dir(path):
            return path
    return fallback


def _cline_peer_dirs() -> list[Path]:
    """Legacy editor tasks and the CLI/SDK `data/sessions` tree."""
    home = Path.home()
    found: list[Path] = []
    if os.environ.get("CLINE_SESSION_DATA_DIR"):
        found.append(Path(os.environ["CLINE_SESSION_DATA_DIR"]))
    if os.environ.get("CLINE_TASKS"):
        found.append(Path(os.environ["CLINE_TASKS"]))
    if os.environ.get("CLINE_DATA_DIR"):
        base = Path(os.environ["CLINE_DATA_DIR"])
        found.extend((base / "sessions", base / "tasks"))
    if os.environ.get("CLINE_DIR"):
        base = Path(os.environ["CLINE_DIR"]) / "data"
        found.extend((base / "sessions", base / "tasks"))
    exts = ("saoudrizwan.claude-dev", "cline.cline")
    found.extend(_editor_task_dirs(exts, ()))
    found.extend(_jetbrains_task_dirs(exts))
    found.extend((home / ".cline" / "data" / "sessions", home / ".cline" / "data" / "tasks"))
    return found


def _cline_home() -> Path:
    peers = _cline_peer_dirs()
    appdata = os.environ.get("APPDATA") or ""
    fallback = (
        Path(appdata) / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "tasks"
        if appdata else Path.home() / ".cline" / "data" / "sessions"
    )
    if os.environ.get("CLINE_SESSION_DATA_DIR"):
        return Path(os.environ["CLINE_SESSION_DATA_DIR"])
    if os.environ.get("CLINE_TASKS"):
        return Path(os.environ["CLINE_TASKS"])
    return _first_existing_dir(peers, fallback)


def _kilo_peer_dirs() -> list[Path]:
    home = Path.home()
    found: list[Path] = []
    if os.environ.get("KILO_TASKS"):
        found.append(Path(os.environ["KILO_TASKS"]))
    found.extend(_editor_task_dirs(("kilocode.kilo-code",), ()))
    found.extend((
        home / ".kilocode" / "cli" / "global" / "tasks",
        home / ".kilocode" / "globalStorage" / "kilocode.kilo-code" / "tasks",
        home / ".kilocode" / "globalStorage" / "tasks",
    ))
    return found


def _kilo_home() -> Path:
    if os.environ.get("KILO_TASKS"):
        return Path(os.environ["KILO_TASKS"])
    appdata = os.environ.get("APPDATA") or ""
    fallback = (
        Path(appdata) / "Code" / "User" / "globalStorage" / "kilocode.kilo-code" / "tasks"
        if appdata else Path.home() / ".kilocode" / "cli" / "global" / "tasks"
    )
    return _first_existing_dir(_kilo_peer_dirs(), fallback)


def _roo_peer_dirs() -> list[Path]:
    home = Path.home()
    found: list[Path] = []
    if os.environ.get("ROO_TASKS"):
        found.append(Path(os.environ["ROO_TASKS"]))
    exts = ("rooveterinaryinc.roo-cline",)
    found.extend(_editor_task_dirs(exts, ()))
    found.extend(_jetbrains_task_dirs(exts))
    found.append(home / ".roo" / "tasks")
    return found


def _roo_home() -> Path:
    if os.environ.get("ROO_TASKS"):
        return Path(os.environ["ROO_TASKS"])
    appdata = os.environ.get("APPDATA") or ""
    fallback = (
        Path(appdata) / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "tasks"
        if appdata else Path.home() / ".roo" / "tasks"
    )
    return _first_existing_dir(_roo_peer_dirs(), fallback)


def _hermes_db_candidates() -> list[Path]:
    home = Path.home()
    found: list[Path] = []
    if os.environ.get("HERMES_STATE"):
        found.append(Path(os.environ["HERMES_STATE"]))
    if os.environ.get("HERMES_HOME"):
        found.append(Path(os.environ["HERMES_HOME"]) / "state.db")
    found.append(home / ".hermes" / "state.db")
    local = os.environ.get("LOCALAPPDATA") or ""
    if local:
        found.append(Path(local) / "hermes" / "state.db")
    return found


def _hermes_home() -> Path:
    found = _existing_file(_hermes_db_candidates())
    if found is not None:
        return found
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"]) / "state.db"
    return Path.home() / ".hermes" / "state.db"


def _pi_home() -> Path:
    if os.environ.get("PI_CODING_AGENT_SESSION_DIR"):
        return Path(os.environ["PI_CODING_AGENT_SESSION_DIR"])
    return _env_or("PI_SESSIONS", Path.home() / ".pi" / "agent" / "sessions")


def _gemini_home() -> Path:
    if os.environ.get("GEMINI_SESSIONS"):
        return Path(os.environ["GEMINI_SESSIONS"])
    base = Path(os.environ["GEMINI_CLI_HOME"]) if os.environ.get("GEMINI_CLI_HOME") else Path.home()
    return base / ".gemini" / "tmp"


def _continue_home() -> Path:
    if os.environ.get("CONTINUE_SESSIONS"):
        return Path(os.environ["CONTINUE_SESSIONS"])
    if os.environ.get("CONTINUE_GLOBAL_DIR"):
        return Path(os.environ["CONTINUE_GLOBAL_DIR"]) / "sessions"
    return Path.home() / ".continue" / "sessions"


def _goose_db_candidates() -> list[Path]:
    home = Path.home()
    found: list[Path] = []
    root = os.environ.get("GOOSE_PATH_ROOT") or ""
    if root and Path(root).is_absolute():
        found.append(Path(root) / "data" / "sessions" / "sessions.db")
    appdata = os.environ.get("APPDATA") or ""
    if appdata:
        found.append(Path(appdata) / "Block" / "goose" / "data" / "sessions" / "sessions.db")
    found.append(home / ".local" / "share" / "goose" / "sessions" / "sessions.db")
    mac = home / "Library" / "Application Support" / "Block" / "goose"
    found.extend((mac / "data" / "sessions" / "sessions.db", mac / "sessions" / "sessions.db"))
    return found


def _goose_home() -> Path:
    if os.environ.get("GOOSE_SESSIONS"):
        return Path(os.environ["GOOSE_SESSIONS"])
    found = _existing_file(_goose_db_candidates())
    if found is not None:
        return found
    home = Path.home()
    appdata = os.environ.get("APPDATA") or ""
    legacy = []
    if appdata:
        legacy.append(Path(appdata) / "Block" / "goose" / "data" / "sessions")
    legacy.append(home / ".local" / "share" / "goose" / "sessions")
    for directory in legacy:
        if not _is_real_dir(directory):
            continue
        try:
            if any(p.is_file() and not p.is_symlink() for p in directory.glob("*.jsonl")):
                return directory
        except OSError:
            continue
    root = os.environ.get("GOOSE_PATH_ROOT") or ""
    if root and Path(root).is_absolute():
        return Path(root) / "data" / "sessions" / "sessions.db"
    if appdata:
        return Path(appdata) / "Block" / "goose" / "data" / "sessions" / "sessions.db"
    return home / ".local" / "share" / "goose" / "sessions" / "sessions.db"


def _amp_home() -> Path:
    if os.environ.get("AMP_THREADS_DIR"):
        return Path(os.environ["AMP_THREADS_DIR"])
    if os.environ.get("AMP_SESSIONS"):
        return Path(os.environ["AMP_SESSIONS"])
    return _xdg_data() / "amp" / "threads"


def _crush_home() -> Path:
    if os.environ.get("CRUSH_SESSIONS"):
        return Path(os.environ["CRUSH_SESSIONS"])
    return _xdg_data() / "crush" / "projects.json"


def default_homes() -> dict[str, Path | None]:
    """Documented store locations. No transcript in the docs means None, so n stays null."""
    home = Path.home()
    appdata = os.environ.get("APPDATA") or ""
    local = os.environ.get("LOCALAPPDATA") or ""
    grok = Path(os.environ["GROK_SESSIONS"]) if os.environ.get("GROK_SESSIONS") else home / ".grok" / "sessions"
    claude_root = Path(os.environ["CLAUDE_CONFIG_DIR"]) if os.environ.get("CLAUDE_CONFIG_DIR") else home / ".claude"
    codex = Path(os.environ["CODEX_HOME"]) if os.environ.get("CODEX_HOME") else home / ".codex"
    cursor = Path(os.environ["CURSOR_HOME"]) if os.environ.get("CURSOR_HOME") else home / ".cursor"
    desktop = None
    if os.environ.get("CLAUDE_DESKTOP_SESSIONS"):
        desktop = Path(os.environ["CLAUDE_DESKTOP_SESSIONS"])
    elif appdata:
        desktop = Path(appdata) / "Claude" / "local-agent-mode-sessions"
    cowork = None
    if os.environ.get("COWORK_CATALOG"):
        cowork = Path(os.environ["COWORK_CATALOG"])
    else:
        cowork = _existing_dir([home / "OpenWork Chat" / "cow_sessions"])
    openwork = None
    if os.environ.get("OPENCODE_DB"):
        openwork = Path(os.environ["OPENCODE_DB"])
    else:
        openwork = _existing_file([
            home / ".local" / "share" / "opencode" / "opencode.db",
            Path(local) / "opencode" / "opencode.db" if local else Path("."),
            Path(appdata) / "opencode" / "opencode.db" if appdata else Path("."),
        ])
    return {
        "grok": grok,
        "claude": claude_root / "projects",
        "codex": codex,
        "cursor": cursor,
        "claude_desktop": desktop,
        "gemini": _gemini_home(),
        "cowork": cowork,
        "openwork": openwork,
        "hermes": _hermes_home(),
        "cline": _cline_home(),
        "kilo": _kilo_home(),
        "roo": _roo_home(),
        "pi": _pi_home(),
        "copilot": _env_or("COPILOT_SESSION_STATE", home / ".copilot" / "session-state"),
        "continue": _continue_home(),
        "aider": Path(os.environ["AIDER_CHAT_HISTORY_FILE"]) if os.environ.get("AIDER_CHAT_HISTORY_FILE") else None,
        "goose": _goose_home(),
        "qwen": _env_or("QWEN_SESSIONS", home / ".qwen" / "projects"),
        "amp": _amp_home(),
        "openhands": _env_or("OPENHANDS_SESSIONS", home / ".openhands" / "conversations"),
        "crush": _crush_home(),
        "amazonq": Path(os.environ["AMAZONQ_HISTORY"]) if os.environ.get("AMAZONQ_HISTORY") else None,
        "dsh": Path(os.environ["DSH_HOME"]) if os.environ.get("DSH_HOME") else home / ".dsh",
        "factory": None,
        "windsurf": None,
        "augment": None,
    }


def home_status(homes: dict | None = None) -> list[dict]:
    """Presence only. n stays null until find walks the store."""
    homes = homes if homes is not None else default_homes()
    rows = []
    for name in HARNESSES:
        path = homes.get(name)
        present = False
        if path is not None:
            try:
                present = path.exists() and not path.is_symlink()
            except OSError:
                present = False
        rows.append({
            "harness": name,
            "present": present,
            "path": str(path) if path and present else None,
            "n": None,
            "status": "PRESENT" if present else "ABSENT",
        })
    return rows


_DRIVE_KIND = {
    0: "unknown", 1: "noroot", 2: "removable", 3: "fixed",
    4: "remote", 5: "cdrom", 6: "ramdisk",
}


def _drive_letter(path: str | None) -> str | None:
    text = str(path or "").replace("/", "\\")
    if len(text) >= 2 and text[1] == ":":
        return text[:2].upper()
    return None


_win_lock = threading.Lock()
_win_dll = None


def _win_kernel():
    """One kernel32 with prototypes set once. Do not mutate the shared windll."""
    global _win_dll
    with _win_lock:
        if _win_dll is not None:
            return _win_dll
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetLogicalDriveStringsW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
        kernel.GetLogicalDriveStringsW.restype = ctypes.c_uint32
        kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
        kernel.GetDriveTypeW.restype = ctypes.c_uint32
        kernel.GetVolumeInformationW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_wchar_p, ctypes.c_uint32,
        ]
        kernel.GetVolumeInformationW.restype = ctypes.c_int
        kernel.GetDiskFreeSpaceExW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_ulonglong),
            ctypes.POINTER(ctypes.c_ulonglong),
            ctypes.POINTER(ctypes.c_ulonglong),
        ]
        kernel.GetDiskFreeSpaceExW.restype = ctypes.c_int
        kernel.SetErrorMode.argtypes = [ctypes.c_uint32]
        kernel.SetErrorMode.restype = ctypes.c_uint32
        _win_dll = kernel
        return kernel


def list_drives() -> list[dict]:
    """Volume letters and labels only. Does not walk the files on the drive."""
    if os.name != "nt":
        root = Path("/")
        return [{"id": "/", "path": "/", "label": "", "kind": "fixed", "fs": "",
                 "total": None, "free": None, "ready": root.exists()}]
    import ctypes
    kernel = _win_kernel()
    # SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX. An empty tray must not
    # raise a system dialog, and a dead network root is not queried below.
    old_mode = kernel.SetErrorMode(0x0001 | 0x8000)
    try:
        size = 256
        buf = ctypes.create_unicode_buffer(size)
        n = int(kernel.GetLogicalDriveStringsW(size, buf))
        while n >= size:
            size = n + 2
            if size > 65536:
                return []
            buf = ctypes.create_unicode_buffer(size)
            n = int(kernel.GetLogicalDriveStringsW(size, buf))
        if n <= 0:
            return []
        text = "".join(buf[i] for i in range(n))
        roots = [part for part in text.split("\x00") if part]
        rows = []
        for root in roots:
            kind_n = int(kernel.GetDriveTypeW(root))
            kind = _DRIVE_KIND.get(kind_n, "unknown")
            letter = root[:2].upper()
            if kind not in ("fixed", "ramdisk", "removable"):
                rows.append({
                    "id": letter, "path": root, "label": "", "kind": kind, "fs": "",
                    "total": None, "free": None, "ready": False,
                })
                continue
            label = ctypes.create_unicode_buffer(261)
            fs = ctypes.create_unicode_buffer(32)
            serial = ctypes.c_uint32()
            maxcl = ctypes.c_uint32()
            flags = ctypes.c_uint32()
            named = bool(kernel.GetVolumeInformationW(
                root, label, 261, ctypes.byref(serial), ctypes.byref(maxcl),
                ctypes.byref(flags), fs, 32,
            ))
            free = ctypes.c_ulonglong()
            total = ctypes.c_ulonglong()
            avail = ctypes.c_ulonglong()
            sized = bool(kernel.GetDiskFreeSpaceExW(
                root, ctypes.byref(avail), ctypes.byref(total), ctypes.byref(free),
            ))
            rows.append({
                "id": letter,
                "path": root,
                "label": label.value if named else "",
                "kind": kind,
                "fs": fs.value if named else "",
                "total": int(total.value) if sized else None,
                "free": int(free.value) if sized else None,
                "ready": named or sized,
            })
        return rows
    finally:
        kernel.SetErrorMode(old_mode)


def places(homes: dict | None = None) -> dict:
    """Drives first, then each default location. Counts stay null until find."""
    homes = homes if homes is not None else default_homes()
    drives = list_drives()
    rows = []
    for row in home_status(homes):
        raw = homes.get(row["harness"])
        candidate = str(raw) if raw else None
        item = dict(row)
        item["candidate"] = candidate
        item["drive"] = _drive_letter(row.get("path") or candidate)
        rows.append(item)
    return {"drives": drives, "homes": rows}


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _hit(*, harness: str, vendor_id: str, path: Path, cwd: str = "",
         title: str = "", stream: str = "", updated: float | None = None,
         nbytes: int | None = None, aliases: dict | None = None) -> dict:
    legal = is_legal(str(path), stream, cwd, title)
    vid = str(vendor_id)
    return {
        "id": legal_id(PREFIX[harness], vid),
        "harness": harness,
        "vendor_id": vid,
        "path": str(path),
        "cwd": "" if legal else (cwd or ""),
        "title": "" if legal else (title or ""),
        "stream": (stream or "unknown").lower(),
        "legal": legal,
        "updated": updated if updated is not None else _mtime(path),
        "bytes": nbytes,
        "aliases": aliases or {},
    }


def _head_lines(path: Path) -> list[dict]:
    try:
        size = path.stat().st_size
    except OSError:
        return []
    try:
        with path.open("rb") as handle:
            raw = handle.read(min(size, HEAD_BYTES))
    except OSError:
        return []
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line.decode("utf-8", errors="replace"))
        except ValueError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _text_of(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if content.get("text"):
            return str(content.get("text"))
        return _text_of(content.get("content"))
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                kind = str(block.get("type") or "")
                if kind in ("text", "input_text", "output_text") or "text" in block:
                    parts.append(str(block.get("text") or ""))
        return "\n".join(p for p in parts if p)
    return ""


def _one_line(text: str, limit: int = 80) -> str:
    flat = " ".join(str(text or "").split())
    return flat[:limit]


def _summary_title(*sources: dict) -> str:
    """Short name from a session summary. Root fields win over a nested info object."""
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("generated_title", "session_summary", "title"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return _one_line(value, 80)
    return ""


def _user_line(obj: dict) -> str:
    """Text of a user turn. System and tool lines return empty."""
    kind = str(obj.get("type") or obj.get("role") or "").lower()
    if kind == "response_item":
        payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
        kind = str(payload.get("role") or "").lower()
        text = _text_of(payload.get("content"))
    elif kind == "user.message":
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        kind = "user"
        text = _text_of(data.get("content"))
    else:
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
        nested = str(msg.get("role") or "").lower() if isinstance(msg, dict) else ""
        if kind not in ("user", "human") and nested:
            kind = nested
        content = None
        if isinstance(msg, dict):
            content = msg.get("content")
            if content is None:
                content = msg.get("text")
        text = _text_of(content)
    if kind not in ("user", "human"):
        return ""
    return text


def _first_user_title(path: Path, limit: int = 262144) -> str:
    """First user line, one screen of text at most. Does not hash the file."""
    read = 0
    try:
        handle = path.open("rb")
    except OSError:
        return ""
    with handle:
        for line in handle:
            read += len(line)
            piece = line.strip()
            if piece:
                try:
                    obj = json.loads(piece.decode("utf-8", errors="replace"))
                except ValueError:
                    obj = None
                if isinstance(obj, dict):
                    title = _user_line(obj)
                    if title.strip():
                        return _one_line(title, 80)
            if read >= limit:
                break
    return ""


def _unescape_json_piece(text: str) -> str:
    return (
        text.replace("\\\\", "\\")
        .replace("\\/", "/")
        .replace('\\"', '"')
        .replace("\\n", " ")
        .replace("\\t", " ")
    )


def _sniff(path: Path, n: int = 1024) -> tuple[str, str]:
    """Header only. Does not parse a whole transcript line."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(n)
    except OSError:
        return "", ""
    text = raw.decode("utf-8", errors="replace")
    cwd = ""
    title = ""
    cwd_m = re.search(r'"cwd"\s*:\s*"((?:\\.|[^"\\]){0,240})"', text)
    if cwd_m:
        cwd = _unescape_json_piece(cwd_m.group(1))
    title_m = re.search(
        r'"(?:customTitle|generated_title|title|summary)"\s*:\s*"((?:\\.|[^"\\]){0,120})"',
        text,
    )
    if title_m:
        title = _one_line(_unescape_json_piece(title_m.group(1)))
    return cwd, title


def _claude_meta(path: Path) -> tuple[str, str]:
    cwd, title = _sniff(path, 2048)
    if cwd and title:
        return cwd, title
    for obj in _head_lines(path):
        if not cwd and isinstance(obj.get("cwd"), str):
            cwd = obj["cwd"]
        kind = str(obj.get("type") or "")
        if kind in ("custom-title", "ai-title") and not title:
            title = _one_line(obj.get("customTitle") or obj.get("title") or obj.get("summary") or "")
        if kind == "user" and not title:
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
            title = _one_line(_text_of(msg.get("content") if isinstance(msg, dict) else ""))
        if cwd and title:
            break
    return cwd, title


def _enum_grok(root: Path) -> list[dict]:
    if not root.is_dir():
        return []
    hits = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            scan = os.scandir(current)
        except OSError:
            continue
        with scan:
            for entry in scan:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in ("node_modules", ".git"):
                            stack.append(Path(entry.path))
                        continue
                    if entry.name != "summary.json":
                        continue
                except OSError:
                    continue
                folder = Path(entry.path).parent
                hist = folder / "chat_history.jsonl"
                try:
                    st = hist.stat()
                except OSError:
                    continue
                if not hist.is_file():
                    continue
                try:
                    info = json.loads(Path(entry.path).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    info = {}
                if not isinstance(info, dict):
                    info = {}
                inner = info.get("info") if isinstance(info.get("info"), dict) else info
                vid = str(inner.get("id") or folder.name)
                cwd = str(inner.get("cwd") or "")
                title = _summary_title(info, inner)
                hits.append(_hit(
                    harness="grok", vendor_id=vid, path=hist, cwd=cwd, title=title,
                    updated=st.st_mtime, nbytes=st.st_size,
                ))
    return hits


def _claude_project_cwd(name: str) -> str:
    """Best-effort reverse of Claude's project-folder encoding, for the legal gate only."""
    text = name
    if len(text) >= 3 and text[0].isalpha() and text[1:3] == "--":
        text = text[0] + ":\\" + text[3:]
    return text.replace("-", "\\")


def _consume_claude_dir(project: Path, hits: list[dict]) -> None:
    """List session files. Do not open each transcript. Legal is the folder name."""
    decoded = _claude_project_cwd(project.name)
    folder_legal = is_legal(str(project), "", decoded, "")
    try:
        scan = os.scandir(project)
    except OSError:
        return
    with scan:
        for entry in scan:
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                continue
            stem = entry.name[:-6] if entry.name.endswith(".jsonl") else ""
            if not stem or not _UUID.fullmatch(stem):
                continue
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            hits.append(_hit(
                harness="claude", vendor_id=stem, path=Path(entry.path),
                cwd=decoded if folder_legal else "", title="",
                updated=st.st_mtime, nbytes=st.st_size,
            ))


def _enum_claude(root: Path) -> list[dict]:
    if not root.is_dir():
        return []
    hits: list[dict] = []
    _consume_claude_dir(root, hits)
    try:
        projects = [p for p in root.iterdir() if p.is_dir() and not p.is_symlink()]
    except OSError:
        return hits
    for project in projects:
        _consume_claude_dir(project, hits)
    return hits


def _enum_codex(root: Path) -> list[dict]:
    if root.is_file() and root.suffix == ".sqlite":
        return _enum_codex_db(root)
    if not root.is_dir():
        return []
    db = None
    try:
        for child in root.iterdir():
            if re.fullmatch(r"state_(\d+)\.sqlite", child.name) and child.is_file():
                db = child
    except OSError:
        db = None
    if db is not None:
        rows = _enum_codex_db(db)
        if rows:
            return rows
    hits = []
    try:
        paths = root.rglob("rollout-*.jsonl")
    except OSError:
        return []
    for path in paths:
        if "archived" in {p.lower() for p in path.parts}:
            continue
        match = _ROLLOUT.match(path.name)
        if not match:
            continue
        cwd, title = _sniff(path)
        hits.append(_hit(
            harness="codex", vendor_id=match.group(1), path=path, cwd=cwd, title=title,
            updated=_mtime(path), nbytes=path.stat().st_size,
        ))
    return hits


def _enum_codex_db(db: Path) -> list[dict]:
    hits = []
    try:
        uri = db.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=1.0)
        cols = {r[1] for r in con.execute("PRAGMA table_info(threads)")}
        if not {"id", "cwd"}.issubset(cols):
            con.close()
            return []
        title_col = "title" if "title" in cols else "''"
        path_col = "rollout_path" if "rollout_path" in cols else "''"
        rows = con.execute(
            f"SELECT id, cwd, {title_col}, {path_col} FROM threads"
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return []
    for sid, cwd, title, rollout in rows:
        path = Path(rollout) if rollout else db
        hits.append(_hit(
            harness="codex", vendor_id=str(sid), path=path,
            cwd=str(cwd or ""), title=str(title or ""), updated=_mtime(path if path.is_file() else db),
        ))
    return hits


def _enum_cursor(root: Path) -> list[dict]:
    if not root.is_dir():
        return []
    hits = []
    chats = root / "chats"
    if chats.is_dir():
        try:
            workspaces = list(chats.iterdir())
        except OSError:
            workspaces = []
        for workspace in workspaces:
            if not workspace.is_dir():
                continue
            try:
                children = list(workspace.iterdir())
            except OSError:
                continue
            for child in children:
                if not child.is_dir() or not _UUID.fullmatch(child.name):
                    continue
                meta_path = child / "meta.json"
                store = child / "store.db"
                path = meta_path if meta_path.is_file() else store
                if not path.is_file():
                    continue
                cwd, title = "", ""
                if meta_path.is_file():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        meta = {}
                    cwd = str(meta.get("cwd") or meta.get("workspacePath") or "")
                    title = str(meta.get("title") or meta.get("name") or "")
                hits.append(_hit(
                    harness="cursor", vendor_id=child.name, path=path, cwd=cwd, title=title,
                    updated=_mtime(path),
                ))
    projects = root / "projects"
    if projects.is_dir():
        try:
            transcripts = projects.glob("*/agent-transcripts/*/*.jsonl")
        except OSError:
            transcripts = []
        seen = {h["vendor_id"] for h in hits}
        for path in transcripts:
            if not _UUID.fullmatch(path.stem) or path.stem in seen:
                continue
            cwd, title = _claude_meta(path)
            hits.append(_hit(
                harness="cursor", vendor_id=path.stem, path=path, cwd=cwd, title=title,
                updated=_mtime(path), nbytes=path.stat().st_size,
            ))
    real = Path(os.environ["CURSOR_HOME"]) if os.environ.get("CURSOR_HOME") else Path.home() / ".cursor"
    try:
        same = root.resolve() == real.resolve()
    except OSError:
        same = False
    if same:
        seen = {hit["vendor_id"] for hit in hits}
        for row in _enum_cursor_desktop():
            if row["vendor_id"] not in seen:
                hits.append(row)
                seen.add(row["vendor_id"])
    return hits


def _enum_cursor_desktop() -> list[dict]:
    """Read-only composer headers. No transcript body."""
    appdata = os.environ.get("APPDATA") or ""
    if not appdata:
        return []
    path = Path(appdata) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    if not path.is_file() or path.is_symlink():
        return []
    hits = []
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=1.0)
        cols = {row[1] for row in con.execute("PRAGMA table_info(composerHeaders)")}
        if not {"composerId", "lastUpdatedAt", "isArchived", "isSubagent", "value"}.issubset(cols):
            con.close()
            return []
        rows = con.execute(
            "SELECT composerId, lastUpdatedAt, value FROM composerHeaders "
            "WHERE COALESCE(isArchived, 0) = 0 AND COALESCE(isSubagent, 0) = 0"
        )
        for sid, updated, raw in rows:
            if not isinstance(sid, str) or not sid:
                continue
            title, cwd = "", ""
            obj = None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            if isinstance(raw, str) and raw:
                try:
                    obj = json.loads(raw)
                except ValueError:
                    obj = None
            if isinstance(obj, dict):
                title = str(obj.get("title") or obj.get("name") or "")
                cwd = str(obj.get("cwd") or obj.get("workspacePath") or "")
            stamp = _mtime(path)
            try:
                number = float(updated)
                stamp = number / 1000.0 if number > 10_000_000_000 else number
            except (TypeError, ValueError):
                pass
            hits.append(_hit(
                harness="cursor", vendor_id=sid, path=path, cwd=cwd, title=title, updated=stamp,
            ))
        con.close()
    except sqlite3.Error:
        return []
    return hits


def _catalog_file(store: Path) -> Path | None:
    if store.is_file() and store.name.endswith(".json"):
        return store
    candidate = store / "COW_SESSION_CATALOG.json"
    return candidate if candidate.is_file() else None


def _enum_cowork(store: Path) -> list[dict]:
    cat = _catalog_file(store)
    if cat is None:
        return []
    try:
        rows = json.loads(cat.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PageError("UNPARSEABLE", str(cat))
    if not isinstance(rows, list):
        raise PageError("UNPARSEABLE", str(cat))
    hits = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("session_id") or row.get("seq") or "")
        filename = str(row.get("filename") or "")
        md = None
        if filename:
            for base in (cat.parent / "ordered_transcripts", store if store.is_dir() else cat.parent):
                candidate = base / filename
                if candidate.is_file():
                    md = candidate
                    break
        seq = row.get("seq")
        aliases = {
            "seq": seq,
            "filename": filename or None,
            "opencode_id": f"ses_cow_{int(seq):03d}" if isinstance(seq, int) or str(seq).isdigit() else None,
        }
        hits.append(_hit(
            harness="cowork", vendor_id=sid,
            path=md or cat,
            cwd="",
            title=str(row.get("title") or ""),
            stream=str(row.get("stream") or ""),
            updated=_mtime(md or cat),
            nbytes=(md.stat().st_size if md else None),
            aliases=aliases,
        ))
    return hits


def _enum_openwork(store: Path) -> list[dict]:
    db = store if store.is_file() else store / "opencode.db"
    if not db.is_file():
        return []
    try:
        uri = db.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=1.0)
        rows = list(con.execute("SELECT id, title, directory FROM session"))
        con.close()
    except sqlite3.Error as exc:
        raise PageError("SCHEMA_UNKNOWN", str(exc))
    hits = []
    for sid, title, directory in rows:
        if str(sid).startswith("ses_cow_"):
            continue
        hits.append(_hit(
            harness="openwork", vendor_id=str(sid), path=db,
            cwd=str(directory or ""), title=str(title or ""),
        ))
    return hits


def _enum_loose_jsonl(harness: str, root: Path | None) -> list[dict]:
    if root is None or not root.is_dir():
        return []
    hits = []
    try:
        files = list(root.rglob("*.jsonl"))
    except OSError:
        return []
    for path in files:
        if path.is_symlink():
            continue
        vid = path.stem
        cwd, title = _sniff(path)
        hits.append(_hit(
            harness=harness, vendor_id=vid, path=path, cwd=cwd, title=title,
            updated=_mtime(path), nbytes=path.stat().st_size,
        ))
    return hits


def _sql_rows(db: Path, statements: tuple[str, ...]) -> list[tuple]:
    if not db.is_file() or db.is_symlink():
        return []
    uri = db.resolve().as_uri() + "?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True, timeout=1.0)
    except sqlite3.Error as exc:
        raise PageError("SCHEMA_UNKNOWN", str(exc)) from exc
    last = "SCHEMA_UNKNOWN"
    try:
        for sql in statements:
            try:
                rows = list(con.execute(sql))
                con.close()
                return rows
            except sqlite3.OperationalError as exc:
                last = str(exc)
                continue
    finally:
        try:
            con.close()
        except sqlite3.Error:
            pass
    raise PageError("SCHEMA_UNKNOWN", last)


def _epoch(value, fallback: float) -> float:
    if isinstance(value, (int, float)) and value > 0:
        number = float(value)
        return number / 1000.0 if number > 10**11 else number
    return fallback


def _json_title(path: Path) -> str:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 32768:
            return ""
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(obj, dict):
        return ""
    for key in ("title", "task", "name"):
        text = obj.get(key)
        if isinstance(text, str) and text.strip():
            return _one_line(text, 120)
    return ""


def _enum_sqlite_meta(harness: str, db: Path, statements: tuple[str, ...]) -> list[dict]:
    rows = _sql_rows(db, statements)
    fallback = _mtime(db)
    hits = []
    for sid, title, cwd, updated in rows:
        hits.append(_hit(
            harness=harness, vendor_id=str(sid), path=db,
            cwd=str(cwd or ""), title=str(title or ""),
            updated=_epoch(updated, fallback),
        ))
    return hits


def _enum_hermes(db: Path) -> list[dict]:
    return _enum_sqlite_meta("hermes", db, (
        "SELECT id, COALESCE(title, display_name, ''), COALESCE(cwd, ''), "
        "last_activity_at FROM sessions WHERE COALESCE(hidden, 0) = 0",
        "SELECT id, COALESCE(title, display_name, ''), COALESCE(cwd, ''), "
        "last_activity_at FROM sessions",
    ))


def _hermes_state_files(path: Path) -> list[Path]:
    if _is_real_file(path):
        bases = [path.parent]
        files = [path]
    elif _is_real_dir(path):
        bases = [path]
        files = [path / "state.db"] if _is_real_file(path / "state.db") else []
    else:
        return []
    for base in bases:
        profiles = base / "profiles"
        if not _is_real_dir(profiles):
            continue
        try:
            files.extend(db for db in profiles.glob("*/state.db") if _is_real_file(db))
        except OSError:
            continue
    return files


def _enum_hermes_home(path: Path) -> list[dict]:
    peers = _hermes_db_candidates()
    seeds = peers if _same_path(path, peers) or _same_path(path / "state.db", peers) else [path]
    seen_db: set[str] = set()
    seen_id: set[str] = set()
    hits = []
    for seed in seeds:
        for db in _hermes_state_files(seed):
            try:
                key = str(db.resolve())
            except OSError:
                key = str(db)
            if key in seen_db:
                continue
            seen_db.add(key)
            try:
                rows = _enum_hermes(db)
            except PageError:
                continue
            for hit in rows:
                if hit["id"] in seen_id:
                    continue
                seen_id.add(hit["id"])
                hits.append(hit)
    return hits


def _copilot_identity(path: Path) -> tuple[str, str]:
    """session.start carries the id. The directory name is not always that id."""
    sid = path.parent.name
    cwd = ""
    try:
        with path.open("rb") as handle:
            raw = handle.read(HEAD_BYTES)
    except OSError:
        return sid, cwd
    for line in raw.splitlines():
        piece = line.strip()
        if not piece:
            continue
        try:
            obj = json.loads(piece.decode("utf-8", errors="replace"))
        except ValueError:
            continue
        if not isinstance(obj, dict) or obj.get("type") != "session.start":
            continue
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        found = data.get("sessionId") or data.get("session_id")
        if isinstance(found, str) and found.strip():
            sid = found.strip()
        ctx = data.get("context") if isinstance(data.get("context"), dict) else {}
        if isinstance(ctx.get("cwd"), str):
            cwd = ctx["cwd"]
        break
    return sid, cwd


def _enum_copilot(root: Path) -> list[dict]:
    if _is_real_file(root) and root.name == "events.jsonl":
        files = [root]
    elif _is_real_dir(root):
        try:
            files = [p for p in root.glob("*/events.jsonl") if _is_real_file(p)]
        except OSError:
            return []
    else:
        return []
    hits = []
    seen: set[str] = set()
    for path in files:
        sid, cwd = _copilot_identity(path)
        hit = _hit(
            harness="copilot", vendor_id=sid, path=path, cwd=cwd,
            updated=_mtime(path), nbytes=path.stat().st_size,
        )
        if hit["id"] in seen:
            continue
        seen.add(hit["id"])
        hits.append(hit)
    return hits


def _enum_task_dirs(harness: str, root: Path) -> list[dict]:
    if not root.is_dir() or root.is_symlink():
        return []
    try:
        children = list(root.iterdir())
    except OSError:
        return []
    folders = [root] if (root / "api_conversation_history.json").is_file() else children
    hits = []
    for folder in folders:
        try:
            if not folder.is_dir() or folder.is_symlink():
                continue
            hist = folder / "api_conversation_history.json"
            if not hist.is_file() or hist.is_symlink():
                continue
            hits.append(_hit(
                harness=harness, vendor_id=folder.name, path=hist,
                title=_json_title(folder / "task_metadata.json"),
                updated=_mtime(hist), nbytes=hist.stat().st_size,
            ))
        except OSError:
            continue
    return hits


def _peer_dirs(root: Path, peers: list[Path]) -> list[Path]:
    if _same_path(root, peers):
        return [p for p in peers if _is_real_dir(p)]
    return [root]


def _enum_task_peers(harness: str, root: Path, peers: list[Path]) -> list[dict]:
    hits = []
    seen: set[str] = set()
    for item in _peer_dirs(root, peers):
        for hit in _enum_task_dirs(harness, item):
            if hit["id"] in seen:
                continue
            seen.add(hit["id"])
            hits.append(hit)
    return hits


def _enum_messages(harness: str, root: Path) -> list[dict]:
    """Cline CLI/SDK: `<sessionId>/<sessionId>.messages.json`."""
    if not _is_real_dir(root):
        return []
    files: list[Path] = []
    named = root / f"{root.name}.messages.json"
    if _is_real_file(named):
        files.append(named)
    try:
        files.extend(p for p in root.glob("*/*.messages.json") if _is_real_file(p))
    except OSError:
        return []
    hits = []
    seen: set[str] = set()
    for path in files:
        vid = path.parent.name if path.parent != root else path.name[: -len(".messages.json")]
        manifest = path.parent / f"{vid}.json"
        hit = _hit(
            harness=harness, vendor_id=vid, path=path,
            title=_json_title(manifest),
            updated=_mtime(path), nbytes=path.stat().st_size,
        )
        if hit["id"] in seen:
            continue
        seen.add(hit["id"])
        hits.append(hit)
    return hits


def _enum_cline(root: Path) -> list[dict]:
    peers = _cline_peer_dirs()
    hits = []
    seen: set[str] = set()
    for item in _peer_dirs(root, peers):
        for hit in _enum_task_dirs("cline", item) + _enum_messages("cline", item):
            if hit["id"] in seen:
                continue
            seen.add(hit["id"])
            hits.append(hit)
    return hits


def _enum_kilo(root: Path) -> list[dict]:
    return _enum_task_peers("kilo", root, _kilo_peer_dirs())


def _enum_roo(root: Path) -> list[dict]:
    return _enum_task_peers("roo", root, _roo_peer_dirs())


def _json_obj(path: Path, limit: int = 262144) -> dict:
    try:
        if not _is_real_file(path) or path.stat().st_size > limit:
            return {}
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _project_root_file(path: Path) -> str:
    marker = path.parent.parent / ".project_root"
    try:
        if marker.is_file() and not marker.is_symlink() and marker.stat().st_size < 1024:
            return marker.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return ""


def _enum_chat_tmp(harness: str, root: Path) -> list[dict]:
    """Gemini `tmp/<project>/chats/*.{json,jsonl}` and Qwen `projects/<cwd>/chats/*.jsonl`."""
    if not _is_real_dir(root):
        return []
    patterns = ("*.jsonl", "*.json") if root.name == "chats" else ("*/chats/**/*.jsonl", "*/chats/**/*.json")
    files: list[Path] = []
    try:
        for pattern in patterns:
            files.extend(root.glob(pattern))
    except OSError:
        return []
    hits = []
    seen: set[str] = set()
    for path in files:
        if not _is_real_file(path) or path.name == "sessions.json":
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        hits.append(_hit(
            harness=harness, vendor_id=path.stem, path=path,
            cwd=_project_root_file(path),
            updated=_mtime(path), nbytes=path.stat().st_size,
        ))
    return hits


def _enum_continue(root: Path) -> list[dict]:
    if not _is_real_dir(root):
        return []
    try:
        files = [p for p in root.glob("*.json") if _is_real_file(p) and p.name != "sessions.json"]
    except OSError:
        return []
    hits = []
    for path in files:
        obj = _json_obj(path)
        sid = obj.get("sessionId") or obj.get("id")
        vid = sid.strip() if isinstance(sid, str) and sid.strip() else path.stem
        title = obj.get("title") if isinstance(obj.get("title"), str) else ""
        cwd = obj.get("workspaceDirectory") if isinstance(obj.get("workspaceDirectory"), str) else ""
        hits.append(_hit(
            harness="continue", vendor_id=vid, path=path, cwd=cwd, title=_one_line(title, 120),
            updated=_mtime(path), nbytes=path.stat().st_size,
        ))
    return hits


def _enum_aider(path: Path) -> list[dict]:
    """One history file from AIDER_CHAT_HISTORY_FILE. There is no global session directory."""
    if not _is_real_file(path):
        return []
    return [_hit(
        harness="aider", vendor_id=path.name, path=path,
        updated=_mtime(path), nbytes=path.stat().st_size,
    )]


def _enum_goose(path: Path) -> list[dict]:
    db = path if _is_real_file(path) and path.suffix.lower() == ".db" else None
    if _is_real_dir(path):
        nested = path / "sessions.db"
        if _is_real_file(nested):
            db = nested
        else:
            try:
                files = [p for p in path.glob("*.jsonl") if _is_real_file(p)]
            except OSError:
                return []
            hits = []
            for item in files:
                cwd, title = _sniff(item)
                hits.append(_hit(
                    harness="goose", vendor_id=item.stem, path=item, cwd=cwd, title=title,
                    updated=_mtime(item), nbytes=item.stat().st_size,
                ))
            return hits
    if db is None:
        return []
    return _enum_sqlite_meta("goose", db, (
        "SELECT id, COALESCE(name, ''), COALESCE(working_dir, ''), updated_at FROM sessions "
        "WHERE lower(COALESCE(session_type, 'user')) NOT IN ('hidden', 'subagent')",
        "SELECT id, COALESCE(description, ''), COALESCE(working_dir, ''), updated_at FROM sessions "
        "WHERE lower(COALESCE(session_type, 'user')) NOT IN ('hidden', 'subagent')",
        "SELECT id, COALESCE(name, ''), COALESCE(working_dir, ''), updated_at FROM sessions",
        "SELECT id, COALESCE(description, ''), COALESCE(working_dir, ''), updated_at FROM sessions",
        "SELECT id, '', COALESCE(working_dir, ''), updated_at FROM sessions",
    ))


def _enum_amp(root: Path) -> list[dict]:
    if _is_real_file(root) and root.suffix.lower() == ".json":
        files = [root]
    elif _is_real_dir(root):
        try:
            files = [p for p in root.glob("*.json") if _is_real_file(p)]
        except OSError:
            return []
    else:
        return []
    hits = []
    for path in files:
        obj = _json_obj(path)
        sid = obj.get("id")
        vid = sid.strip() if isinstance(sid, str) and sid.strip() else path.stem
        title = obj.get("title") if isinstance(obj.get("title"), str) else ""
        hits.append(_hit(
            harness="amp", vendor_id=vid, path=path, title=_one_line(title, 120),
            updated=_mtime(path), nbytes=path.stat().st_size,
        ))
    return hits


def _enum_openhands(root: Path) -> list[dict]:
    states: list[Path] = []
    if _is_real_file(root) and root.name == "base_state.json":
        states = [root]
    elif _is_real_dir(root):
        direct = root / "base_state.json"
        if _is_real_file(direct):
            states = [direct]
        else:
            try:
                states = [p for p in root.glob("*/base_state.json") if _is_real_file(p)]
                states += [p for p in root.glob("conversations/*/base_state.json") if _is_real_file(p)]
            except OSError:
                return []
    hits = []
    seen: set[str] = set()
    for path in states:
        obj = _json_obj(path)
        sid = obj.get("id") or obj.get("conversation_id")
        vid = sid.strip() if isinstance(sid, str) and sid.strip() else path.parent.name
        title = obj.get("title") if isinstance(obj.get("title"), str) else ""
        cwd = obj.get("workspace") if isinstance(obj.get("workspace"), str) else ""
        if not cwd and isinstance(obj.get("cwd"), str):
            cwd = obj["cwd"]
        hit = _hit(
            harness="openhands", vendor_id=vid, path=path, cwd=cwd, title=_one_line(title, 120),
            updated=_mtime(path), nbytes=path.stat().st_size,
        )
        if hit["id"] in seen:
            continue
        seen.add(hit["id"])
        hits.append(hit)
    return hits


def _crush_db(project: dict) -> tuple[Path | None, str]:
    raw_cwd = project.get("path")
    cwd = raw_cwd if isinstance(raw_cwd, str) else ""
    raw = project.get("data_dir")
    if isinstance(raw, str) and raw.strip():
        db = Path(raw)
        if _is_real_dir(db):
            db = db / "crush.db"
    elif cwd:
        db = Path(cwd) / ".crush" / "crush.db"
    else:
        return None, cwd
    if not _is_real_file(db):
        return None, cwd
    return db, cwd


def _enum_crush(path: Path) -> list[dict]:
    projects: list[dict] = []
    if _is_real_file(path) and path.name == "projects.json":
        obj = _json_obj(path, limit=1_048_576)
        raw = obj.get("projects")
        if isinstance(raw, list):
            projects = [item for item in raw if isinstance(item, dict)]
    elif _is_real_file(path) and path.suffix.lower() == ".db":
        projects = [{"data_dir": str(path), "path": ""}]
    else:
        return []
    hits = []
    seen: set[str] = set()
    for project in projects:
        db, cwd = _crush_db(project)
        if db is None:
            continue
        try:
            rows = _sql_rows(db, (
                "SELECT id, COALESCE(title, ''), updated_at FROM sessions "
                "WHERE parent_session_id IS NULL",
                "SELECT id, COALESCE(title, ''), updated_at FROM sessions",
            ))
        except PageError:
            continue
        fallback = _mtime(db)
        for sid, title, updated in rows:
            hit = _hit(
                harness="crush", vendor_id=str(sid), path=db, cwd=cwd,
                title=str(title or ""), updated=_epoch(updated, fallback),
            )
            if hit["id"] in seen:
                continue
            seen.add(hit["id"])
            hits.append(hit)
    return hits


def _enum_amazonq(path: Path) -> list[dict]:
    """Only an explicit AMAZONQ_HISTORY file or directory. `~/.aws/amazonq` is not a transcript store."""
    files: list[Path] = []
    if _is_real_file(path):
        files = [path]
    elif _is_real_dir(path):
        try:
            for pattern in ("q-dev-chat-*.md", "q-dev-chat-*.html", "q-dev-chat-*.json"):
                files.extend(p for p in path.glob(pattern) if _is_real_file(p))
        except OSError:
            return []
    hits = []
    seen: set[str] = set()
    for item in files:
        hit = _hit(
            harness="amazonq", vendor_id=item.stem, path=item,
            updated=_mtime(item), nbytes=item.stat().st_size,
        )
        if hit["id"] in seen:
            continue
        seen.add(hit["id"])
        hits.append(hit)
    return hits


def _enum_dsh(root: Path) -> list[dict]:
    """Count `session.v3.jsonl.zstd`. Do not decompress or descend into dependency trees."""
    if not _is_real_dir(root):
        return []
    files: list[Path] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in ("node_modules", ".git")]
            if "session.v3.jsonl.zstd" in filenames:
                path = Path(dirpath) / "session.v3.jsonl.zstd"
                if _is_real_file(path):
                    files.append(path)
    except OSError:
        return []
    hits = []
    seen: set[str] = set()
    for path in files:
        hit = _hit(
            harness="dsh", vendor_id=path.parent.name, path=path,
            updated=_mtime(path), nbytes=path.stat().st_size,
        )
        if hit["id"] in seen:
            continue
        seen.add(hit["id"])
        hits.append(hit)
    return hits


def _store_present(path: Path | None) -> bool:
    if path is None:
        return False
    return _is_real_dir(path) or _is_real_file(path)


def _walk_report(homes: dict) -> tuple[list[dict], dict[str, str]]:
    """One bad store is recorded and skipped. The other harnesses still return."""
    hits: list[dict] = []
    failed: dict[str, str] = {}
    mapping = (
        ("grok", _enum_grok),
        ("claude", _enum_claude),
        ("codex", _enum_codex),
        ("cursor", _enum_cursor),
        ("cowork", _enum_cowork),
        ("openwork", _enum_openwork),
        ("hermes", _enum_hermes_home),
        ("copilot", _enum_copilot),
        ("pi", lambda root: _enum_loose_jsonl("pi", root)),
        ("continue", _enum_continue),
        ("aider", _enum_aider),
        ("goose", _enum_goose),
        ("amp", _enum_amp),
        ("openhands", _enum_openhands),
        ("crush", _enum_crush),
        ("amazonq", _enum_amazonq),
        ("dsh", _enum_dsh),
        ("gemini", lambda root: _enum_chat_tmp("gemini", root)),
        ("qwen", lambda root: _enum_chat_tmp("qwen", root)),
        ("cline", _enum_cline),
        ("kilo", _enum_kilo),
        ("roo", _enum_roo),
        ("claude_desktop", lambda root: _enum_loose_jsonl("claude_desktop", root)),
    )
    for name, fn in mapping:
        path = homes.get(name)
        if not _store_present(path):
            continue
        try:
            hits.extend(fn(path))
        except PageError as exc:
            failed[name] = exc.kind
        except (OSError, sqlite3.Error):
            failed[name] = "UNREADABLE"
    return hits, failed


def _walk(homes: dict) -> list[dict]:
    hits, _failed = _walk_report(homes)
    return hits


def _match(hit: dict, query: str, harness: str, cwd: str) -> bool:
    if harness and hit["harness"] != harness and PREFIX.get(hit["harness"]) != harness:
        return False
    if cwd and _blob(hit.get("cwd")) != _blob(cwd) and _blob(cwd) not in _blob(hit.get("cwd")):
        return False
    if not query:
        return True
    needle = query.lower()
    hay = " ".join([
        hit.get("id") or "", hit.get("vendor_id") or "", hit.get("title") or "",
        hit.get("cwd") or "", hit.get("harness") or "",
    ]).lower()
    return needle in hay


def _enrich(rows: list[dict]) -> None:
    """Titles for the rows on screen. Legal rows stay blank."""
    for row in rows:
        if row.get("legal"):
            row["title"] = ""
            row["cwd"] = ""
            continue
        if row.get("title"):
            continue
        path = Path(row.get("path") or "")
        if path.suffix.lower() != ".jsonl" or not path.is_file():
            continue
        cwd, title = _sniff(path, HEAD_BYTES)
        if not title:
            title = _first_user_title(path)
        if cwd and not row.get("cwd"):
            row["cwd"] = cwd
        if title:
            row["title"] = title
        if is_legal(str(path), row.get("stream") or "", row.get("cwd") or "", row.get("title") or ""):
            row["legal"] = True
            row["title"] = ""
            row["cwd"] = ""


def _drive_prefix(drive: str) -> str:
    letter = str(drive or "").strip().upper()
    if not letter:
        return ""
    if len(letter) == 1:
        letter += ":"
    return letter[:2] + "\\"


def _on_drive(hit: dict, drive: str) -> bool:
    prefix = _drive_prefix(drive)
    if not prefix:
        return True

    def on(text: str) -> bool:
        blob = str(text or "").replace("/", "\\").upper()
        return blob.startswith(prefix)

    if on(hit.get("path") or ""):
        return True
    # A legal row has a blank cwd on purpose. Do not match it through the project.
    if hit.get("legal"):
        return False
    return on(hit.get("cwd") or "")


_live_lock = threading.Lock()
_live_rows: dict = {"key": None, "at": 0.0, "hits": [], "failed": {}}


def _homes_key(homes: dict) -> tuple:
    return tuple(
        (name, None if homes.get(name) is None else str(homes[name]))
        for name in HARNESSES
    )


def _live_key() -> tuple:
    return _homes_key(default_homes())


def _copy_hits(hits: list[dict]) -> list[dict]:
    return [dict(hit) for hit in hits]


def _live_load(homes: dict, fresh: bool = False) -> tuple[list[dict], dict[str, str]]:
    """Always walk. Remember the live default rows so preview can look up an id.

    The remembered rows never answer find. A session created after the last
    find shows up on the next find. Caller-supplied homes are not remembered.
    """
    del fresh
    hits, failed = _walk_report(homes)
    if _homes_key(homes) == _live_key():
        with _live_lock:
            _live_rows["key"] = _homes_key(homes)
            _live_rows["at"] = time.monotonic()
            _live_rows["hits"] = hits
            _live_rows["failed"] = dict(failed)
    return _copy_hits(hits), dict(failed)


def _live_lookup(homes: dict, rec_id: str) -> dict | None:
    key = _homes_key(homes)
    if key != _live_key():
        return None
    want = str(rec_id)
    norm = _blob(want)
    with _live_lock:
        if _live_rows.get("key") != key:
            return None
        hits = list(_live_rows.get("hits") or [])
    for hit in hits:
        matched = hit["id"] == want or hit["vendor_id"] == want or _blob(hit.get("path") or "") == norm
        aliases = hit.get("aliases") or {}
        if not matched and aliases.get("opencode_id") != want:
            continue
        path = Path(hit.get("path") or "")
        try:
            if not path.exists():
                return None
        except OSError:
            return None
        return dict(hit)
    return None


def find(homes: dict | None = None, query: str = "", harness: str = "",
         cwd: str = "", limit: int = DEFAULT_LIMIT, enrich: bool = True,
         drive: str = "", fresh: bool = False) -> dict:
    homes = homes if homes is not None else default_homes()
    walked, failed = _live_load(homes, fresh=fresh)
    pool = [h for h in walked if _match(h, query, "", cwd) and _on_drive(h, drive)]
    rows = [h for h in pool if _match(h, "", harness, "")]
    rows.sort(key=lambda h: (-(h.get("updated") or 0), h["id"]))
    shown = rows[: max(0, int(limit))]
    if enrich:
        _enrich(shown)
    n_legal = sum(1 for h in rows if h["legal"])
    families = []
    for name in HARNESSES:
        group = [h for h in pool if h["harness"] == name]
        path = homes.get(name)
        present = _store_present(path)
        if name in failed:
            status = failed[name]
            count = None
            n_family_legal = 0
        elif present:
            status = "OK"
            count = len(group)
            n_family_legal = sum(1 for h in group if h["legal"])
        else:
            status = "ABSENT"
            count = None
            n_family_legal = 0
        families.append({
            "family": name,
            "status": status,
            "path": str(path) if path and present else None,
            "n": count,
            "n_legal": n_family_legal,
        })
    return _result("find", "OK", {
        "n": len(rows),
        "n_shown": len(shown),
        "n_legal": n_legal,
        "families": families,
    }, legal_omitted=n_legal, hits=shown, n=len(rows))


def _narrow_homes(homes: dict, rec_id: str) -> dict:
    """A prefixed id only needs one harness store."""
    prefix = str(rec_id).split("-", 1)[0]
    for name, pre in PREFIX.items():
        if prefix == pre and homes.get(name):
            narrowed = {key: None for key in homes}
            narrowed[name] = homes[name]
            return narrowed
    return homes


def _by_id(homes: dict, rec_id: str) -> dict:
    found = _live_lookup(homes, rec_id)
    if found is not None:
        return found
    homes = _narrow_homes(homes, rec_id)
    want = str(rec_id)
    norm = _blob(want)
    for hit in _walk(homes):
        if hit["id"] == want or hit["vendor_id"] == want or _blob(hit["path"]) == norm:
            return hit
        aliases = hit.get("aliases") or {}
        if aliases.get("opencode_id") == want:
            return hit
    path = Path(want)
    if path.is_file():
        found = _hit_from_file(path)
        if found is not None:
            return found
    raise PageError("NOT_FOUND", want)


def _hit_from_file(path: Path) -> dict | None:
    parent = path.parent
    if path.name == "chat_history.jsonl" and (parent / "summary.json").is_file():
        rows = _enum_grok(parent)
        return rows[0] if rows else None
    if path.suffix == ".jsonl" and _UUID.fullmatch(path.stem):
        cwd, title = _claude_meta(path)
        return _hit(harness="claude", vendor_id=path.stem, path=path, cwd=cwd, title=title,
                    updated=_mtime(path), nbytes=path.stat().st_size)
    if _ROLLOUT.match(path.name):
        return _hit(harness="codex", vendor_id=_ROLLOUT.match(path.name).group(1), path=path,
                    updated=_mtime(path), nbytes=path.stat().st_size)
    return None


def _read_jsonl(path: Path) -> tuple[list[dict], bool]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise PageError("NO_STORE", str(path)) from exc
    if size > MAX_BYTES:
        raise PageError("TOO_LARGE", str(path))
    raw = path.read_bytes()
    truncated = False
    rows = []
    for line in raw.splitlines(True):
        piece = line.strip()
        if not piece:
            continue
        try:
            obj = json.loads(piece.decode("utf-8", errors="replace"))
        except ValueError:
            truncated = True
            break
        if isinstance(obj, dict):
            rows.append(obj)
    return rows, truncated


def _turns_from_rows(rows: list[dict], harness: str) -> list[dict]:
    turns = []

    def add(role: str, text: str, model: str | None = None):
        if role not in ("user", "assistant", "system", "tool_call", "tool_result", "meta"):
            role = "meta"
        turns.append({
            "seq": len(turns) + 1,
            "role": role,
            "text": text if text != "" else None,
            "model": model,
        })

    if harness in ("claude", "claude_desktop", "cursor", "gemini"):
        role_of = {"user": "user", "assistant": "assistant", "system": "system"}
        for obj in rows:
            kind = str(obj.get("type") or obj.get("role") or "")
            if kind not in role_of and kind not in ("tool_result", "tool_use"):
                continue
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
            role = role_of.get(kind, "tool_result" if "tool" in kind else "meta")
            if kind == "tool_use":
                role = "tool_call"
            add(role, _text_of(msg.get("content") if isinstance(msg, dict) else msg),
                (msg.get("model") if isinstance(msg, dict) else None))
        return turns
    if harness == "grok":
        role_of = {
            "user": "user", "assistant": "assistant", "system": "system",
            "tool_result": "tool_result", "tool": "tool_result",
            "tool_call": "tool_call",
        }
        for obj in rows:
            kind = str(obj.get("type") or obj.get("role") or "meta")
            text = obj.get("text")
            if text is None:
                text = obj.get("content") if not isinstance(obj.get("content"), (dict, list)) else _text_of(obj.get("content"))
            if isinstance(text, (dict, list)):
                text = _text_of(text)
            add(role_of.get(kind, "meta"), "" if text is None else str(text), obj.get("model"))
        return turns
    if harness == "codex":
        for obj in rows:
            if obj.get("type") != "response_item":
                continue
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
            role = str(payload.get("role") or "meta")
            if role not in ("user", "assistant", "system"):
                role = "meta"
            add(role, _text_of(payload.get("content")))
        return turns
    if harness == "copilot":
        role_of = {
            "user.message": "user",
            "assistant.message": "assistant",
            "system.message": "system",
            "tool.execution_start": "tool_call",
        }
        for obj in rows:
            kind = str(obj.get("type") or "")
            if kind not in role_of:
                continue
            data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
            text = data.get("content")
            if text is None and kind == "tool.execution_start":
                text = data.get("toolName") or ""
            add(role_of[kind], _text_of(text), data.get("model") if isinstance(data.get("model"), str) else None)
        return turns
    if harness in _MESSAGE_HARNESSES:
        role_of = {"user": "user", "assistant": "assistant", "system": "system"}
        for obj in rows:
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
            kind = str(
                obj.get("role")
                or (msg.get("role") if isinstance(msg, dict) else "")
                or obj.get("type")
                or ""
            )
            if kind not in role_of and kind not in ("tool_result", "tool_use", "tool_call"):
                continue
            role = role_of.get(kind, "tool_call" if kind == "tool_use" else "tool_result")
            content = msg.get("content") if isinstance(msg, dict) else obj.get("content")
            if content is None and isinstance(msg, dict):
                content = msg.get("text")
            add(role, _text_of(content), msg.get("model") if isinstance(msg, dict) else None)
        return turns
    return turns


def _turns_cowork(hit: dict) -> tuple[list[dict], bool]:
    if hit["legal"]:
        raise PageError("LEGAL_OMITTED", hit["id"])
    path = Path(hit["path"])
    if not path.is_file() or path.suffix.lower() not in (".md", ".txt", ".jsonl"):
        return [], False
    _guard_size(path)
    if path.suffix.lower() == ".jsonl":
        rows, truncated = _read_jsonl(path)
        return _turns_from_rows(rows, "grok"), truncated
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks = re.split(r"\n(?=## \[\d+\] )", text)
    turns = []
    if len(chunks) > 1:
        for chunk in chunks:
            match = re.match(r"## \[(\d+)\]\s+(\w+)", chunk)
            if not match:
                continue
            role = match.group(2).lower()
            if role not in ("user", "assistant", "system"):
                role = "meta"
            body = chunk.split("\n", 1)[1] if "\n" in chunk else ""
            turns.append({"seq": len(turns) + 1, "role": role, "text": body.strip(), "model": None})
    else:
        turns.append({"seq": 1, "role": "user", "text": text, "model": None})
    return turns, False


def _turns_openwork(hit: dict) -> tuple[list[dict], bool]:
    if str(hit["vendor_id"]).startswith("ses_cow_"):
        raise PageError("DO_NOT_REINGEST", hit["id"])
    if hit["legal"]:
        raise PageError("LEGAL_OMITTED", hit["id"])
    db = Path(hit["path"])
    try:
        uri = db.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=1.0)
        msgs = list(con.execute(
            "SELECT data FROM message WHERE session_id=? ORDER BY time_created, id",
            (hit["vendor_id"],),
        ))
        con.close()
    except sqlite3.Error as exc:
        raise PageError("SCHEMA_UNKNOWN", str(exc))
    turns = []
    for (data,) in msgs:
        try:
            obj = json.loads(data) if isinstance(data, str) else json.loads(data.decode("utf-8"))
        except (ValueError, AttributeError):
            obj = {"text": str(data)}
        role = str(obj.get("role") or obj.get("type") or "meta")
        if role not in ("user", "assistant", "system"):
            role = "meta"
        turns.append({
            "seq": len(turns) + 1,
            "role": role,
            "text": _text_of(obj.get("content") if "content" in obj else obj.get("text")),
            "model": obj.get("model"),
        })
    return turns, False


def _guard_size(path: Path) -> int:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise PageError("NO_STORE", str(path)) from exc
    if size > MAX_BYTES:
        raise PageError("TOO_LARGE", str(path))
    return size


def _open_hit(hit: dict) -> dict:
    """Refuse a legal transcript before any full read. Header sniff only."""
    if hit.get("legal"):
        raise PageError("LEGAL_OMITTED", hit["id"])
    path = Path(hit.get("path") or "")
    if path.is_file() and path.suffix.lower() in (".jsonl", ".json", ".md", ".txt"):
        cwd, title = _sniff(path, HEAD_BYTES)
        if is_legal(str(path), hit.get("stream") or "", cwd or hit.get("cwd") or "", title or hit.get("title") or ""):
            raise PageError("LEGAL_OMITTED", hit["id"])
    return hit


def _rows_from_json(obj: object) -> list[dict]:
    if isinstance(obj, list):
        return [item for item in obj if isinstance(item, dict)]
    if isinstance(obj, dict):
        inner = obj.get("history") or obj.get("messages") or obj.get("conversation")
        if isinstance(inner, list):
            return [item for item in inner if isinstance(item, dict)]
    return []


def load_record(hit: dict) -> dict:
    hit = _open_hit(hit)
    path = Path(hit["path"])
    if path.is_file():
        _guard_size(path)
    truncated = False
    if hit["harness"] == "cowork":
        turns, truncated = _turns_cowork(hit)
        source_sha = sha256_bytes(path.read_bytes()) if path.is_file() else ""
    elif hit["harness"] == "openwork":
        turns, truncated = _turns_openwork(hit)
        source_sha = sha256_bytes(path.read_bytes()) if path.is_file() else ""
    elif path.suffix.lower() == ".jsonl" and path.is_file():
        rows, truncated = _read_jsonl(path)
        turns = _turns_from_rows(rows, hit["harness"])
        source_sha = sha256_bytes(path.read_bytes())
    elif path.suffix.lower() == ".json" and path.is_file():
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PageError("UNPARSEABLE", str(path)) from exc
        rows = _rows_from_json(obj)
        if not rows:
            raise PageError("UNMEASURED", str(path))
        turns = _turns_from_rows(rows, hit["harness"])
        truncated = False
        source_sha = sha256_bytes(path.read_bytes())
    elif hit["harness"] == "cursor" and path.suffix.lower() == ".db":
        raise PageError("UNMEASURED", "cursor store.db has no transcript adapter in this plug")
    else:
        raise PageError("UNMEASURED", hit["path"])
    head = {
        "schema": TRANSCRIPT,
        "kind": "COSMOS_TRANSCRIPT",
        "id": hit["id"],
        "family": hit["harness"],
        "vendor_session_id": hit["vendor_id"],
        "title": hit.get("title") or "",
        "stream": hit.get("stream") or "unknown",
        "legal": False,
        "cwd": hit.get("cwd") or "",
        "n_turns": len(turns),
        "sources": [{
            "idx": 0, "path": str(path), "kind": path.suffix.lstrip(".") or "file",
            "len": path.stat().st_size if path.is_file() else 0,
            "sha256": source_sha, "fidelity": "span" if path.suffix.lower() != ".db" else "blob",
        }],
        "aliases": hit.get("aliases") or {},
    }
    return {"head": head, "turns": turns, "truncated": truncated, "source_sha": source_sha}


def encode_transcript(head: dict, turns: list[dict]) -> bytes:
    body = dict(head)
    body["n_turns"] = len(turns)
    lines = [json.dumps(body, ensure_ascii=False, separators=(",", ":"))]
    for turn in turns:
        lines.append(json.dumps(turn, ensure_ascii=False, separators=(",", ":")))
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_pair(out_dir: Path, stem: str, payload: bytes, source_sha: str, n_turns: int,
               anonymized: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / f"{stem}.ctr.jsonl"
    decl = out_dir / f"{stem}.ctr.decl.json"
    if jsonl.exists() or decl.exists():
        stage = var_dir() / "replaced" / time.strftime("%Y%m%dT%H%M%S")
        stage.mkdir(parents=True, exist_ok=True)
        for path in (jsonl, decl):
            if path.exists():
                shutil.copy2(path, stage / path.name)
    jsonl.write_bytes(payload)
    side = {
        "len": len(payload),
        "sha": sha256_bytes(payload),
        "n_turns": n_turns,
        "source_sha": source_sha,
        "fidelity": "span",
        "anonymized": anonymized,
    }
    decl.write_text(json.dumps(side, indent=2) + "\n", encoding="utf-8")
    return {"jsonl": str(jsonl), "decl": str(decl), "sha": side["sha"], "len": side["len"], "n_turns": n_turns}


def _speakable(turns: list[dict]) -> list[dict]:
    """User and assistant lines. System prompts stay out of the preview pane."""
    return [
        turn for turn in turns
        if turn.get("role") in ("user", "assistant") and (turn.get("text") or "").strip()
    ]


def _clip_turns(turns: list[dict], n: int, chars: int) -> list[dict]:
    picked = _speakable(turns)
    source = picked if picked else turns
    shown = []
    for turn in source[: max(0, n)]:
        text = (turn.get("text") or "").strip()
        if chars >= 0 and len(text) > chars:
            text = text[:chars].rstrip() + "…"
        shown.append({"seq": turn.get("seq"), "role": turn.get("role") or "meta", "text": text})
    return shown


def _preview_result(hit: dict, kind: str, n_turns: int | None, shown: list[dict]) -> dict:
    return _result("preview", kind, {
        "id": hit["id"], "n_turns": n_turns, "shown": len(shown), "turns": shown,
    })


def _jsonl_head_turns(path: Path, harness: str, n_want: int) -> tuple[list[dict], int | None, bool]:
    """Read a short preview. A small file reports a real total. Nothing is hashed."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise PageError("NO_STORE", str(path)) from exc
    if size <= PREVIEW_WHOLE:
        rows, truncated = _read_jsonl(path)
        parsed = _turns_from_rows(rows, harness)
        return parsed, len(parsed), truncated
    if n_want <= 0:
        return [], None, False
    collected: list[dict] = []
    read = 0
    budget = 2 * 1024 * 1024
    stopped = False
    bad = False
    with path.open("rb") as handle:
        for line in handle:
            read += len(line)
            piece = line.strip()
            if piece:
                try:
                    obj = json.loads(piece.decode("utf-8", errors="replace"))
                except ValueError:
                    bad = True
                    stopped = True
                    break
                if isinstance(obj, dict):
                    collected.append(obj)
            parsed = _turns_from_rows(collected, harness)
            if len(_speakable(parsed)) >= n_want or read >= budget:
                stopped = True
                break
    parsed = _turns_from_rows(collected, harness)
    if bad or stopped:
        return parsed, None, bad
    return parsed, len(parsed), False


def _message_turns(rows: list[tuple]) -> list[dict]:
    turns = []
    for (data,) in rows:
        try:
            obj = json.loads(data) if isinstance(data, str) else json.loads(data.decode("utf-8"))
        except (ValueError, AttributeError):
            obj = {"text": str(data)}
        role = str(obj.get("role") or obj.get("type") or "meta")
        if role not in ("user", "assistant", "system"):
            role = "meta"
        turns.append({
            "seq": len(turns) + 1,
            "role": role,
            "text": _text_of(obj.get("content") if "content" in obj else obj.get("text")),
            "model": obj.get("model"),
        })
    return turns


def _preview_openwork(hit: dict, n_want: int, chars: int) -> dict:
    if str(hit["vendor_id"]).startswith("ses_cow_"):
        raise PageError("DO_NOT_REINGEST", hit["id"])
    db = Path(hit["path"])
    try:
        uri = db.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=1.0)
        total = con.execute(
            "SELECT COUNT(*) FROM message WHERE session_id=?",
            (hit["vendor_id"],),
        ).fetchone()
        n_turns = int(total[0]) if total else 0
        msgs = list(con.execute(
            "SELECT data FROM message WHERE session_id=? ORDER BY time_created, id LIMIT ?",
            (hit["vendor_id"], int(max(0, n_want))),
        ))
        con.close()
    except sqlite3.Error as exc:
        raise PageError("SCHEMA_UNKNOWN", str(exc))
    shown = _clip_turns(_message_turns(msgs), n_want, chars)
    return _preview_result(hit, "OK", n_turns, shown)


def _preview_cowork(hit: dict, n_want: int, chars: int) -> dict:
    path = Path(hit["path"])
    if path.suffix.lower() == ".jsonl":
        parsed, n_turns, truncated = _jsonl_head_turns(path, "grok", n_want)
        kind = "TRUNCATED" if truncated else "OK"
        return _preview_result(hit, kind, n_turns, _clip_turns(parsed, n_want, chars))
    size = _guard_size(path)
    if path.suffix.lower() not in (".md", ".txt"):
        raise PageError("UNMEASURED", hit["path"])
    if size <= PREVIEW_WHOLE:
        turns, truncated = _turns_cowork(hit)
        kind = "TRUNCATED" if truncated else "OK"
        return _preview_result(hit, kind, len(turns), _clip_turns(turns, n_want, chars))
    with path.open("rb") as handle:
        text = handle.read(PREVIEW_WHOLE).decode("utf-8", errors="replace")
    turns, _truncated = _md_turns(text), False
    return _preview_result(hit, "OK", None, _clip_turns(turns, n_want, chars))


def _md_turns(text: str) -> list[dict]:
    chunks = re.split(r"\n(?=## \[\d+\] )", text)
    turns = []
    if len(chunks) > 1:
        for chunk in chunks:
            match = re.match(r"## \[(\d+)\]\s+(\w+)", chunk)
            if not match:
                continue
            role = match.group(2).lower()
            if role not in ("user", "assistant", "system"):
                role = "meta"
            body = chunk.split("\n", 1)[1] if "\n" in chunk else ""
            turns.append({"seq": len(turns) + 1, "role": role, "text": body.strip(), "model": None})
        return turns
    return [{"seq": 1, "role": "user", "text": text, "model": None}]


def preview(rec_id: str, homes: dict | None = None, turns: int = 6, chars: int = 400) -> dict:
    """A short read of one session. Legal rows are refused. Nothing is written."""
    homes = homes if homes is not None else default_homes()
    hit = _open_hit(_by_id(homes, rec_id))
    path = Path(hit["path"])
    n_want = max(0, int(turns))
    limit = max(0, int(chars))
    if hit["harness"] == "openwork":
        return _preview_openwork(hit, n_want, limit)
    if hit["harness"] == "cowork":
        return _preview_cowork(hit, n_want, limit)
    if path.suffix.lower() == ".jsonl" and path.is_file():
        parsed, n_turns, truncated = _jsonl_head_turns(path, hit["harness"], n_want)
        kind = "TRUNCATED" if truncated else "OK"
        return _preview_result(hit, kind, n_turns, _clip_turns(parsed, n_want, limit))
    if path.suffix.lower() == ".json" and path.is_file():
        _guard_size(path)
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PageError("UNPARSEABLE", str(path)) from exc
        rows = _rows_from_json(obj)
        if not rows:
            raise PageError("UNMEASURED", str(path))
        parsed = _turns_from_rows(rows, hit["harness"])
        return _preview_result(hit, "OK", len(parsed), _clip_turns(parsed, n_want, limit))
    if hit["harness"] == "cursor" and path.suffix.lower() == ".db":
        raise PageError("UNMEASURED", "cursor store.db has no transcript adapter in this plug")
    raise PageError("UNMEASURED", hit["path"])


def _source_hash(path: Path) -> str:
    if not path.is_file():
        return ""
    return sha256_bytes(path.read_bytes())


def _same_source(path: Path, before: str) -> None:
    if before and _source_hash(path) != before:
        raise PageError("FIDELITY_MISMATCH", "source changed during read")


def import_session(rec_id: str, out_dir: Path, homes: dict | None = None) -> dict:
    homes = homes if homes is not None else default_homes()
    hit = _open_hit(_by_id(homes, rec_id))
    source = Path(hit["path"])
    before = _source_hash(source)
    loaded = load_record(hit)
    _same_source(source, before)
    payload = encode_transcript(loaded["head"], loaded["turns"])
    written = write_pair(out_dir, hit["id"], payload, loaded["source_sha"], len(loaded["turns"]))
    kind = "TRUNCATED" if loaded["truncated"] else "OK"
    return _result("import", kind, {
        "id": hit["id"], "n_turns": len(loaded["turns"]),
        "source_sha": loaded["source_sha"], "out_sha": written["sha"],
    }, written=written, original_untouched=True)


def export_md(rec_id: str, out_dir: Path, homes: dict | None = None) -> dict:
    homes = homes if homes is not None else default_homes()
    hit = _open_hit(_by_id(homes, rec_id))
    source = Path(hit["path"])
    before = _source_hash(source)
    loaded = load_record(hit)
    _same_source(source, before)
    lines = [f"# {loaded['head'].get('title') or hit['id']}", "",
             f"harness: {hit['harness']}", f"id: {hit['id']}", ""]
    for turn in loaded["turns"]:
        lines.append(f"## [{turn['seq']}] {turn['role']}")
        lines.append(turn.get("text") or "")
        lines.append("")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{hit['id']}.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    kind = "TRUNCATED" if loaded["truncated"] else "OK"
    return _result("export", kind, {
        "id": hit["id"], "out": str(dest), "out_sha": sha256_bytes(dest.read_bytes()),
        "source_sha": before, "n_turns": len(loaded["turns"]),
    }, original_untouched=True)


def build_index(out_path: Path | None = None, homes: dict | None = None,
                limit: int = 0) -> dict:
    found = find(homes=homes, limit=limit or 10**9, enrich=False)
    out_path = out_path or (var_dir() / "index.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for hit in found["hits"]:
        row = {
            "schema": INDEX_SCHEMA,
            "id": hit["id"],
            "harness": hit["harness"],
            "vendor_id": hit["vendor_id"],
            "path": hit["path"],
            "cwd": "" if hit["legal"] else hit.get("cwd") or "",
            "title": "" if hit["legal"] else hit.get("title") or "",
            "legal": bool(hit["legal"]),
            "updated": hit.get("updated"),
            "bytes": hit.get("bytes"),
            "aliases": hit.get("aliases") or {},
        }
        lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    out_path.write_bytes(payload)
    return _result("index", "OK", {
        "n": found["n"], "n_legal": found["legal_omitted"],
        "out": str(out_path), "out_sha": sha256_bytes(payload), "len": len(payload),
    }, legal_omitted=found["legal_omitted"])


def _jsonl_state(path: Path) -> tuple[str, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return "busy", str(exc)
    if not raw.strip():
        return "damage", "empty"
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return "damage", "jsonl"
    return "ok", "jsonl"


def _jsonl_ok(path: Path) -> bool:
    return _jsonl_state(path)[0] == "ok"


def _sqlite_state(path: Path) -> tuple[str, str]:
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=1.0)
        integ = con.execute("PRAGMA integrity_check").fetchone()[0]
        con.close()
        del con
        gc.collect()
    except sqlite3.Error as exc:
        text = str(exc).lower()
        if "locked" in text or "busy" in text or "unable to open" in text or "disk i/o" in text:
            return "busy", str(exc)
        return "damage", str(exc)
    if integ != "ok":
        return "damage", f"integrity={integ}"
    return "ok", "ok"


def _sqlite_ok(path: Path) -> tuple[bool, str]:
    state, detail = _sqlite_state(path)
    return state == "ok", detail


def _file_state(path: Path, sqlite_target: bool) -> tuple[str, str]:
    if sqlite_target:
        return _sqlite_state(path)
    return _jsonl_state(path)


_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _park_sidecars(target: Path, stage_dir: Path) -> list[tuple[Path, Path]]:
    parked = []
    for suffix in _SIDECAR_SUFFIXES:
        side = Path(str(target) + suffix)
        if not side.is_file() or side.is_symlink():
            continue
        dest = stage_dir / side.name
        os.replace(side, dest)
        parked.append((side, dest))
    return parked


def _unpark_sidecars(parked: list[tuple[Path, Path]]) -> None:
    for original, staged in reversed(parked):
        if staged.is_file():
            os.replace(staged, original)


def recover(target: Path, bak: Path | None = None, stage: Path | None = None,
            apply: bool = False) -> dict:
    """Check, then replace from a verified bak. Never edits the broken bytes in place."""
    if not target.exists():
        raise PageError("NO_STORE", str(target))
    if is_legal(str(target)):
        raise PageError("LEGAL_OMITTED", str(target))
    suffix = target.suffix.lower()
    sqlite_target = suffix in (".db", ".sqlite")
    if suffix == ".jsonl":
        cwd, title = _sniff(target, HEAD_BYTES)
        if is_legal(str(target), "", cwd, title):
            raise PageError("LEGAL_OMITTED", str(target))
    elif not sqlite_target:
        raise PageError("UNMEASURED", suffix or target.name)
    state, detail = _file_state(target, sqlite_target)
    if state == "busy":
        return _result("recover", "BUSY", {"target": str(target), "detail": detail})
    if state == "ok":
        return _result("recover", "ALREADY_OK", {"target": str(target), "detail": detail})
    candidates = [bak] if bak is not None else _bak_candidates(target)
    chosen: Path | None = None
    bak_detail = detail
    for cand in candidates:
        if cand is None or not cand.is_file():
            continue
        cand_state, cand_detail = _file_state(cand, sqlite_target)
        if cand_state == "ok":
            chosen = cand
            break
        bak_detail = cand_detail
    if chosen is None:
        if any(cand is not None and cand.is_file() for cand in candidates):
            raise PageError("BAD_BAK", bak_detail)
        return _result("recover", "NO_BAK", {"target": str(target), "detail": detail})
    bak = chosen
    bak_sha = sha256_bytes(bak.read_bytes())
    if not apply:
        return _result("recover", "DRY_RUN", {
            "target": str(target), "bak": str(bak), "bak_sha": bak_sha, "detail": detail,
        })
    stage_root = stage or (var_dir() / "stage")
    staged = stage_root / time.strftime("%Y%m%dT%H%M%S") / target.name
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, staged)
    staged_sha = sha256_bytes(staged.read_bytes())
    parked: list[tuple[Path, Path]] = []
    incoming = target.with_name(target.name + ".restore")
    try:
        if sqlite_target:
            parked = _park_sidecars(target, staged.parent)
        shutil.copy2(bak, incoming)
        restored = sha256_bytes(incoming.read_bytes())
        if restored != bak_sha:
            raise PageError("RESTORE_FAILED", str(staged))
        last_exc: OSError | None = None
        for _try in range(10):
            try:
                os.replace(incoming, target)
                last_exc = None
                break
            except PermissionError as exc:
                last_exc = exc
                time.sleep(0.05)
        if last_exc is not None:
            raise PageError("RESTORE_FAILED", str(staged)) from last_exc
        again, again_detail = _file_state(target, sqlite_target)
        if again != "ok":
            rollback = target.with_name(target.name + ".rollback")
            shutil.copy2(staged, rollback)
            os.replace(rollback, target)
            _unpark_sidecars(parked)
            raise PageError("RESTORE_FAILED", again_detail)
    except Exception:
        incoming.unlink(missing_ok=True)
        if parked:
            try:
                _unpark_sidecars(parked)
            except OSError:
                pass
        raise
    return _result("recover", "OK", {
        "target": str(target), "bak_path": str(bak), "bak_sha": bak_sha,
        "staged_path": str(staged), "staged_sha": staged_sha, "restored_sha": restored,
    })


def _which(names: list[str], extra: list[Path]) -> str | None:
    for path in extra:
        if path.is_file():
            return str(path)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def resume(rec_id: str, homes: dict | None = None, launch: bool = False) -> dict:
    homes = homes if homes is not None else default_homes()
    hit = _open_hit(_by_id(homes, rec_id))
    harness = hit["harness"]
    vid = hit["vendor_id"]
    cwd = hit.get("cwd") or ""
    home = Path.home()
    if harness == "grok":
        argv = ["grok", "--resume", vid]
        binary = _which(["grok"], [home / ".grok" / "bin" / "grok.exe"])
    elif harness == "claude":
        argv = ["claude", "--resume", vid]
        binary = _which(["claude"], [])
    elif harness == "codex":
        argv = ["codex", "resume", vid]
        binary = _which(["codex"], [])
    elif harness == "cursor":
        argv = ["agent", "--resume", vid]
        binary = _which(["agent", "cursor-agent"], [])
    elif harness == "pi":
        argv = ["pi", "--session", str(hit["path"])]
        binary = _which(["pi"], [])
    elif harness == "hermes":
        argv = ["hermes", "--resume", vid]
        binary = _which(["hermes"], [])
    elif harness == "cline" and str(hit["path"]).endswith(".messages.json"):
        argv = ["cline", "--id", vid]
        binary = _which(["cline"], [])
    elif harness == "goose":
        argv = ["goose", "session", "--resume", "--session-id", vid]
        binary = _which(["goose"], [])
    elif harness == "qwen":
        argv = ["qwen", "--resume", vid]
        binary = _which(["qwen"], [])
    elif harness == "copilot":
        argv = ["copilot", f"--resume={vid}"]
        binary = _which(["copilot"], [])
    elif harness == "crush":
        argv = ["crush", "--session", vid]
        binary = _which(["crush"], [])
    elif harness in ("openwork", "cowork"):
        opencode = (hit.get("aliases") or {}).get("opencode_id") or vid
        return _result("resume", "OPENWORK_FOCUS", {
            "id": hit["id"], "harness": harness, "opencode_id": opencode,
            "argv": [], "launched": False,
            "detail": "focus this id in OpenWork; this plug does not spawn OpenWork.exe",
        })
    else:
        return _result("resume", "UNMEASURED", {
            "id": hit["id"], "harness": harness, "argv": None, "launched": False,
        })
    if binary:
        argv = [binary, *argv[1:]]
    gate = {
        "id": hit["id"], "harness": harness, "argv": argv, "cwd": cwd,
        "binary": binary, "launched": False,
    }
    if not launch:
        return _result("resume", "OK", gate)
    if not binary:
        return _result("resume", "BINARY_ABSENT", gate)
    if cwd and not Path(cwd).is_dir():
        raise PageError("CWD_MISSING", cwd)
    flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    proc = subprocess.Popen(argv, cwd=cwd or None, creationflags=flags, close_fds=True)
    gate["launched"] = True
    gate["pid"] = proc.pid
    return _result("resume", "LAUNCHED", gate)


def redact(text: str) -> tuple[str, int]:
    if not text:
        return "", 0
    n = 0
    out = text
    for kind, rx in _REDACT:
        if kind == "secret-assign":
            def _sub(match, _k=kind):
                return f"{match.group(1)}=[REDACTED:{_k}]"
            out, k = rx.subn(_sub, out)
        else:
            out, k = rx.subn(f"[REDACTED:{kind}]", out)
        n += k
    return out, n


def _strip_text(text: str) -> str:
    return _STRIP_TAGS.sub(" ", text or "").strip()


def anonymize(rec_id: str, out_dir: Path, homes: dict | None = None) -> dict:
    homes = homes if homes is not None else default_homes()
    hit = _open_hit(_by_id(homes, rec_id))
    source = Path(hit["path"])
    before = _source_hash(source)
    loaded = load_record(hit)
    _same_source(source, before)
    n = 0
    cleaned = []
    for turn in loaded["turns"]:
        text, k = redact(turn.get("text") or "")
        n += k
        row = dict(turn)
        row["text"] = text
        row["redactions"] = k
        cleaned.append(row)
    payload = encode_transcript(loaded["head"], cleaned)
    written = write_pair(out_dir, hit["id"] + ".anon", payload, loaded["source_sha"], len(cleaned), anonymized=True)
    kind = "TRUNCATED" if loaded["truncated"] else "OK"
    return _result("anonymize", kind, {
        "n_redactions": n, "source_sha": before, "out_sha": written["sha"], "id": hit["id"],
    }, written=written, original_untouched=True)


def strip(rec_id: str, out_dir: Path | None, homes: dict | None = None, dry: bool = False) -> dict:
    homes = homes if homes is not None else default_homes()
    hit = _open_hit(_by_id(homes, rec_id))
    loaded = load_record(hit)
    kept = []
    dropped = 0
    for turn in loaded["turns"]:
        if turn["role"] in _TOOL_ROLES:
            dropped += 1
            continue
        text = _strip_text(turn.get("text") or "")
        if text != (turn.get("text") or ""):
            dropped += 1
        if not text:
            continue
        row = dict(turn)
        row["text"] = text
        row["seq"] = len(kept) + 1
        kept.append(row)
    gate = {"id": hit["id"], "kept": len(kept), "dropped_markers": dropped, "dry": dry}
    kind = "TRUNCATED" if loaded["truncated"] else "OK"
    if dry:
        return _result("strip_dry", kind, gate)
    if out_dir is None:
        raise PageError("NO_OUTDIR", "strip needs an output directory")
    payload = encode_transcript(loaded["head"], kept)
    written = write_pair(out_dir, hit["id"] + ".strip", payload, loaded["source_sha"], len(kept))
    gate["out_sha"] = written["sha"]
    return _result("strip", kind, gate, written=written, original_untouched=True)


def _result(verb: str, kind: str, gate: dict, legal_omitted: int = 0, **extra) -> dict:
    rec = {
        "schema": SCHEMA,
        "verb": verb,
        "kind": kind,
        "gate": gate,
        "legal_omitted": legal_omitted,
    }
    rec.update(extra)
    return rec


def _homes_from_body(body: dict, homes: dict | None) -> dict:
    if homes is not None:
        return homes
    base = default_homes()
    store = body.get("store") or body.get("path")
    if store:
        base = dict(base)
        base["__store__"] = Path(store)
    return base


def _bak_candidates(target: Path) -> list[Path]:
    """Sibling backups only, newest first. Never a volume-wide search."""
    try:
        children = list(target.parent.iterdir())
    except OSError:
        return []
    found = []
    try:
        target_res = target.resolve()
    except OSError:
        target_res = target
    for child in children:
        if not child.is_file() or child.is_symlink():
            continue
        try:
            if child.resolve() == target_res:
                continue
        except OSError:
            continue
        name = child.name
        if name.startswith(target.name) and ".bak" in name:
            found.append(child)
    found.sort(key=_mtime, reverse=True)
    return found


def nearest_bak(target: Path) -> Path | None:
    """Newest sibling backup. It is not checked; recover chooses a good one."""
    found = _bak_candidates(target)
    return found[0] if found else None


def _store_homes(store: Path) -> dict:
    """One operator-picked store, detected. Does not scan the user profile."""
    homes = {name: None for name in HARNESSES}
    cat = _catalog_file(store)
    if cat is not None:
        homes["cowork"] = store if store.is_dir() else cat
        return homes
    if store.is_file() and store.suffix.lower() in (".db", ".sqlite"):
        homes["openwork"] = store
        return homes
    if not store.is_dir():
        return homes
    if (store / "chats").is_dir() or (store / "projects" / "agent-transcripts").exists():
        homes["cursor"] = store
        return homes
    try:
        nested_summary = any(store.glob("summary.json")) or any(store.glob("*/summary.json")) or any(store.glob("*/*/summary.json"))
    except OSError:
        nested_summary = False
    if nested_summary:
        homes["grok"] = store
        return homes
    try:
        rollouts = any(store.glob("rollout-*.jsonl")) or any(store.glob("state_*.sqlite")) or any(store.glob("sessions/*/rollout-*.jsonl"))
    except OSError:
        rollouts = False
    if rollouts:
        homes["codex"] = store
        return homes
    try:
        claude_jsonl = any(
            p.is_file() and p.suffix == ".jsonl" and _UUID.fullmatch(p.stem)
            for p in list(store.glob("*.jsonl")) + list(store.glob("*/*.jsonl"))
        )
    except OSError:
        claude_jsonl = False
    if claude_jsonl:
        homes["claude"] = store
        return homes
    return homes


def scan(store: Path) -> dict:
    homes = _store_homes(store)
    if not any(homes.values()):
        return _result("scan", "UNMEASURED", {"n": None, "path": str(store), "families": []})
    found = find(homes=homes, limit=20)
    n = found["n"]
    return _result("scan", "OK", {
        "n": n,
        "families": found["gate"]["families"],
        "sample_ids": [h["id"] for h in found["hits"][:5]],
    }, legal_omitted=found["legal_omitted"], n=n)


def diff_files(left: Path, right: Path) -> dict:
    if not left.is_file() or not right.is_file():
        raise PageError("NOT_FOUND", f"{left} {right}")
    lb, rb = left.read_bytes(), right.read_bytes()
    def n_turns(raw: bytes) -> int | None:
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        if not lines:
            return 0
        try:
            json.loads(lines[0])
        except ValueError:
            return None
        return max(0, len(lines) - 1)
    lt, rt = n_turns(lb), n_turns(rb)
    delta = None if lt is None or rt is None else rt - lt
    return _result("diff", "OK", {
        "left_sha": sha256_bytes(lb), "right_sha": sha256_bytes(rb),
        "n_turns_delta": delta, "identical": lb == rb,
    })


def check(what: str, path: Path, chair: str = "ccr") -> dict:
    if what == "catalog":
        cat = _catalog_file(path)
        if cat is None:
            raise PageError("NO_STORE", str(path))
        rows = json.loads(cat.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise PageError("UNPARSEABLE", str(cat))
        missing = []
        for row in rows:
            fn = row.get("filename") if isinstance(row, dict) else None
            if not fn:
                continue
            if not (cat.parent / "ordered_transcripts" / fn).is_file() and not (cat.parent / fn).is_file():
                missing.append(fn)
        if missing:
            raise PageError("MISSING_PART", ",".join(missing[:20]))
        return _result("check", "VERIFIED", {"n": len(rows), "path": str(cat), "what": "catalog"})
    if what == "sqlite":
        if path.is_dir():
            nested = path / "opencode.db"
            path = nested if nested.is_file() else path
        ok, detail = _sqlite_ok(path)
        if not ok:
            raise PageError("SQLITE_CORRUPT", detail)
        return _result("check", "VERIFIED", {"what": "sqlite", "integrity_check": detail, "path": str(path)})
    if what == "seed":
        seed = path if path.is_file() else path / "SEED.json"
        decl = seed.with_name("SEED.decl.json")
        if not seed.is_file():
            raise PageError("NO_SEED", str(seed))
        if not decl.is_file():
            raise PageError("NO_SEED", str(decl))
        raw = seed.read_bytes()
        side = json.loads(decl.read_text(encoding="utf-8"))
        if int(side.get("len") or -1) != len(raw) or str(side.get("sha") or "") != sha256_bytes(raw):
            raise PageError("BAD_SEED", "len/sha mismatch")
        return _result("check", "VERIFIED", {
            "what": "seed", "sha": side.get("sha"), "len": len(raw),
            "mac_present": bool(side.get("mac")), "mac_ok": None,
        })
    if what == "sit":
        if not path.is_file():
            raise PageError("NO_STORE", str(path))
        text = path.read_text(encoding="utf-8", errors="replace")
        if chair == "ccr":
            if "bucm/1" not in text:
                raise PageError("SIT_MIXED", "ccr sit is not bucm/1")
            return _result("check", "VERIFIED", {"what": "sit", "sit": "ccr", "schema": "bucm/1"})
        if chair == "orc":
            if "burestart/3" not in text:
                raise PageError("SIT_MIXED", "orc sit is not burestart/3")
            return _result("check", "VERIFIED", {"what": "sit", "sit": "orc", "schema": "burestart/3"})
        raise PageError("UNMEASURED", chair)
    raise PageError("UNMEASURED", what)


def dispatch(action: str, body: dict | None = None, homes: dict | None = None) -> dict:
    body = body or {}
    action = str(action or body.get("action") or body.get("verb") or "")
    if action in ("migrate", "rebind"):
        return _result(action, "DO_NOT_REINGEST", {"detail": "666 re-ingest and rebind stay closed"})
    if action == "doi":
        return _result("doi", "UNPROVEN", {"detail": "citation existence is not fetched"})
    if action not in VERBS:
        raise PageError("BAD_ACTION", action or "(empty)")
    if action == "preview":
        rec_id = str(body.get("id") or "")
        if not rec_id:
            raise PageError("NOT_FOUND", "id is required")
        return preview(rec_id, homes=homes if homes is not None else _homes_for(body))
    if action == "find":
        flag = body.get("fresh", False)
        if not isinstance(flag, bool):
            raise PageError("BAD_INPUT", "fresh must be boolean")
        return find(
            homes=homes, query=str(body.get("query") or body.get("q") or ""),
            harness=str(body.get("harness") or body.get("family") or ""),
            cwd=str(body.get("cwd") or ""),
            limit=int(body.get("limit") or DEFAULT_LIMIT),
            drive=str(body.get("drive") or ""),
            fresh=flag,
        )
    if action == "scan":
        store = body.get("store") or body.get("path")
        if not store:
            raise PageError("NO_STORE", "scan needs a store")
        return scan(Path(store))
    if action in ("import", "load", "convert"):
        rec_id = str(body.get("id") or "")
        if not rec_id:
            raise PageError("NOT_FOUND", "id is required")
        out = body.get("out") or body.get("out_dir")
        if action == "load" and not out:
            hit = _by_id(homes if homes is not None else _homes_for(body), rec_id)
            loaded = load_record(hit)
            kind = "TRUNCATED" if loaded["truncated"] else "OK"
            return _result("load", kind, {
                "id": hit["id"], "n_turns": len(loaded["turns"]),
                "source_sha": loaded["source_sha"], "schema": TRANSCRIPT,
            }, record={"head": loaded["head"], "n_turns": len(loaded["turns"])})
        dest = Path(out) if out else (var_dir() / "exports")
        rec = import_session(rec_id, dest, homes=homes if homes is not None else _homes_for(body))
        if action != "import":
            rec["verb"] = action
        return rec
    if action == "export":
        rec_id = str(body.get("id") or "")
        if not rec_id:
            raise PageError("NOT_FOUND", "id is required")
        dest = Path(body["out"]) if body.get("out") else (var_dir() / "exports")
        return export_md(rec_id, dest, homes=homes if homes is not None else _homes_for(body))
    if action == "index":
        out = Path(body["out"]) if body.get("out") else None
        return build_index(out, homes=homes if homes is not None else _homes_for(body))
    if action in ("recover", "crash-recover"):
        target = body.get("target") or body.get("path") or body.get("store")
        if not target:
            raise PageError("NO_STORE", "recover needs a target")
        target_path = Path(target)
        # A named bak is the only candidate. Otherwise recover walks siblings
        # and keeps the newest file that still checks out.
        bak = Path(body["bak"]) if body.get("bak") else None
        stage = Path(body["stage"]) if body.get("stage") else None
        flag = body.get("apply", False)
        if not isinstance(flag, bool):
            raise PageError("BAD_INPUT", "apply must be boolean")
        apply = flag
        rec = recover(target_path, bak, stage, apply=apply)
        if action == "crash-recover":
            rec["verb"] = "crash-recover"
        return rec
    if action == "resume":
        rec_id = str(body.get("id") or "")
        if not rec_id:
            raise PageError("NOT_FOUND", "id is required")
        return resume(rec_id, homes=homes if homes is not None else _homes_for(body),
                      launch=bool(body.get("launch")))
    if action == "diff":
        if not body.get("left") or not body.get("right"):
            raise PageError("NOT_FOUND", "diff needs left and right")
        return diff_files(Path(body["left"]), Path(body["right"]))
    if action == "check":
        what = str(body.get("what") or "catalog")
        path = body.get("path") or body.get("store")
        if not path:
            raise PageError("NO_STORE", "check needs a path")
        return check(what, Path(path), str(body.get("chair") or body.get("sit") or "ccr"))
    if action == "anonymize":
        rec_id = str(body.get("id") or "")
        if not rec_id:
            raise PageError("NOT_FOUND", "id is required")
        dest = Path(body["out"]) if body.get("out") or body.get("out_dir") else (var_dir() / "exports")
        if body.get("out_dir"):
            dest = Path(body["out_dir"])
        return anonymize(rec_id, dest, homes=homes if homes is not None else _homes_for(body))
    if action in ("strip", "strip_dry"):
        rec_id = str(body.get("id") or body.get("path") or "")
        if not rec_id:
            raise PageError("NOT_FOUND", "id is required")
        dest = Path(body["out"]) if body.get("out") else (var_dir() / "exports")
        return strip(rec_id, dest, homes=homes if homes is not None else _homes_for(body),
                     dry=(action == "strip_dry"))
    raise PageError("BAD_ACTION", action)


def _homes_for(body: dict) -> dict:
    if body.get("store"):
        return _store_homes(Path(body["store"]))
    return default_homes()
