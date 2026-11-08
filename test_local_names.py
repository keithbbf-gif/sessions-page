#!/usr/bin/env python3
"""Hermetic checks for local automatic names. Temp files only. No live profile."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine

PROBE = "11111111-1111-1111-1111-111111111111"
KEPT = "22222222-2222-2222-2222-222222222222"
ROOT_ID = "33333333-3333-3333-3333-333333333333"
NAMED = "44444444-4444-4444-4444-444444444444"
LEGAL = "55555555-5555-5555-5555-555555555555"
SESSION = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    results = []

    def check(label, fn):
        try:
            results.append((label, bool(fn()), ""))
        except Exception as exc:  # noqa: BLE001
            results.append((label, False, f"{type(exc).__name__}: {exc}"))

    with tempfile.TemporaryDirectory(prefix="sesspage_names_") as tmp:
        tmp_path = Path(tmp)

        named = tmp_path / "named.jsonl"
        user = "plan the fence and then " + ("keep going " * 400)
        _jsonl(named, [
            {"type": "user", "cwd": r"V:\work", "message": {"role": "user", "content": user}},
            {"type": "ai-title", "aiTitle": "Fence plan", "sessionId": SESSION},
        ])
        raw = named.read_bytes()
        hit = {
            "harness": "claude",
            "title": "",
            "cwd": "",
            "path": str(named),
            "stream": "",
            "legal": False,
        }
        engine._enrich([hit])
        check("aiTitle wins over a long first user line",
              lambda: hit["title"] == "Fence plan" and hit["cwd"] == r"V:\work"
              and 2048 < raw.find(b"aiTitle") < engine.HEAD_BYTES)

        projects = tmp_path / "projects"
        probe = projects / "C--Users-Papa-AppData-Local-Temp-claude-probe--abc"
        keep = projects / "V--A-Ai-COSMOS"
        probe.mkdir(parents=True)
        keep.mkdir()
        _jsonl(probe / f"{PROBE}.jsonl", [{"type": "user", "message": {"content": "probe"}}])
        _jsonl(keep / f"{KEPT}.jsonl", [{"type": "user", "message": {"content": "kept"}}])
        _jsonl(projects / f"{ROOT_ID}.jsonl", [{"type": "user", "message": {"content": "root"}}])
        found = engine._enum_claude(projects)
        ids = {row["vendor_id"] for row in found}
        check("claude-probe projects are omitted and other projects stay",
              lambda: PROBE not in ids and KEPT in ids and ROOT_ID in ids)

        home = tmp_path / "index-home"
        good = home / "V--work"
        legal = home / "P-Legal"
        good.mkdir(parents=True)
        legal.mkdir()
        _jsonl(good / f"{NAMED}.jsonl", [
            {"type": "user", "message": {"role": "user", "content": "hello"}},
            {"type": "ai-title", "aiTitle": "Fence plan", "sessionId": NAMED},
        ])
        _jsonl(legal / f"{LEGAL}.jsonl", [
            {"type": "ai-title", "aiTitle": "Sealed matter", "sessionId": LEGAL},
            {"type": "user", "cwd": r"P:\Legal\case", "message": {"role": "user", "content": "secret case"}},
        ])
        homes = {name: None for name in engine.HARNESSES}
        homes["claude"] = home
        out = tmp_path / "index.jsonl"
        engine.build_index(out, homes=homes)
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        by_id = {row["vendor_id"]: row for row in rows}
        text = out.read_text(encoding="utf-8")
        check("index stores the local name and blanks a legal title",
              lambda: by_id[NAMED]["title"] == "Fence plan" and by_id[NAMED]["legal"] is False
              and by_id[LEGAL]["title"] == "" and by_id[LEGAL]["cwd"] == ""
              and by_id[LEGAL]["legal"] is True and "Sealed matter" not in text
              and "secret case" not in text)

    def formats_ok():
        try:
            rec = engine.dispatch("formats", {})
        except engine.PageError as exc:
            return exc.kind == "UNMEASURED"
        return rec.get("verb") == "formats" and rec.get("kind") == "OK" and "gate" in rec

    check("formats is measured or still unmeasured",
          lambda: "formats" in engine.VERBS and formats_ok())

    failed = [label for label, ok, _detail in results if not ok]
    for label, ok, detail in results:
        print(("ok  " if ok else "FAIL") + " " + label + (f" — {detail}" if detail else ""))
    print(f"{len(results) - len(failed)}/{len(results)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
