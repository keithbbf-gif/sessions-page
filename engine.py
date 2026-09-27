#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sessions-page engine. Stdlib only. No Core, no ledger, no live-tree write.

Find, import, export, index, recover, and resume across the harnesses that
keep a local session store. Legal transcripts are counted and not opened.
Crash recovery replaces a file from a verified backup after staging the
original. It does not repair sqlite or JSONL in place.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

SCHEMA = "cosmos-session-tools-result/1"
TRANSCRIPT = "cosmos-transcript/1"
INDEX_SCHEMA = "sessions-page-index/1"
MAX_BYTES = 48 * 1024 * 1024
HEAD_BYTES = 8192
DEFAULT_LIMIT = 200

VERBS = (
    "find", "import", "export", "index", "recover", "resume",
    "scan", "load", "convert", "diff", "check", "anonymize",
    "crash-recover", "strip", "strip_dry", "doi",
)

HARNESSES = (
    "grok", "claude", "codex", "cursor", "cowork", "openwork",
    "claude_desktop", "gemini",
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
}


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


def default_homes() -> dict[str, Path | None]:
    """Bound locations only. A missing directory stays None — never a guessed volume."""
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
    gemini = Path(os.environ["GEMINI_SESSIONS"]) if os.environ.get("GEMINI_SESSIONS") else None
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
        "gemini": gemini,
        "cowork": cowork,
        "openwork": openwork,
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
    try:
        summaries = root.rglob("summary.json")
    except OSError:
        return []
    for summary in summaries:
        folder = summary.parent
        hist = folder / "chat_history.jsonl"
        if not hist.is_file():
            continue
        try:
            info = json.loads(summary.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            info = {}
        inner = info.get("info") if isinstance(info.get("info"), dict) else info
        vid = str(inner.get("id") or folder.name)
        cwd = str(inner.get("cwd") or "")
        title = str(inner.get("generated_title") or inner.get("title") or "")
        hits.append(_hit(
            harness="grok", vendor_id=vid, path=hist, cwd=cwd, title=title,
            updated=_mtime(hist), nbytes=hist.stat().st_size,
        ))
    return hits


def _consume_claude_dir(project: Path, hits: list[dict]) -> None:
    try:
        files = list(project.iterdir())
    except OSError:
        return
    for path in files:
        if not path.is_file() or path.suffix != ".jsonl" or path.is_symlink():
            continue
        if not _UUID.fullmatch(path.stem):
            continue
        cwd, title = _sniff(path)
        hits.append(_hit(
            harness="claude", vendor_id=path.stem, path=path, cwd=cwd, title=title,
            updated=_mtime(path), nbytes=path.stat().st_size,
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
        con = sqlite3.connect(uri, uri=True)
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
        con = sqlite3.connect(uri, uri=True)
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
        con = sqlite3.connect(uri, uri=True)
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


def _walk(homes: dict) -> list[dict]:
    hits: list[dict] = []
    mapping = (
        ("grok", _enum_grok),
        ("claude", _enum_claude),
        ("codex", _enum_codex),
        ("cursor", _enum_cursor),
        ("cowork", _enum_cowork),
        ("openwork", _enum_openwork),
    )
    for name, fn in mapping:
        path = homes.get(name)
        if path is None:
            continue
        try:
            present = path.exists()
        except OSError:
            continue
        if not present:
            continue
        hits.extend(fn(path))
    desktop = homes.get("claude_desktop")
    if desktop is not None and desktop.exists():
        hits.extend(_enum_loose_jsonl("claude_desktop", desktop))
    gemini = homes.get("gemini")
    if gemini is not None and gemini.exists():
        hits.extend(_enum_loose_jsonl("gemini", gemini))
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
        cwd, title = _sniff(path, 2048)
        if cwd and not row.get("cwd"):
            row["cwd"] = cwd
        if title:
            row["title"] = title
        if is_legal(str(path), row.get("stream") or "", row.get("cwd") or "", row.get("title") or ""):
            row["legal"] = True
            row["title"] = ""
            row["cwd"] = ""


def find(homes: dict | None = None, query: str = "", harness: str = "",
         cwd: str = "", limit: int = DEFAULT_LIMIT, enrich: bool = True) -> dict:
    homes = homes if homes is not None else default_homes()
    rows = [h for h in _walk(homes) if _match(h, query, harness, cwd)]
    rows.sort(key=lambda h: (-(h.get("updated") or 0), h["id"]))
    shown = rows[: max(0, int(limit))]
    if enrich:
        _enrich(shown)
    n_legal = sum(1 for h in rows if h["legal"])
    families = []
    for name in HARNESSES:
        group = [h for h in rows if h["harness"] == name]
        path = homes.get(name)
        present = bool(path and path.exists())
        families.append({
            "family": name,
            "status": "OK" if present else "ABSENT",
            "path": str(path) if path and present else None,
            "n": len(group) if present else None,
            "n_legal": sum(1 for h in group if h["legal"]) if present else 0,
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
    return turns


def _turns_cowork(hit: dict) -> tuple[list[dict], bool]:
    if hit["legal"]:
        raise PageError("LEGAL_OMITTED", hit["id"])
    path = Path(hit["path"])
    if not path.is_file() or path.suffix.lower() not in (".md", ".txt", ".jsonl"):
        return [], False
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
        con = sqlite3.connect(uri, uri=True)
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


def load_record(hit: dict) -> dict:
    if hit["legal"]:
        raise PageError("LEGAL_OMITTED", hit["id"])
    path = Path(hit["path"])
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


def import_session(rec_id: str, out_dir: Path, homes: dict | None = None) -> dict:
    homes = homes if homes is not None else default_homes()
    hit = _by_id(homes, rec_id)
    before = sha256_bytes(Path(hit["path"]).read_bytes()) if Path(hit["path"]).is_file() else ""
    loaded = load_record(hit)
    payload = encode_transcript(loaded["head"], loaded["turns"])
    written = write_pair(out_dir, hit["id"], payload, loaded["source_sha"], len(loaded["turns"]))
    after = sha256_bytes(Path(hit["path"]).read_bytes()) if Path(hit["path"]).is_file() and before else before
    if before and after != before:
        raise PageError("FIDELITY_MISMATCH", "source changed during import")
    kind = "TRUNCATED" if loaded["truncated"] else "OK"
    return _result("import", kind, {
        "id": hit["id"], "n_turns": len(loaded["turns"]),
        "source_sha": loaded["source_sha"], "out_sha": written["sha"],
    }, written=written, original_untouched=True)


def export_md(rec_id: str, out_dir: Path, homes: dict | None = None) -> dict:
    homes = homes if homes is not None else default_homes()
    hit = _by_id(homes, rec_id)
    source = Path(hit["path"])
    before = sha256_bytes(source.read_bytes()) if source.is_file() else ""
    loaded = load_record(hit)
    lines = [f"# {loaded['head'].get('title') or hit['id']}", "",
             f"harness: {hit['harness']}", f"id: {hit['id']}", ""]
    for turn in loaded["turns"]:
        lines.append(f"## [{turn['seq']}] {turn['role']}")
        lines.append(turn.get("text") or "")
        lines.append("")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{hit['id']}.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    after = sha256_bytes(source.read_bytes()) if source.is_file() and before else before
    if before and after != before:
        raise PageError("FIDELITY_MISMATCH", "source changed during export")
    return _result("export", "OK", {
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


def _jsonl_ok(path: Path) -> bool:
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    if not raw:
        return True
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return False
    # a trailing partial line without newline still fails json.loads above
    return True


def _swap_in(incoming: Path, target: Path) -> None:
    """Replace target with incoming. Windows can deny the rename while a
    scanner holds the destination; the verified bytes are then written over it.
    """
    try:
        os.replace(incoming, target)
        return
    except PermissionError:
        data = incoming.read_bytes()
        target.write_bytes(data)
        incoming.unlink(missing_ok=True)


def _sqlite_ok(path: Path) -> tuple[bool, str]:
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        integ = con.execute("PRAGMA integrity_check").fetchone()[0]
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        con.close()
    except sqlite3.Error as exc:
        return False, str(exc)
    if integ != "ok" or fk:
        return False, f"integrity={integ} fk={len(fk)}"
    return True, "ok"


def recover(target: Path, bak: Path | None = None, stage: Path | None = None,
            apply: bool = False) -> dict:
    """Check, then replace from a verified bak. Never edits the broken bytes in place."""
    if not target.exists():
        raise PageError("NO_STORE", str(target))
    suffix = target.suffix.lower()
    sqlite_target = suffix in (".db", ".sqlite")
    if sqlite_target:
        ok, detail = _sqlite_ok(target)
    elif suffix == ".jsonl":
        ok, detail = _jsonl_ok(target), "jsonl"
    else:
        raise PageError("UNMEASURED", suffix or target.name)
    if ok:
        return _result("recover", "ALREADY_OK", {"target": str(target), "detail": detail})
    if bak is None:
        bak = nearest_bak(target)
    if bak is None or not bak.is_file():
        return _result("recover", "NO_BAK", {"target": str(target), "detail": detail})
    if sqlite_target:
        bak_ok, bak_detail = _sqlite_ok(bak)
    else:
        bak_ok, bak_detail = _jsonl_ok(bak), "jsonl"
    if not bak_ok:
        raise PageError("BAD_BAK", bak_detail)
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
    incoming = target.with_name(target.name + ".restore")
    shutil.copy2(bak, incoming)
    restored = sha256_bytes(incoming.read_bytes())
    if restored != bak_sha:
        incoming.unlink(missing_ok=True)
        raise PageError("RESTORE_FAILED", str(target))
    _swap_in(incoming, target)
    if sqlite_target:
        again, again_detail = _sqlite_ok(target)
    else:
        again, again_detail = _jsonl_ok(target), "jsonl"
    if not again:
        back = target.with_name(target.name + ".restore")
        shutil.copy2(staged, back)
        _swap_in(back, target)
        raise PageError("RESTORE_FAILED", again_detail)
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
    hit = _by_id(homes, rec_id)
    if hit["legal"]:
        raise PageError("LEGAL_OMITTED", hit["id"])
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
    hit = _by_id(homes, rec_id)
    source = Path(hit["path"])
    before = sha256_bytes(source.read_bytes()) if source.is_file() else ""
    loaded = load_record(hit)
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
    after = sha256_bytes(source.read_bytes()) if source.is_file() and before else before
    if before and after != before:
        raise PageError("FIDELITY_MISMATCH", "original changed")
    return _result("anonymize", "OK", {
        "n_redactions": n, "source_sha": before, "out_sha": written["sha"], "id": hit["id"],
    }, written=written, original_untouched=True)


def strip(rec_id: str, out_dir: Path | None, homes: dict | None = None, dry: bool = False) -> dict:
    homes = homes if homes is not None else default_homes()
    hit = _by_id(homes, rec_id)
    if hit["legal"]:
        raise PageError("LEGAL_OMITTED", hit["id"])
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
    if dry:
        return _result("strip_dry", "OK", gate)
    if out_dir is None:
        raise PageError("NO_OUTDIR", "strip needs an output directory")
    payload = encode_transcript(loaded["head"], kept)
    written = write_pair(out_dir, hit["id"] + ".strip", payload, loaded["source_sha"], len(kept))
    gate["out_sha"] = written["sha"]
    return _result("strip", "OK", gate, written=written, original_untouched=True)


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


def nearest_bak(target: Path) -> Path | None:
    """A sibling backup only. Never a volume-wide search."""
    try:
        children = list(target.parent.iterdir())
    except OSError:
        return None
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
    if action == "find":
        return find(
            homes=homes, query=str(body.get("query") or body.get("q") or ""),
            harness=str(body.get("harness") or body.get("family") or ""),
            cwd=str(body.get("cwd") or ""),
            limit=int(body.get("limit") or DEFAULT_LIMIT),
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
        bak = Path(body["bak"]) if body.get("bak") else nearest_bak(target_path)
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
