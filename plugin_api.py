#!/usr/bin/env python3
"""In-process sessions plug. Cosmos calls this. No port.

snapshot() reads presence and verbs. call() runs one verb.
formats() reads formats.catalog when that module exists.

This module does not bind a socket and does not spawn OpenWork.exe or grok.exe.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCHEMA = "cmsessions-plugin/1"
_ENGINE_FILE = Path(__file__).resolve().parent / "engine.py"
_KIT_FILE = Path(__file__).resolve().parents[2] / "cosmos" / "cosmos_session_tools_kit.py"

_KIT = None
_KIT_LOOKED = False
_ENG = None


class PluginError(RuntimeError):
    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        super().__init__(detail or kind)


def _load_file(path: Path, name: str):
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


def _kit():
    """Kit on the Cosmos path, else the sibling file. None if neither loads."""
    global _KIT, _KIT_LOOKED
    if _KIT_LOOKED:
        return _KIT
    _KIT_LOOKED = True
    try:
        import cosmos_session_tools_kit as kit
    except ImportError:
        kit = _load_file(_KIT_FILE, "cosmos_session_tools_kit")
    _KIT = kit
    return kit


def _engine():
    global _ENG
    if _ENG is not None:
        return _ENG
    mod = _load_file(_ENGINE_FILE, "sessions_page_engine_direct")
    if mod is None:
        raise PluginError("ENGINE_MISSING", "builds/sessions-page/engine.py")
    _ENG = mod
    return mod


def _stamp(rec: dict) -> dict:
    out = dict(rec)
    out["schema"] = SCHEMA
    out["port"] = None
    out["window"] = "desk"
    if out.get("kind") == "OK":
        out["engine"] = "builds/sessions-page"
    return out


def snapshot() -> dict:
    """Presence and the verb list. Does not read transcript bodies or mkdir."""
    kit = _kit()
    if kit is not None:
        rec = kit.snapshot()
        if isinstance(rec, dict):
            return _stamp(rec)
    eng = _engine()
    return _stamp({
        "kind": "OK",
        "verbs": list(eng.VERBS),
        "homes": eng.home_status(),
    })


def call(body: dict, homes=None) -> dict:
    """Forward one verb. action or verb is required. Refusals stay raised."""
    if not isinstance(body, dict):
        raise PluginError("BAD_REQUEST", "body must be an object")
    action = str(body.get("action") or body.get("verb") or "").strip()
    if not action:
        raise PluginError("BAD_ACTION", "action or verb is required")
    kit = _kit()
    if kit is not None:
        return kit.run(body, homes=homes)
    return _engine().dispatch(action, body, homes=homes)


def formats() -> dict:
    """Lazy formats.catalog(). A missing module is UNMEASURED."""
    try:
        import formats as formats_mod
        rec = formats_mod.catalog()
    except ImportError:
        return {"schema": SCHEMA, "kind": "UNMEASURED"}
    if isinstance(rec, dict):
        return rec
    return {"schema": SCHEMA, "kind": "OK", "catalog": rec}
