#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermetic checks for the sessions-page engine. No live profile walk."""
from __future__ import annotations

import http.client
import json
import os
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

    extra = _homes(root)
    cline = root / "cline" / "task-1"
    cline.mkdir(parents=True)
    (cline / "api_conversation_history.json").write_text(json.dumps([
        {"role": "user", "content": "cline hello"},
        {"role": "assistant", "content": "cline hi"},
    ]), encoding="utf-8")
    pi = root / "pi"
    pi.mkdir()
    (pi / "sess.jsonl").write_text('{"role":"user","content":"pi hello"}\n', encoding="utf-8")
    chats = root / "gemini-store" / "proj" / "chats"
    chats.mkdir(parents=True)
    (chats.parent / ".project_root").write_text(r"V:\work\gem", encoding="utf-8")
    (chats / "session-abc.jsonl").write_text(
        '{"sessionId":"abc","kind":"header"}\n'
        '{"type":"user","message":{"content":"gem hello"}}\n',
        encoding="utf-8")
    (chats / "session-json.json").write_text(json.dumps({
        "messages": [{"role": "user", "content": "gem json"}],
    }), encoding="utf-8")
    hermes_db = root / "hermes.db"
    con = sqlite3.connect(hermes_db)
    con.execute(
        "CREATE TABLE sessions (id TEXT, title TEXT, display_name TEXT, cwd TEXT, "
        "last_activity_at REAL, hidden INTEGER)")
    con.execute(
        "INSERT INTO sessions VALUES ('h1', 'hermes title', '', ?, 100, 0)",
        (r"V:\work",))
    con.commit()
    con.close()
    extra["cline"] = root / "cline"
    extra["pi"] = pi
    extra["gemini"] = root / "gemini-store"
    extra["hermes"] = hermes_db
    extra_found = engine.find(homes=extra, limit=50)
    extra_ids = {h["id"] for h in extra_found["hits"]}
    check("cline, pi, gemini, and hermes are counted",
          lambda: "cln-task-1" in extra_ids and "pi-sess" in extra_ids
          and "gem-session-abc" in extra_ids and "gem-session-json" in extra_ids
          and "hm-h1" in extra_ids)
    cline_imp = engine.import_session("cln-task-1", root / "out-cline", homes=extra)
    check("cline import reads the json history",
          lambda: cline_imp["kind"] == "OK" and cline_imp["gate"]["n_turns"] == 2)
    hermes_kind = None
    try:
        engine.import_session("hm-h1", root / "out-hermes", homes=extra)
    except engine.PageError as exc:
        hermes_kind = exc.kind
    check("hermes sqlite is listed and its transcript import stays unmeasured",
          lambda: hermes_kind == "UNMEASURED")

    doc = _homes(root)
    modern_id = "sess-modern"
    modern = root / "cline-sessions" / modern_id
    modern.mkdir(parents=True)
    (modern / f"{modern_id}.messages.json").write_text(json.dumps([
        {"role": "user", "content": "modern"},
        {"role": "assistant", "content": "ok"},
    ]), encoding="utf-8")
    qchats = root / "qwen" / "sanitized" / "chats"
    qchats.mkdir(parents=True)
    (qchats / "qw1.jsonl").write_text('{"role":"user","content":"qwen"}\n', encoding="utf-8")
    goose_db = root / "goose" / "sessions.db"
    goose_db.parent.mkdir(parents=True)
    gcon = sqlite3.connect(goose_db)
    gcon.execute(
        "CREATE TABLE sessions (id TEXT, name TEXT, working_dir TEXT, updated_at REAL, session_type TEXT)")
    gcon.execute(
        "INSERT INTO sessions VALUES ('g1', 'goose title', ?, 100, 'user')", (r"V:\work",))
    gcon.execute(
        "INSERT INTO sessions VALUES ('g-hidden', 'nope', '', 1, 'hidden')")
    gcon.commit()
    gcon.close()
    cop = root / "copilot" / "not-the-id"
    cop.mkdir(parents=True)
    (cop / "events.jsonl").write_text(
        json.dumps({"type": "session.start", "data": {"sessionId": "cop1", "context": {"cwd": r"V:\work"}}}) + "\n"
        + json.dumps({"type": "user.message", "data": {"content": "hi copilot"}}) + "\n",
        encoding="utf-8")
    cont = root / "continue"
    cont.mkdir()
    (cont / "sessions.json").write_text("{}", encoding="utf-8")
    (cont / "keep.json").write_text(json.dumps({
        "sessionId": "keep", "title": "continue title", "workspaceDirectory": r"V:\work",
        "history": [{"role": "user", "content": "cont"}],
    }), encoding="utf-8")
    amp = root / "amp"
    amp.mkdir()
    (amp / "T-amp1.json").write_text(json.dumps({
        "id": "T-amp1", "title": "amp title",
        "messages": [{"role": "user", "content": "amp"}],
    }), encoding="utf-8")
    project = root / "proj"
    crush_db = project / ".crush" / "crush.db"
    crush_db.parent.mkdir(parents=True)
    ccon = sqlite3.connect(crush_db)
    ccon.execute(
        "CREATE TABLE sessions (id TEXT, parent_session_id TEXT, title TEXT, updated_at INTEGER, created_at INTEGER)")
    ccon.execute("INSERT INTO sessions VALUES ('one', NULL, 'crush title', 100, 100)")
    ccon.execute("INSERT INTO sessions VALUES ('child', 'one', 'child', 100, 100)")
    ccon.commit()
    ccon.close()
    registry = root / "crush" / "projects.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({
        "projects": [{"path": str(project), "data_dir": str(crush_db.parent)}],
    }), encoding="utf-8")
    zstd = root / "dsh" / "sessions" / "bucket" / "session-abc" / "session.v3.jsonl.zstd"
    zstd.parent.mkdir(parents=True)
    zstd.write_bytes(b"not-decompressed")
    history = root / "repo" / ".aider.chat.history.md"
    history.parent.mkdir(parents=True)
    history.write_text("# history\n", encoding="utf-8")
    hands = root / "openhands" / "conv-1"
    hands.mkdir(parents=True)
    (hands / "base_state.json").write_text(json.dumps({"id": "conv-1", "title": "oh"}), encoding="utf-8")
    (hands / "events").mkdir()
    (hands / "events" / "event-00001-x.json").write_text("{}", encoding="utf-8")
    kilo = root / "kilo" / "task-k"
    kilo.mkdir(parents=True)
    (kilo / "api_conversation_history.json").write_text(json.dumps([
        {"role": "user", "content": "kilo"},
    ]), encoding="utf-8")
    doc["cline"] = root / "cline-sessions"
    doc["qwen"] = root / "qwen"
    doc["goose"] = goose_db
    doc["copilot"] = root / "copilot"
    doc["continue"] = cont
    doc["amp"] = amp
    doc["crush"] = registry
    doc["dsh"] = root / "dsh"
    doc["aider"] = history
    doc["openhands"] = root / "openhands"
    doc["kilo"] = root / "kilo"
    doc_found = engine.find(homes=doc, limit=50)
    doc_ids = {h["id"] for h in doc_found["hits"]}
    check("documented stores are counted and indexes are not",
          lambda: {
              "cln-sess-modern", "qw-qw1", "goo-g1", "cop-cop1", "con-keep",
              "amp-T-amp1", "cru-one", "dsh-session-abc", "oh-conv-1", "kilo-task-k",
          }.issubset(doc_ids)
          and "goo-g-hidden" not in doc_ids and "con-sessions" not in doc_ids
          and "cru-child" not in doc_ids and "cop-not-the-id" not in doc_ids)
    check("aider counts the one history file",
          lambda: any(h["harness"] == "aider" and h["path"].endswith(".aider.chat.history.md") for h in doc_found["hits"]))
    fams = {f["family"]: f["n"] for f in doc_found["gate"]["families"]}
    check("stores without a documented transcript stay null",
          lambda: fams["factory"] is None and fams["windsurf"] is None
          and fams["amazonq"] is None and fams["augment"] is None)
    modern_imp = engine.import_session("cln-sess-modern", root / "out-modern", homes=doc)
    cop_imp = engine.import_session("cop-cop1", root / "out-cop", homes=doc)
    amp_imp = engine.import_session("amp-T-amp1", root / "out-amp", homes=doc)
    con_imp = engine.import_session("con-keep", root / "out-con", homes=doc)
    check("json transcripts import and sqlite or zstd stay unmeasured",
          lambda: modern_imp["kind"] == "OK" and modern_imp["gate"]["n_turns"] == 2
          and cop_imp["kind"] == "OK" and cop_imp["gate"]["n_turns"] == 1
          and amp_imp["kind"] == "OK" and amp_imp["gate"]["n_turns"] == 1
          and con_imp["kind"] == "OK" and con_imp["gate"]["n_turns"] == 1)
    unmeasured = {}
    for rec_id, label in (("goo-g1", "goose"), ("cru-one", "crush"), ("dsh-session-abc", "dsh")):
        try:
            engine.import_session(rec_id, root / "out-unmeasured" / label, homes=doc)
            unmeasured[label] = "OK"
        except engine.PageError as exc:
            unmeasured[label] = exc.kind
    check("goose, crush, and dsh import stay unmeasured",
          lambda: unmeasured == {"goose": "UNMEASURED", "crush": "UNMEASURED", "dsh": "UNMEASURED"})
    pi_res = engine.resume("pi-sess", homes=extra)
    hm_res = engine.resume("hm-h1", homes=extra)
    legacy = engine.resume("cln-task-1", homes=extra)
    mod_res = engine.resume("cln-sess-modern", homes=doc)
    goo_res = engine.resume("goo-g1", homes=doc)
    qw_res = engine.resume("qw-qw1", homes=doc)
    cop_res = engine.resume("cop-cop1", homes=doc)
    cru_res = engine.resume("cru-one", homes=doc)
    check("documented resume flags are named",
          lambda: pi_res["kind"] == "OK" and pi_res["gate"]["argv"][1] == "--session"
          and str(pi_res["gate"]["argv"][2]).endswith("sess.jsonl")
          and hm_res["gate"]["argv"][1:] == ["--resume", "h1"]
          and legacy["kind"] == "UNMEASURED"
          and mod_res["kind"] == "OK" and mod_res["gate"]["argv"][1:] == ["--id", "sess-modern"]
          and goo_res["gate"]["argv"][1:] == ["session", "--resume", "--session-id", "g1"]
          and qw_res["gate"]["argv"][1:] == ["--resume", "qw1"]
          and cop_res["gate"]["argv"][1:] == ["--resume=cop1"]
          and cru_res["kind"] == "OK" and cru_res["gate"]["argv"][1:] == ["--session", "one"]
          and cru_res["gate"]["cwd"] == str(project))

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
    seen = engine.preview(f"grok-{UUID}", homes=homes)
    check("preview quotes a turn and writes nothing",
          lambda: seen["kind"] == "OK" and seen["gate"]["shown"] >= 1
          and any("hello grok" in (turn.get("text") or "") for turn in seen["gate"]["turns"])
          and not (out / f"grok-{UUID}.ctr.jsonl").exists())
    try:
        engine.preview("cow-leg1", homes=homes)
        check("legal preview refuses", lambda: False)
    except engine.PageError as exc:
        check("legal preview refuses", lambda: exc.kind == "LEGAL_OMITTED")

    scoped = engine.find(homes=homes, harness="grok", limit=50)
    claude_n = [fam["n"] for fam in scoped["gate"]["families"] if fam["family"] == "claude"]
    check("a harness filter keeps the other counts",
          lambda: scoped["hits"] and all(hit["harness"] == "grok" for hit in scoped["hits"])
          and claude_n and claude_n[0] and claude_n[0] >= 1)

    project = root / "claude" / "projects" / "P--Legal-case"
    project.mkdir(parents=True)
    hidden = project / "12121212-1212-1212-1212-121212121212.jsonl"
    hidden.write_text('{"type":"user","message":{"content":"not a path"}}\n', encoding="utf-8")
    sealed = engine.find(homes=homes, limit=80)
    sealed_hit = next(hit for hit in sealed["hits"] if hit["vendor_id"] == "12121212-1212-1212-1212-121212121212")
    try:
        engine.preview(sealed_hit["id"], homes=homes)
        check("folder name seals a legal claude session", lambda: False)
    except engine.PageError as exc:
        check("folder name seals a legal claude session",
              lambda: sealed_hit["legal"] is True and sealed_hit["title"] == "" and exc.kind == "LEGAL_OMITTED")

    wide_id = "88888888-8888-8888-8888-888888888888"
    wide = root / "grok" / "wide" / wide_id
    wide.mkdir(parents=True)
    (wide / "summary.json").write_text(json.dumps({
        "info": {"id": wide_id, "cwd": r"V:\work", "generated_title": "wide"},
    }), encoding="utf-8")
    chunks = []
    for i in range(3000):
        role = "user" if i % 2 == 0 else "assistant"
        chunks.append(json.dumps({"type": role, "text": f"turn-{i}-" + ("x" * 180)}))
    payload = ("\n".join(chunks) + "\n").encode("utf-8")
    (wide / "chat_history.jsonl").write_bytes(payload)
    check("wide transcript is past the preview head", lambda: len(payload) > engine.PREVIEW_WHOLE)
    seen_wide = engine.preview(f"grok-{wide_id}", homes=homes, turns=4, chars=40)
    wide_text = "\n".join((turn.get("text") or "") for turn in seen_wide["gate"]["turns"])
    check("wide preview reads the head and does not invent a total",
          lambda: seen_wide["kind"] == "OK" and seen_wide["gate"]["n_turns"] is None
          and seen_wide["gate"]["shown"] == 4 and "turn-0-" in wide_text
          and "turn-2999-" not in wide_text
          and not (out / f"grok-{wide_id}.ctr.jsonl").exists())

    named_id = "99999999-9999-9999-9999-999999999999"
    named = root / "grok" / "named" / named_id
    named.mkdir(parents=True)
    (named / "summary.json").write_text(json.dumps({
        "generated_title": "root session name",
        "info": {"id": named_id, "cwd": r"V:\work"},
    }), encoding="utf-8")
    (named / "chat_history.jsonl").write_text(
        '{"type":"system","text":"system prompt stays out"}\n'
        '{"type":"user","text":"ignored because the summary has a name"}\n',
        encoding="utf-8")
    named_found = engine.find(homes=homes, query="root session name", limit=20)
    check("a root summary title is searchable",
          lambda: any(hit["vendor_id"] == named_id and hit["title"] == "root session name"
                      for hit in named_found["hits"]))

    bare_id = "77777777-7777-7777-7777-777777777777"
    bare = root / "grok" / "bare" / bare_id
    bare.mkdir(parents=True)
    (bare / "summary.json").write_text(json.dumps({
        "info": {"id": bare_id, "cwd": r"V:\work"},
    }), encoding="utf-8")
    (bare / "chat_history.jsonl").write_text(
        '{"type":"system","text":"you are a helper with a long preamble"}\n'
        '{"type":"user","text":"plan the fence"}\n'
        '{"type":"assistant","text":"start with the posts"}\n',
        encoding="utf-8")
    bare_found = engine.find(homes=homes, limit=100)
    bare_hit = next(hit for hit in bare_found["hits"] if hit["vendor_id"] == bare_id)
    bare_seen = engine.preview(bare_hit["id"], homes=homes)
    bare_roles = [turn.get("role") for turn in bare_seen["gate"]["turns"]]
    bare_text = "\n".join(turn.get("text") or "" for turn in bare_seen["gate"]["turns"])
    check("a missing summary title uses the first user line",
          lambda: bare_hit["title"] == "plan the fence")
    check("preview skips the system prompt and still counts it",
          lambda: bare_seen["kind"] == "OK" and bare_seen["gate"]["n_turns"] == 3
          and bare_seen["gate"]["shown"] == 2 and "system" not in bare_roles
          and "plan the fence" in bare_text and "you are a helper" not in bare_text)

    again = engine.find(homes=homes, limit=100)
    check("the next find sees a session added after the last one",
          lambda: any(hit["vendor_id"] == wide_id for hit in again["hits"]))

    calls = {"n": 0}
    real_walk = engine._walk_report
    real_key = engine._live_key

    def _counting(value):
        calls["n"] += 1
        return real_walk(value)

    engine._walk_report = _counting
    engine._live_key = lambda: engine._homes_key(homes)
    engine._live_rows["key"] = None
    engine._live_rows["hits"] = []
    try:
        engine.find(homes=homes, limit=20)
        calls["n"] = 0
        engine.preview(f"grok-{UUID}", homes=homes)
        check("preview reuses the find list", lambda: calls["n"] == 0)
    finally:
        engine._walk_report = real_walk
        engine._live_key = real_key
        engine._live_rows["key"] = None
        engine._live_rows["hits"] = []
        engine._live_rows["failed"] = {}

    bad_homes = dict(homes)
    bad_db = root / "bad-openwork.db"
    bad_con = sqlite3.connect(bad_db)
    bad_con.execute("CREATE TABLE note (id TEXT)")
    bad_con.commit()
    bad_con.close()
    bad_homes["openwork"] = bad_db
    broken_cat = root / "bad-cow"
    broken_cat.mkdir()
    (broken_cat / "COW_SESSION_CATALOG.json").write_text("{", encoding="utf-8")
    bad_homes["cowork"] = broken_cat
    survived = engine.find(homes=bad_homes, limit=30)
    fam = {row["family"]: row for row in survived["gate"]["families"]}
    check("one bad store does not hide the others",
          lambda: any(hit["harness"] == "grok" for hit in survived["hits"])
          and fam["openwork"]["status"] == "SCHEMA_UNKNOWN" and fam["openwork"]["n"] is None
          and fam["cowork"]["status"] == "UNPARSEABLE" and fam["cowork"]["n"] is None)

    legal_file = root / "claude" / "projects" / "P-Legal" / f"{CLAUDE}.jsonl"
    legal_bytes = legal_file.read_bytes()
    try:
        engine.recover(legal_file, apply=True)
        check("legal recover refuses", lambda: False)
    except engine.PageError as exc:
        check("legal recover refuses",
              lambda: exc.kind == "LEGAL_OMITTED" and legal_file.read_bytes() == legal_bytes)

    fk = root / "fk.db"
    fk_con = sqlite3.connect(fk)
    fk_con.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    fk_con.execute("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))")
    fk_con.execute("PRAGMA foreign_keys=OFF")
    fk_con.execute("INSERT INTO child VALUES (1, 99)")
    fk_con.commit()
    fk_con.close()
    fk_before = fk.read_bytes()
    (root / "fk.db.bak").write_bytes(b"not a database")
    fk_rec = engine.recover(fk, apply=True)
    check("foreign keys do not count as damage",
          lambda: fk_rec["kind"] == "ALREADY_OK" and fk.read_bytes() == fk_before)

    empty = root / "empty.jsonl"
    empty.write_bytes(b"")
    (root / "empty.jsonl.bak").write_text('{"type":"user","text":"back"}\n', encoding="utf-8")
    check("an empty jsonl is not already healthy",
          lambda: engine.recover(empty)["kind"] == "DRY_RUN")
    engine.recover(empty, apply=True, stage=root / "stage-empty")
    check("an empty jsonl restores from the sibling bak",
          lambda: b"back" in empty.read_bytes())

    newer = root / "pick.jsonl.bak"
    older = root / "pick.jsonl.bak.1"
    pick = root / "pick.jsonl"
    pick.write_text('{"type":\n', encoding="utf-8")
    newer.write_text("{not-json", encoding="utf-8")
    older.write_text('{"type":"user","text":"older"}\n', encoding="utf-8")
    os.utime(older, (1, 1))
    os.utime(newer, None)
    engine.recover(pick, apply=True, stage=root / "stage-pick")
    check("an older good bak is used when the newest bak is bad",
          lambda: b"older" in pick.read_bytes())

    mix = root / "mix.db"
    mix.write_bytes(b"not a database")
    wal_side = Path(str(mix) + "-wal")
    wal_side.write_bytes(b"wal-bytes")
    good_mix = root / "mix.db.bak"
    mix_con = sqlite3.connect(good_mix)
    mix_con.execute("CREATE TABLE t (id INT)")
    mix_con.execute("INSERT INTO t VALUES (7)")
    mix_con.commit()
    mix_con.close()
    mix_rec = engine.recover(mix, bak=good_mix, apply=True, stage=root / "stage-wal")
    staged_wal = Path(mix_rec["gate"]["staged_path"]).parent / "mix.db-wal"
    check("sqlite restore parks the wal sidecar",
          lambda: mix_rec["kind"] == "OK" and engine._sqlite_ok(mix)[0]
          and not wal_side.exists() and staged_wal.read_bytes() == b"wal-bytes")

    held = root / "held.jsonl"
    held.write_text('{"type":\n', encoding="utf-8")
    (root / "held.jsonl.bak").write_text('{"type":"user","text":"safe"}\n', encoding="utf-8")
    held_bytes = held.read_bytes()
    real_replace = engine.os.replace

    def _deny(*_args, **_kwargs):
        raise PermissionError("held")

    engine.os.replace = _deny
    held_kind = ""
    try:
        try:
            engine.recover(held, apply=True, stage=root / "stage-held")
        except engine.PageError as exc:
            held_kind = exc.kind + " " + str(exc)
    finally:
        engine.os.replace = real_replace
    check("a blocked replace leaves the original in place",
          lambda: held_kind.startswith("RESTORE_FAILED") and "stage-held" in held_kind
          and held.read_bytes() == held_bytes)

    busy = root / "busy.db"
    busy_con = sqlite3.connect(busy)
    busy_con.execute("CREATE TABLE t (id INT)")
    busy_con.commit()
    busy_con.close()
    busy_bytes = busy.read_bytes()
    real_state = engine._sqlite_state

    def _locked(path):
        if path.name == "busy.db":
            return "busy", "database is locked"
        return real_state(path)

    engine._sqlite_state = _locked
    try:
        busy_rec = engine.recover(busy, apply=True)
    finally:
        engine._sqlite_state = real_state
    check("a locked database is not replaced",
          lambda: busy_rec["kind"] == "BUSY" and busy.read_bytes() == busy_bytes)

    try:
        engine.dispatch("find", {"fresh": "yes"}, homes=homes)
        check("fresh must be a boolean", lambda: False)
    except engine.PageError as exc:
        check("fresh must be a boolean", lambda: exc.kind == "BAD_INPUT")

    v_found = engine.find(homes=homes, drive="V:", limit=50)
    other_letter = "D:" if str(root.drive).upper() != "D:" else "E:"
    other_found = engine.find(homes=homes, drive=other_letter, limit=20)
    check("project cwd counts and a blank legal cwd does not",
          lambda: any(hit["id"] == f"grok-{UUID}" for hit in v_found["hits"])
          and all(not hit["legal"] or str(hit["path"]).upper().startswith("V:\\") for hit in v_found["hits"])
          and other_found["n"] == 0)

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
          lambda: page is not None and 'id="list"' in page and "Import" in page
          and 'id="drive-grid"' in page and 'id="place-grid"' in page
      and 'id="preview"' in page and 'id="restore"' in page and "Anonymize" in page)

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
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    conn.request("POST", "/api/run", body=b"{}", headers={"Content-Length": "-1"})
    refused = conn.getresponse()
    refused_body = refused.read()
    conn.close()
    check("a negative content length is refused",
          lambda: refused.status == 400 and b"BAD_REQUEST" in refused_body)
    places = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/places", timeout=5).read().decode("utf-8"))
    check("places lists drives and default locations before a count",
          lambda: isinstance(places.get("drives"), list) and len(places["drives"]) >= 1
          and any(h.get("harness") == "grok" and h.get("n") is None for h in places.get("homes") or []))
    letter = str(root.drive or "")
    other = "Q:" if letter.upper() != "Q:" else "R:"
    on_drive = engine.find(homes=homes, drive=letter, limit=50) if letter else None
    off_drive = engine.find(homes=homes, drive=other, limit=50)
    check("find can stay on one drive",
          lambda: (on_drive is None or on_drive["n"] >= 1) and off_drive["n"] == 0)

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
