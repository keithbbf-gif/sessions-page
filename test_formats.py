#!/usr/bin/env python3
"""Format-index checks. No network and no live home walk."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine
import formats

EXTRAS = (
    "claude-code-sessions",
    "claude-ai-indexeddb",
    "cosmos",
    "cosmos-code",
)
WIRED = (
    "agy",
    "antigravity",
    "antigravity-ide",
    "antigravity-cli",
)
KEYS = (
    "harness", "prefix", "title", "home", "header",
    "title_fields", "body", "load", "resume", "notes",
)
NOT_FORMATS = ("legal", "projects", "artifacts", "scheduled")


def main() -> int:
    assert isinstance(formats.CATALOG, tuple) and formats.CATALOG
    by_name = {}
    for row in formats.CATALOG:
        assert tuple(row) == KEYS
        for value in row.values():
            assert value is None or isinstance(value, str)
        assert row["load"] in ("measured", "unmeasured", "absent")
        assert isinstance(row["resume"], str) and row["resume"]
        name = row["harness"]
        assert name not in by_name
        by_name[name] = row
    for name in engine.HARNESSES:
        assert name in by_name
        assert by_name[name]["prefix"] == engine.PREFIX[name]
    prefixes = {row["prefix"] for row in formats.CATALOG}
    for value in engine.PREFIX.values():
        assert value in prefixes
    claude = by_name["claude"]
    assert claude["title_fields"] and "aiTitle" in claude["title_fields"]
    for banned in NOT_FORMATS:
        assert banned not in by_name
    for name in EXTRAS:
        assert name in by_name
        assert name not in engine.HARNESSES
        assert by_name[name]["load"] == "unmeasured"
    for name in WIRED:
        assert name in by_name
        assert name in engine.HARNESSES
    assert by_name["agy"]["load"] == "unmeasured"
    assert by_name["agy"]["home"] is None
    for name in ("antigravity", "antigravity-ide", "antigravity-cli"):
        assert by_name[name]["load"] == "measured"
    for name in ("factory", "windsurf", "augment"):
        assert by_name[name]["home"] is None
        assert by_name[name]["load"] == "absent"
        assert by_name[name]["resume"] == "UNMEASURED"
    assert by_name["cowork"]["resume"] == "OPENWORK_FOCUS"
    assert by_name["openwork"]["resume"] == "OPENWORK_FOCUS"
    assert by_name["cosmos"]["resume"] == "POINTER"
    assert by_name["cosmos-code"]["resume"] == "POINTER"
    assert "ev" in (by_name["cosmos-code"]["body"] or "")
    page = formats.catalog()
    assert page["schema"] == formats.SCHEMA == "cmsessions-format-index/1"
    assert page["n"] == len(page["formats"]) == len(formats.CATALOG)
    assert page["formats"][0] is not formats.CATALOG[0]
    json.dumps(page)
    print(f"ok {page['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
