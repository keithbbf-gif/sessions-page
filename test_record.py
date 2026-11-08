#!/usr/bin/env python3
"""Hermetic checks for the shared session record. Temp homes only. No live profile."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
import record  # noqa: E402

GROK = "11111111-1111-1111-1111-111111111111"
CLAUDE = "22222222-2222-2222-2222-222222222222"
FIELDS = (
    "id", "vendor", "model", "harness", "project", "title",
    "started", "last_activity", "duration", "status", "tokens",
    "parent", "paths", "location", "tags", "favorite",
)
BODY = "assistant body stays out of the record"


def _homes(root: Path) -> dict:
    homes = {name: None for name in engine.HARNESSES}
    homes["grok"] = root / "grok"
    homes["claude"] = root / "claude" / "projects"
    return homes


def _fixture(root: Path) -> None:
    grok = root / "grok" / "alpha" / GROK
    grok.mkdir(parents=True)
    (grok / "summary.json").write_text(json.dumps({
        "info": {
            "id": GROK,
            "cwd": r"C:\fixture\alpha",
            "generated_title": "grok title",
        },
    }), encoding="utf-8")
    hist = grok / "chat_history.jsonl"
    hist.write_text(
        '{"type":"user","text":"hello grok"}\n'
        '{"type":"assistant","text":"' + BODY + '"}\n',
        encoding="utf-8",
    )
    os.utime(hist, (1_700_000_100, 1_700_000_100))

    work = root / "claude" / "projects" / "C--fixture-beta"
    work.mkdir(parents=True)
    path = work / f"{CLAUDE}.jsonl"
    lines = [
        {
            "type": "user",
            "cwd": r"C:\fixture\beta",
            "message": {"role": "user", "content": [{"type": "text", "text": "hello claude"}]},
        },
        {"type": "ai-title", "aiTitle": "claude title"},
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": BODY}]},
        },
    ]
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    os.utime(path, (1_700_000_000, 1_700_000_000))


def _by_vendor(rows: list[dict]) -> dict[str, dict]:
    return {row["vendor"]: row for row in rows}


def main() -> int:
    results = []

    def check(label, fn):
        try:
            results.append((label, bool(fn()), ""))
        except Exception as exc:  # noqa: BLE001
            results.append((label, False, f"{type(exc).__name__}: {exc}"))

    check("schema is the shared record",
          lambda: record.SCHEMA == "cmsessions-record/1")
    check("vendor map folds harnesses and leaves the rest other",
          lambda: record.vendor_of("claude") == "claude"
          and record.vendor_of("claude_desktop") == "claude"
          and record.vendor_of("codex") == "codex"
          and record.vendor_of("grok") == "grok"
          and record.vendor_of("gemini") == "gemini"
          and record.vendor_of("antigravity") == "antigravity"
          and record.vendor_of("antigravity-ide") == "antigravity"
          and record.vendor_of("antigravity-cli") == "antigravity"
          and record.vendor_of("agy") == "antigravity"
          and record.vendor_of("cursor") == "other"
          and record.vendor_of("nope") == "other")

    with tempfile.TemporaryDirectory(prefix="sesspage_rec_") as tmp:
        root = Path(tmp)
        _fixture(root)
        found = engine.find(homes=_homes(root), limit=50)
        hits = found["hits"]
        rows = record.records_from_hits(hits)
        by_vendor = _by_vendor(rows)
        claude = by_vendor.get("claude")
        grok = by_vendor.get("grok")

        check("find on the temp homes returns claude and grok",
              lambda: found["kind"] == "OK" and claude is not None and grok is not None
              and {row["vendor"] for row in rows} == {"claude", "grok"})
        check("those hits become claude and grok records",
              lambda: claude["harness"] == "claude" and grok["harness"] == "grok"
              and claude["title"] == "claude title" and grok["title"] == "grok title"
              and claude["project"] == "beta" and grok["project"] == "alpha"
              and claude["id"] == f"cc-{CLAUDE}" and grok["id"] == f"grok-{GROK}"
              and claude["status"] == "idle" and grok["status"] == "idle"
              and claude["model"] is None and grok["model"] is None
              and claude["duration"] is None and grok["tokens"] is None
              and claude["favorite"] is False and grok["tags"] == []
              and claude["paths"] == [] and grok["parent"] is None
              and claude["location"] and grok["location"])
        check("a record has the shared fields and no transcript",
              lambda: all(tuple(row) == FIELDS for row in rows)
              and all("transcript" not in row for row in rows)
              and all(BODY not in json.dumps(row) for row in rows))

        both = record.filter_records(rows, vendors=["claude", "grok"])
        only = record.filter_records(rows, vendors=["claude"])
        check("vendor multi-select interleaves claude and grok by activity",
              lambda: [row["vendor"] for row in both] == ["grok", "claude"]
              and [row["vendor"] for row in only] == ["claude"]
              and len(record.filter_records(rows, vendors=[])) == 2)

        bare_hits = [
            {"id": "bare-1", "harness": "codex", "cwd": r"C:\fixture\gamma", "updated": 10},
            "not-a-dict",
            None,
            5,
            {"harness": "gemini", "title": "kept", "transcript": BODY, "messages": [BODY]},
        ]
        bare = record.records_from_hits(bare_hits)
        check("a hit missing a title still makes a record",
              lambda: len(bare) == 2 and bare[0]["id"] == "bare-1"
              and bare[0]["title"] is None and bare[0]["vendor"] == "codex"
              and bare[0]["project"] == "gamma" and bare[0]["status"] == "idle")
        check("a non-dict hit is skipped and transcript text is not copied",
              lambda: bare[1]["vendor"] == "gemini" and bare[1]["title"] == "kept"
              and "transcript" not in bare[1] and BODY not in json.dumps(bare))

        rich = record.to_record({
            "id": "rich-1",
            "harness": "antigravity-cli",
            "cwd": r"C:\fixture\delta",
            "title": "rich title",
            "path": r"C:\fixture\delta\session.json",
            "updated": 1_700_000_050,
            "started": 1_700_000_000,
            "current_model_id": "model-a",
            "status": "in_progress",
            "tokens": 42,
            "parent_id": "parent-1",
            "paths": [r"C:\fixture\delta\main.py", ""],
            "tags": ["handoff"],
            "favorite": True,
            "transcript": BODY,
        })
        legal = record.to_record({
            "id": "leg-1",
            "harness": "claude",
            "legal": True,
            "status": "RUNNING",
            "title": "",
        })
        crashed = record.to_record({
            "id": "wreck-1",
            "harness": "cursor",
            "title": "wreck",
            "status": "crashed",
            "updated": 1_700_000_040,
            "path": r"C:\fixture\wreck\session.json",
        })
        untimed = record.to_record({
            "id": "untimed",
            "harness": "gemini",
            "title": "untimed",
        })
        check("status, tokens, and parent stay inside the record",
              lambda: record.status_of({}) == "idle"
              and record.status_of({"status": "PRESENT"}) == "idle"
              and rich["vendor"] == "antigravity" and rich["status"] == "active"
              and rich["model"] == "model-a" and rich["tokens"] == 42
              and rich["parent"] == "parent-1" and rich["started"] == 1_700_000_000
              and rich["paths"] == [r"C:\fixture\delta\main.py"]
              and rich["tags"] == ["handoff"] and rich["favorite"] is True
              and rich["duration"] is None and rich["project"] == "delta"
              and "transcript" not in rich and BODY not in json.dumps(rich)
              and legal["status"] == "finished" and legal["title"] is None
              and crashed["vendor"] == "other" and crashed["status"] == "crashed"
              and untimed["last_activity"] is None)
        mixed = [untimed, crashed, claude, grok]
        shown = record.filter_records(mixed, query="TITLE")
        check("crashed rows stay and unknown times sort last",
              lambda: [row["id"] for row in record.filter_records(mixed)]
              == [grok["id"], crashed["id"], claude["id"], "untimed"]
              and [row["id"] for row in record.filter_records(mixed, status="crashed")]
              == ["wreck-1"]
              and [row["vendor"] for row in shown] == ["grok", "claude"]
              and record.filter_records(mixed, vendors=["claude"], query="wreck") == [])

    failed = [label for label, ok, _detail in results if not ok]
    for label, ok, detail in results:
        print(("ok  " if ok else "FAIL") + " " + label + (f" — {detail}" if detail else ""))
    print(f"{len(results) - len(failed)}/{len(results)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
