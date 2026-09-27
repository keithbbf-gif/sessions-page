#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermetic checks for the sessions-page engine. No live profile walk."""
from __future__ import annotations

import json
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
import sessions_page  # noqa: E402

UUID = "22222222-2222-2222-2222-222222222222"
CLAUDE = "33333333-3333-3333-3333-333333333333"
CODEX = "44444444-4444-4444-4444-444444444444"
CURSOR = "55555555-5555-5555-5555-555555555555"


def _homes(root: Path) -> dict:
    homes = {name: None for name in engine.HARNESSES}
    homes["grok"] = root / "grok"
    homes["claude"] = root / "claude" / "projects"
    homes["codex"] = root / "codex"
    homes["cursor"] = root / "cursor"
    homes["cowork"] = root / "cowork"
    homes["openwork"] = root / "opencode.db"
    homes["claude_desktop"] = root / "desktop"
    homes["gemini"] = None
    return homes


def _fixture(root: Path) -> None:
    grok = root / "grok" / "Vwork" / UUID
    grok.mkdir(parents=True)
    (grok / "summary.json").write_text(json.dumps({
        "info": {"id": UUID, "cwd": r"V:\work", "generated_title": "grok title",
                 "current_model_id": "grok-test"}
    }), encoding="utf-8")
    (grok / "chat_history.jsonl").write_text(
        '{"type":"user","text":"hello grok"}\n{"type":"assistant","text":"hi"}\n',
        encoding="utf-8")

    legal = root / "claude" / "projects" / "P-Legal" 
    legal.mkdir(parents=True)
    (legal / f"{CLAUDE}.jsonl").write_text(
        '{"type":"user","cwd":"P:\\\\Legal\\\\case","message":{"role":"user","content":"secret case"}}\n',
        encoding="utf-8")
    work = root / "claude" / "projects" / "V-work"
    work.mkdir()
    (work / f"{CLAUDE[:-1]}a.jsonl").write_text(
        '{"type":"user","cwd":"V:\\\\work","message":{"role":"user","content":[{"type":"text","text":"hello claude"}]}}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"ok"}]}}\n',
        encoding="utf-8")

    codex = root / "codex" / "sessions" / "2026"
    codex.mkdir(parents=True)
    (codex / f"rollout-2026-09-01T00-00-00-{CODEX}.jsonl").write_text(
        json.dumps({"type": "session_meta", "payload": {"id": CODEX, "cwd": r"V:\work", "source": "cli"}}) + "\n"
        + json.dumps({"type": "response_item", "payload": {"role": "user", "content": [{"type": "input_text", "text": "hello codex"}]}}) + "\n",
        encoding="utf-8")

    cur = root / "cursor" / "chats" / "abc" / CURSOR
    cur.mkdir(parents=True)
    (cur / "meta.json").write_text(json.dumps({"cwd": r"V:\work", "title": "cursor title"}), encoding="utf-8")
    transcript = root / "cursor" / "projects" / "ws" / "agent-transcripts" / CURSOR / f"{CURSOR}.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        '{"type":"user","message":{"content":"from cursor transcript"}}\n',
        encoding="utf-8")

    cow = root / "cowork" / "ordered_transcripts"
    cow.mkdir(parents=True)
    (cow / "legal.md").write_text("## [1] USER\ncase text\n", encoding="utf-8")
    (cow / "ok.md").write_text("## [1] USER\nplain question\n\n## [2] ASSISTANT\nplain answer\n", encoding="utf-8")
    (root / "cowork" / "COW_SESSION_CATALOG.json").write_text(json.dumps([
        {"seq": 1, "filename": "legal.md", "stream": "legal", "session_id": "leg1", "title": "case", "turns": 1},
        {"seq": 2, "filename": "ok.md", "stream": "cm", "session_id": "ok1", "title": "plain", "turns": 2},
    ]), encoding="utf-8")

    db = root / "opencode.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE session (id TEXT, title TEXT, directory TEXT)")
    con.execute("INSERT INTO session VALUES ('ses_cow_001','old','V:\\\\work')")
    con.execute("INSERT INTO session VALUES ('ses_native','native title','V:\\\\work')")
    con.execute("CREATE TABLE message (id TEXT, session_id TEXT, data TEXT, time_created INT)")
    con.execute(
        "INSERT INTO message VALUES ('m1','ses_native',?,1)",
        (json.dumps({"role": "user", "content": "native hello"}),),
    )
    con.commit()
    con.close()

    desk = root / "desktop"
    desk.mkdir()
    (desk / "note.jsonl").write_text('{"type":"user","message":{"content":"desktop"}}\n', encoding="utf-8")


def main() -> int:
    results = []

    def check(label, fn):
        try:
            results.append((label, bool(fn()), ""))
        except Exception as exc:  # noqa: BLE001
            results.append((label, False, f"{type(exc).__name__}: {exc}"))

    root = Path(tempfile.mkdtemp(prefix="sesspage_"))
    _fixture(root)
    homes = _homes(root)
    found = engine.find(homes=homes, limit=50)
    ids = {h["id"] for h in found["hits"]}

    check("find counts every harness and leaves gemini unmeasured",
          lambda: found["kind"] == "OK" and found["n"] >= 6
          and any(f["family"] == "gemini" and f["n"] is None for f in found["gate"]["families"]))
    check("legal claude and cowork are counted, titles blank",
          lambda: found["legal_omitted"] >= 2
          and all(h["title"] == "" for h in found["hits"] if h["legal"]))
    check("ids are stable",
          lambda: f"grok-{UUID}" in ids and "cow-ok1" in ids and "cow-leg1" in ids
          and "ow-ses_native" in ids and "ow-ses_cow_001" not in ids)

    out = root / "out"
    imp = engine.import_session("cow-ok1", out, homes=homes)
    src = root / "cowork" / "ordered_transcripts" / "ok.md"
    before = src.read_bytes()
    check("import writes canonical jsonl and leaves the md",
          lambda: imp["kind"] == "OK" and imp["gate"]["n_turns"] == 2
          and (out / "cow-ok1.ctr.jsonl").is_file() and src.read_bytes() == before)
    try:
        engine.import_session("cow-leg1", out, homes=homes)
        check("legal import refuses", lambda: False)
    except engine.PageError as exc:
        check("legal import refuses", lambda: exc.kind == "LEGAL_OMITTED")

    exp = engine.export_md(f"grok-{UUID}", out, homes=homes)
    check("export is derived markdown",
          lambda: exp["kind"] == "OK" and "hello grok" in (out / f"grok-{UUID}.md").read_text(encoding="utf-8"))

    idx = engine.build_index(root / "index.jsonl", homes=homes)
    lines = (root / "index.jsonl").read_text(encoding="utf-8").splitlines()
    check("index has no legal body text",
          lambda: idx["gate"]["n"] == found["n"]
          and all("secret case" not in line and "case text" not in line for line in lines))

    good = root / "chat.jsonl"
    good.write_text('{"type":"user","text":"whole"}\n', encoding="utf-8")
    check("complete jsonl is already ok",
          lambda: engine.recover(good)["kind"] == "ALREADY_OK")
    broken = root / "broken.jsonl"
    broken.write_text('{"type":"user","text":"ok"}\n{"type":', encoding="utf-8")
    original = broken.read_bytes()
    nobak = engine.recover(broken)
    check("truncated jsonl without bak is named and untouched",
          lambda: nobak["kind"] == "NO_BAK" and broken.read_bytes() == original)
    bak = root / "broken.jsonl.bak"
    bak.write_text('{"type":"user","text":"restored"}\n', encoding="utf-8")
    dry = engine.recover(broken)
    check("recover without apply does not copy",
          lambda: dry["kind"] == "DRY_RUN" and broken.read_bytes() == original)
    applied = engine.recover(broken, apply=True, stage=root / "stage")
    check("apply restores from the sibling bak and stages the original",
          lambda: applied["kind"] == "OK" and b"restored" in broken.read_bytes()
          and (root / "stage").exists())

    db = root / "bad.db"
    db.write_bytes(b"not a database")
    good_db = root / "bad.db.bak_before"
    con = sqlite3.connect(good_db)
    con.execute("CREATE TABLE session (id TEXT)")
    con.execute("INSERT INTO session VALUES ('s1')")
    con.commit()
    con.close()
    fixed = engine.recover(db, bak=good_db, apply=True, stage=root / "stage2")
    check("sqlite restore uses the bak, not an in-place repair",
          lambda: fixed["kind"] == "OK" and engine._sqlite_ok(db)[0])

    resumed = engine.resume(f"cc-{CLAUDE[:-1]}a", homes=homes, launch=False)
    check("claude resume argv has no headless flag",
          lambda: resumed["kind"] == "OK" and resumed["gate"]["argv"][1:] == ["--resume", f"{CLAUDE[:-1]}a"]
          and "-p" not in resumed["gate"]["argv"])
    grok_res = engine.resume(f"grok-{UUID}", homes=homes)
    check("grok resume names --resume",
          lambda: grok_res["gate"]["argv"][1:3] == ["--resume", UUID])
    codex_res = engine.resume(f"cdx-{CODEX}", homes=homes)
    check("codex resume names resume",
          lambda: codex_res["gate"]["argv"][1:3] == ["resume", CODEX])
    cur_res = engine.resume(f"cur-{CURSOR}", homes=homes)
    check("cursor resume names agent --resume",
          lambda: any(part == "--resume" for part in cur_res["gate"]["argv"]) and CURSOR in cur_res["gate"]["argv"])
    ow = engine.resume("ow-ses_native", homes=homes, launch=True)
    check("openwork resume does not spawn",
          lambda: ow["kind"] == "OPENWORK_FOCUS" and ow["gate"]["launched"] is False)
    try:
        engine.resume("cow-leg1", homes=homes)
        check("legal resume refuses", lambda: False)
    except engine.PageError as exc:
        check("legal resume refuses", lambda: exc.kind == "LEGAL_OMITTED")

    scanned = engine.scan(root / "cowork")
    check("scan of a catalog quotes n and legal",
          lambda: scanned["kind"] == "OK" and scanned["gate"]["n"] == 2 and scanned["legal_omitted"] == 1)
    unknown = engine.scan(root / "empty_store")
    (root / "empty_store").mkdir()
    unknown = engine.scan(root / "empty_store")
    check("unknown store is unmeasured, not zero",
          lambda: unknown["kind"] == "UNMEASURED" and unknown["gate"]["n"] is None)

    loaded = engine.dispatch("load", {"id": f"cdx-{CODEX}", "store": str(root / "codex")})
    check("load codex turn count", lambda: loaded["kind"] == "OK" and loaded["gate"]["n_turns"] == 1)
    secret_dir = root / "grok" / "sec" / "66666666-6666-6666-6666-666666666666"
    secret_dir.mkdir(parents=True)
    (secret_dir / "summary.json").write_text(
        '{"info":{"id":"66666666-6666-6666-6666-666666666666","cwd":"V:\\\\work","generated_title":"sec"}}',
        encoding="utf-8")
    (secret_dir / "chat_history.jsonl").write_text(
        '{"type":"user","text":"token sk-abcdefghijklmnopqrstuvwxyz"}\n', encoding="utf-8")
    anon = engine.anonymize("grok-66666666-6666-6666-6666-666666666666", out, homes=homes)
    raw_left = (secret_dir / "chat_history.jsonl").read_text(encoding="utf-8")
    anon_body = (out / "grok-66666666-6666-6666-6666-666666666666.anon.ctr.jsonl").read_text(encoding="utf-8")
    check("anonymize redacts the copy only",
          lambda: anon["gate"]["n_redactions"] >= 1 and "sk-abcdefghijklmnopqrstuvwxyz" in raw_left
          and "sk-abcdefghijklmnopqrstuvwxyz" not in anon_body and "[REDACTED:" in anon_body)

    pair = root / "same.jsonl"
    pair.write_text('{"schema":"cosmos-transcript/1"}\n{"seq":1,"role":"user","text":"a"}\n', encoding="utf-8")
    diff = engine.diff_files(pair, pair)
    check("diff of a file against itself is identical",
          lambda: diff["gate"]["identical"] is True and diff["gate"]["n_turns_delta"] == 0)

    seed = root / "SEED.json"
    seed.write_text('{"tree_id":"t"}', encoding="utf-8")
    raw = seed.read_bytes()
    (root / "SEED.decl.json").write_text(json.dumps({"len": len(raw), "sha": engine.sha256_bytes(raw), "mac": "x"}), encoding="utf-8")
    check("seed check verifies len and sha", lambda: engine.check("seed", seed)["kind"] == "VERIFIED")
    (root / "BUCm.toml").write_text('schema = "bucm/1"\n', encoding="utf-8")
    check("sit check reads bucm", lambda: engine.check("sit", root / "BUCm.toml")["kind"] == "VERIFIED")

    stripped = engine.strip(f"grok-{UUID}", out, homes=homes, dry=True)
    check("strip dry writes nothing new", lambda: stripped["verb"] == "strip_dry" and stripped["gate"]["kept"] == 2)

    closed = engine.dispatch("rebind", {})
    check("rebind stays closed", lambda: closed["kind"] == "DO_NOT_REINGEST")
    check("doi does not claim existence", lambda: engine.dispatch("doi", {})["kind"] == "UNPROVEN")

    status = engine.home_status(homes)
    check("home status does not pretend a count", lambda: all(row["n"] is None for row in status))

    ui = sessions_page._ui_dir()
    check("ui files exist", lambda: (ui / "index.html").is_file() and (ui / "app.js").is_file())

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    thread = threading.Thread(target=sessions_page._serve, args=(port,), daemon=True)
    thread.start()
    deadline = time.time() + 5
    page = None
    while time.time() < deadline:
        try:
            page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.5).read().decode("utf-8")
            break
        except Exception:
            time.sleep(0.05)
    check("standalone page serves a session list",
          lambda: page is not None and 'id="list"' in page and "Import" in page)

    def post(body):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/run",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode("utf-8"))

    # The server uses default homes, not the fixture. Ask verbs and a typed refusal.
    verbs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/verbs", timeout=5).read().decode("utf-8"))
    check("verbs route lists find and resume",
          lambda: "find" in verbs["verbs"] and "resume" in verbs["verbs"])
    bad = None
    try:
        post({"action": "nope"})
    except urllib.error.HTTPError as exc:
        bad = json.loads(exc.read().decode("utf-8"))
    check("page refusal is a JSON error, not a disconnect",
          lambda: bad and bad.get("error") == "BAD_ACTION")

    plugin = (HERE / "plugin" / "deck_sessions_page.js").read_text(encoding="utf-8")
    check("plugin mounts one id and does not call Core",
          lambda: 'getElementById("panel-sessions-page")' in plugin and "cosmos_service" not in plugin
          and "/api/v1/" not in plugin)

    failed = [label for label, ok, _detail in results if not ok]
    for label, ok, detail in results:
        print(("ok  " if ok else "FAIL") + " " + label + (f" — {detail}" if detail else ""))
    print(f"{len(results) - len(failed)}/{len(results)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
