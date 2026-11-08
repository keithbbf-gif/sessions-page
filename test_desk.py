#!/usr/bin/env python3
"""Hermetic desk checks. No Tk window and no socket."""
from __future__ import annotations

import ast
import importlib
import json
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

CLAUDE = "33333333-3333-3333-3333-333333333333"


def _import_desk():
    calls = []
    original = socket.socket.bind

    def trap(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)

    socket.socket.bind = trap
    try:
        sys.modules.pop("desk", None)
        module = importlib.import_module("desk")
        importlib.reload(module)
    finally:
        socket.socket.bind = original
    return module, calls


def _claude_hit() -> dict:
    return {
        "id": f"cc-{CLAUDE}",
        "harness": "claude",
        "vendor_id": CLAUDE,
        "path": r"V:\work\session.jsonl",
        "cwd": r"V:\work",
        "title": "hello",
        "aliases": {},
    }


def main() -> int:
    results = []

    def check(label, fn):
        try:
            results.append((label, bool(fn()), ""))
        except Exception as exc:  # noqa: BLE001
            results.append((label, False, f"{type(exc).__name__}: {exc}"))

    desk, binds = _import_desk()
    source = Path(desk.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    hit = _claude_hit()
    same = desk.plan_resume(hit, "claude")
    check("claude resume argv starts with claude and --resume",
          lambda: same["argv"][0] == "claude" and same["argv"][:2] == ["claude", "--resume"]
          and CLAUDE == same["argv"][2])

    foreign = desk.plan_resume(hit, "grok")
    foreign_argv = foreign.get("argv") or []
    check("claude hit on grok is NEED_LOAD without the claude uuid",
          lambda: foreign["kind"] == "NEED_LOAD"
          and foreign_argv[:1] == ["grok"]
          and "--resume" not in foreign_argv
          and CLAUDE not in foreign_argv
          and f"--resume={CLAUDE}" not in foreign_argv)

    owned = dict(hit)
    owned["aliases"] = {"grok_id": "grok-native-id"}
    crossed = desk.plan_resume(owned, "grok")
    check("a grok id on the hit uses grok --resume, not the claude uuid",
          lambda: crossed["kind"] == "OK"
          and crossed["argv"] == ["grok", "--resume", "grok-native-id"]
          and CLAUDE not in crossed["argv"])

    blank = desk.plan_resume(hit, "")
    check("an empty app defaults to the hit harness",
          lambda: blank["argv"][:2] == ["claude", "--resume"])

    openwork = {
        "id": "ow-ses_native",
        "harness": "openwork",
        "vendor_id": "ses_native",
        "path": r"V:\work\opencode.db",
        "aliases": {},
    }
    focused = desk.plan_resume(openwork, "openwork")
    check("openwork resume is OPENWORK_FOCUS",
          lambda: focused["kind"] == "OPENWORK_FOCUS" and focused["argv"] == []
          and focused["launched"] is False)

    cowork = {
        "id": "cow-ok1",
        "harness": "cowork",
        "vendor_id": "ok1",
        "path": r"V:\work\ok.md",
        "aliases": {"opencode_id": "ses_cow_002"},
    }
    check("cowork resume is OPENWORK_FOCUS and does not spawn",
          lambda: desk.plan_resume(cowork, "cowork")["kind"] == "OPENWORK_FOCUS"
          and desk.plan_resume(cowork, "openwork")["argv"] == []
          and desk.plan_resume(cowork, "openwork")["opencode_id"] == "ses_cow_002")

    other = desk.plan_resume(hit, "openwork")
    check("a claude id is not focused as OpenWork",
          lambda: other["kind"] == "NEED_LOAD" and other["argv"] == [] and "opencode_id" not in other)

    cursor = {"id": "cur-abc", "harness": "cursor", "vendor_id": "abc", "path": r"V:\work\c.jsonl"}
    check("cursor resume matches agent --resume",
          lambda: desk.plan_resume(cursor, "cursor")["argv"] == ["agent", "--resume", "abc"]
          and desk.plan_resume(cursor, "agent")["kind"] == "OK")

    cline = {
        "id": "cln-m",
        "harness": "cline",
        "vendor_id": "m1",
        "path": r"V:\work\task.messages.json",
    }
    check("cline --id is only for a messages file",
          lambda: desk.plan_resume(cline, "cline")["argv"] == ["cline", "--id", "m1"]
          and desk.plan_resume(dict(cline, path=r"V:\work\other.json"), "cline")["kind"] == "UNMEASURED")

    check("an unknown app is UNMEASURED",
          lambda: desk.plan_resume(hit, "notepad")["kind"] == "UNMEASURED"
          and desk.plan_resume(hit, "notepad")["argv"] is None)

    loaded = desk.plan_load(hit)
    check("load names the action and id and does not modify the source",
          lambda: loaded["action"] == "load" and loaded["id"] == hit["id"]
          and loaded["path"] == hit["path"] and loaded["modify_source"] is False)
    check("load plan has no write flag",
          lambda: "write" not in loaded and not any("write" in str(key).lower() for key in loaded)
          and not any(str(key).lower() in {"apply", "overwrite", "out", "dest"} for key in loaded))

    check("importing desk binds nothing", lambda: binds == [])
    check("desk has no ThreadingHTTPServer reference",
          lambda: "ThreadingHTTPServer" not in source and not hasattr(desk, "ThreadingHTTPServer")
          and "http.server" not in source)

    def _imports_at_module(tree):
        banned = {"tkinter", "http.server", "socket", "webbrowser"}
        for node in tree.body:
            if isinstance(node, ast.Import):
                if any(alias.name.split(".")[0] in banned or alias.name in banned for alias in node.names):
                    return True
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod.split(".")[0] in banned or mod in banned:
                    return True
        return False

    check("tkinter is not imported at module level", lambda: not _imports_at_module(tree))
    check("plan json for a foreign app does not stuff the uuid into --resume",
          lambda: f"--resume\", \"{CLAUDE}" not in json.dumps(foreign)
          and f"--resume={CLAUDE}" not in json.dumps(foreign))

    handoff = desk.plan_foreign_launch(hit, "grok")
    check("plan_foreign_launch of a claude hit onto grok is HANDOFF",
          lambda: handoff["kind"] == "HANDOFF" and handoff["export"] is True
          and handoff["writes_vendor"] is False and handoff["argv"] == ["grok"])

    own_launch = desk.plan_foreign_launch(hit, "claude")
    own_plan = desk.plan_resume(hit, "claude")
    check("plan_foreign_launch of a claude hit onto claude is not HANDOFF",
          lambda: own_launch["kind"] != "HANDOFF" and own_launch["kind"] == own_plan["kind"]
          and own_launch["argv"] == own_plan["argv"])

    check("plan_foreign_launch of openwork is OPENWORK_FOCUS",
          lambda: desk.plan_foreign_launch(openwork, "openwork")["kind"] == "OPENWORK_FOCUS")

    check("instance_name is Local\\cmSessionsDesk",
          lambda: desk.instance_name() == "Local\\cmSessionsDesk")

    def _module_calls(names):
        found = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                if isinstance(func, ast.Name):
                    found.append(func.id)
                elif isinstance(func, ast.Attribute):
                    found.append(func.attr)
        return any(name in found for name in names)

    check("claim_instance is not called by import",
          lambda: callable(desk.claim_instance)
          and not _module_calls(("claim_instance", "CreateMutexW")))

    failed = [label for label, ok, _detail in results if not ok]
    for label, ok, detail in results:
        print(("ok  " if ok else "FAIL") + " " + label + (f" — {detail}" if detail else ""))
    print(f"{len(results) - len(failed)}/{len(results)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
