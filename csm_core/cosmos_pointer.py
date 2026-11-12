"""Thin pointers to the COSMOS proper seed.

A pointer names sid, closed_epoch, tree_id, and the fixed seed path.
The schema name is cosmos-session-seed/1. There is no cwd. This module
does not read or write the live tree and does not spawn.

Boundary: no second Core, no live\\ writes, no CCR.lease. Standalone if
Cosmos is absent.

Kit: V:\\A\\Ai\\COSMOS\\cosmos\\cosmos_session_tools_kit.py loads
builds/sessions-page/engine.py via importlib.util.spec_from_file_location.
"""

from __future__ import annotations

import math

SCHEMA = "cosmos-session-seed/1"
SEED_PATH = "V:\\a\\ai\\COSMOS\\live\\state\\SEED.json"


class PointerError(RuntimeError):
    """kind in {BAD_POINTER, BAD_SCHEMA}."""

    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        super().__init__(detail or kind)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PointerError("BAD_POINTER", f"{name} is required")
    return value.strip()


def _epoch(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PointerError("BAD_POINTER", "closed_epoch must be a number")
    if not math.isfinite(float(value)):
        raise PointerError("BAD_POINTER", "closed_epoch must be finite")
    return value


def _schema(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, str) or value.strip() != SCHEMA:
        raise PointerError("BAD_SCHEMA", "schema must be cosmos-session-seed/1")


def pointer(sid: str, closed_epoch: int | float, tree_id: str) -> dict:
    """One thin pointer. The seed path is a name only and is not opened."""
    return {
        "schema": SCHEMA,
        "sid": _text(sid, "sid"),
        "closed_epoch": _epoch(closed_epoch),
        "tree_id": _text(tree_id, "tree_id"),
        "path": SEED_PATH,
    }


def inherit(tree_id: str, closed_epoch: int | float) -> dict:
    """Proper empty close. sid is inherit. Still no cwd."""
    return pointer("inherit", closed_epoch, tree_id)


def from_record(record: dict) -> dict:
    """Copy sid, closed_epoch, and tree_id. cwd and any other key are dropped."""
    if not isinstance(record, dict):
        raise PointerError("BAD_POINTER", "record must be an object")
    _schema(record.get("schema"))
    return pointer(record.get("sid"), record.get("closed_epoch"), record.get("tree_id"))
