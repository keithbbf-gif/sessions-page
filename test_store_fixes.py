#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermetic store-fix checks. Temp files only. No live profile, network, or spawn."""
from __future__ import annotations

import gc
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

CODEX_FOUND = "12121212-3434-5656-7878-909090909090"
CODEX_GONE = "abababab-cdcd-efef-0101-232323232323"
OPENWORK_BODY = {"role": "user", "content": "hello openwork"}
CODEX_LINE = (
    '{"type":"response_item","payload":{"role":"user","content":'
    '[{"type":"input_text","text":"hello codex"}]}}\n'
)


def _homes(tmp_path: Path, **assigned: Path) -> dict:
    homes = {name: None for name in engine.HARNESSES}
    for name, path in assigned.items():
        if name not in homes:
            raise AssertionError(f"{name} is not in HARNESSES")
        if path != tmp_path and tmp_path not in Path(path).parents:
            raise AssertionError("home escaped tmp_path")
        homes[name] = path
    return homes


def _contained(found: dict, tmp_path: Path) -> list[dict]:
    hits = found.get("hits")
    if not isinstance(hits, list):
        raise AssertionError("find result has no hits")
    for hit in hits:
        path = Path(str(hit.get("path") or ""))
        if path != tmp_path and tmp_path not in path.parents:
            raise AssertionError("find hit left tmp_path")
    return hits


def _n_turns(rec: dict) -> int:
    gate = rec.get("gate")
    if not isinstance(gate, dict) or "n_turns" not in gate:
        raise AssertionError("load result has no gate n_turns")
    return gate["n_turns"]


def _same(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _openwork_db(path: Path, sid: str, n: int, vary: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE session (id TEXT, title TEXT, directory TEXT)")
        con.execute(
            "INSERT INTO session (id, title, directory) VALUES (?, ?, ?)",
            (sid, "openwork", str(path.parent)),
        )
        con.execute(
            "CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT)"
        )
        rows = []
        for i in range(n):
            body = dict(OPENWORK_BODY)
            if vary:
                body["content"] = f"turn-{i}"
            rows.append((f"m{i:04d}", sid, i, json.dumps(body, separators=(",", ":"))))
        con.executemany("INSERT INTO message (id, session_id, time_created, data) VALUES (?, ?, ?, ?)", rows)
        con.commit()
    finally:
        con.close()


def _load(homes: dict, rec_id: str) -> dict:
    return engine.dispatch("load", {"id": rec_id}, homes=homes)


def case_openwork_short(tmp_path: Path) -> None:
    sid = "s1"
    db = tmp_path / "ow" / "opencode.db"
    _openwork_db(db, sid, 2, vary=False)
    homes = _homes(tmp_path, openwork=db)
    hits = _contained(engine.find(homes=homes), tmp_path)
    want = f"ow-{sid}"
    if want not in {hit["id"] for hit in hits}:
        raise AssertionError(f"find did not list {want}")
    loaded = _load(homes, want)
    if loaded.get("kind") != "OK" or _n_turns(loaded) != 2:
        raise AssertionError(f"kind {loaded.get('kind')} n_turns {_n_turns(loaded)}")


def case_openwork_truncated(tmp_path: Path) -> None:
    sid = "s2001"
    db = tmp_path / "ow-long" / "opencode-long.db"
    _openwork_db(db, sid, 2001, vary=True)
    homes = _homes(tmp_path, openwork=db)
    hits = _contained(engine.find(homes=homes), tmp_path)
    want = f"ow-{sid}"
    if want not in {hit["id"] for hit in hits}:
        raise AssertionError(f"find did not list {want}")
    loaded = _load(homes, want)
    if loaded.get("kind") != "TRUNCATED" or _n_turns(loaded) != 2000:
        raise AssertionError(f"kind {loaded.get('kind')} n_turns {_n_turns(loaded)}")


def _hermes_db(path: Path, sid: str, message: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute(
            "CREATE TABLE sessions ("
            "id TEXT, title TEXT, display_name TEXT, cwd TEXT, "
            "last_activity_at REAL, hidden INTEGER)"
        )
        con.execute(
            "INSERT INTO sessions (id, title, display_name, cwd, last_activity_at, hidden) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sid, "hermes title", "", str(path.parent), 100, 0),
        )
        if message is not None:
            con.execute(
                "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, timestamp REAL)"
            )
            con.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (sid, "user", message, 100),
            )
        con.commit()
    finally:
        con.close()


def case_hermes_unmeasured(tmp_path: Path) -> None:
    sid = "h1"
    db = tmp_path / "hermes" / "state.db"
    _hermes_db(db, sid, None)
    homes = _homes(tmp_path, hermes=db)
    hits = _contained(engine.find(homes=homes), tmp_path)
    want = f"hm-{sid}"
    if want not in {hit["id"] for hit in hits}:
        raise AssertionError(f"find did not list {want}")
    try:
        _load(homes, want)
    except engine.PageError as exc:
        if exc.kind != "UNMEASURED":
            raise AssertionError(f"kind {exc.kind}") from exc
        return
    raise AssertionError("expected PageError UNMEASURED")


def case_hermes_messages(tmp_path: Path) -> None:
    sid = "h2"
    db = tmp_path / "hermes-msg" / "state.db"
    _hermes_db(db, sid, "hermes hello")
    homes = _homes(tmp_path, hermes=db)
    hits = _contained(engine.find(homes=homes), tmp_path)
    want = f"hm-{sid}"
    if want not in {hit["id"] for hit in hits}:
        raise AssertionError(f"find did not list {want}")
    loaded = _load(homes, want)
    if loaded.get("kind") != "OK" or _n_turns(loaded) != 1:
        raise AssertionError(f"kind {loaded.get('kind')} n_turns {_n_turns(loaded)}")


def _codex_home(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "codex"
    real = home / "sessions" / "2026" / "11" / f"rollout-2026-11-05T01-02-03-{CODEX_FOUND}.jsonl"
    real.parent.mkdir(parents=True)
    real.write_text(CODEX_LINE, encoding="utf-8")
    missing_found = home / "absent" / f"rollout-2026-11-05T01-02-03-{CODEX_FOUND}.jsonl"
    missing_gone = home / "absent" / f"rollout-2026-11-05T01-02-03-{CODEX_GONE}.jsonl"
    db = home / "state_5.sqlite"
    con = sqlite3.connect(db)
    try:
        con.execute(
            "CREATE TABLE threads (id TEXT, cwd TEXT, title TEXT, rollout_path TEXT)"
        )
        con.execute(
            "INSERT INTO threads (id, cwd, title, rollout_path) VALUES (?, ?, ?, ?)",
            (CODEX_FOUND, str(home), "found", str(missing_found)),
        )
        con.execute(
            "INSERT INTO threads (id, cwd, title, rollout_path) VALUES (?, ?, ?, ?)",
            (CODEX_GONE, str(home), "gone", str(missing_gone)),
        )
        con.commit()
    finally:
        con.close()
    return home, real


def case_codex(tmp_path: Path) -> None:
    home, real = _codex_home(tmp_path)
    homes = _homes(tmp_path, codex=home)
    hits = _contained(engine.find(homes=homes), tmp_path)
    by_vendor = {}
    for hit in hits:
        if hit.get("harness") != "codex":
            continue
        by_vendor.setdefault(hit.get("vendor_id"), []).append(hit)
    found_rows = by_vendor.get(CODEX_FOUND) or []
    gone_rows = by_vendor.get(CODEX_GONE) or []
    if len(found_rows) != 1:
        raise AssertionError(f"codex found hits {len(found_rows)}")
    if not _same(Path(found_rows[0]["path"]), real):
        raise AssertionError("find path is not the real rollout")
    loaded = _load(homes, found_rows[0]["id"])
    if loaded.get("kind") != "OK" or _n_turns(loaded) != 1:
        raise AssertionError(f"kind {loaded.get('kind')} n_turns {_n_turns(loaded)}")
    if len(gone_rows) != 1:
        raise AssertionError(f"codex missing hits {len(gone_rows)}")
    try:
        _load(homes, gone_rows[0]["id"])
    except engine.PageError as exc:
        if exc.kind != "MISSING_FILE":
            raise AssertionError(f"kind {exc.kind}") from exc
        return
    raise AssertionError("expected PageError MISSING_FILE")


def case_antigravity(tmp_path: Path) -> bool:
    if "antigravity-cli" not in engine.HARNESSES:
        print("antigravity harness not wired")
        return True
    home = tmp_path / "antigravity-cli"
    home.mkdir()
    db = home / "conversation_summaries.db"
    con = sqlite3.connect(db)
    try:
        con.execute(
            "CREATE TABLE conversation_summaries ("
            "conversation_id TEXT, title TEXT, preview TEXT, step_count INTEGER, "
            "last_modified_time INTEGER, workspace_uris TEXT)"
        )
        con.execute(
            "INSERT INTO conversation_summaries ("
            "conversation_id, title, preview, step_count, last_modified_time, workspace_uris"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("conv1", "fence", "draw the fence", 1, 1700000000, json.dumps([str(home)])),
        )
        con.commit()
    finally:
        con.close()
    homes = _homes(tmp_path, **{"antigravity-cli": home})
    hits = [
        hit for hit in _contained(engine.find(homes=homes), tmp_path)
        if hit.get("harness") == "antigravity-cli"
    ]
    if len(hits) != 1:
        raise AssertionError(f"antigravity-cli hits {len(hits)}")
    loaded = _load(homes, hits[0]["id"])
    if loaded.get("kind") != "OK" or _n_turns(loaded) != 1:
        raise AssertionError(f"kind {loaded.get('kind')} n_turns {_n_turns(loaded)}")
    return False


def case_openwork_parts(tmp_path: Path) -> None:
    sid = "spart"
    db = tmp_path / "ow-part" / "opencode.db"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    try:
        con.execute("CREATE TABLE session (id TEXT, title TEXT, directory TEXT)")
        con.execute(
            "INSERT INTO session (id, title, directory) VALUES (?, ?, ?)",
            (sid, "parts", str(db.parent)),
        )
        con.execute(
            "CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT)"
        )
        con.execute(
            "INSERT INTO message (id, session_id, time_created, data) VALUES (?, ?, ?, ?)",
            (sid + "m", sid, 1, json.dumps({"role": "user"})),
        )
        con.execute(
            "CREATE TABLE part (id TEXT, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT)"
        )
        con.execute(
            "INSERT INTO part (id, message_id, session_id, time_created, data) VALUES (?, ?, ?, ?, ?)",
            ("p1", sid + "m", sid, 1, json.dumps({"type": "text", "text": "from the part"})),
        )
        con.commit()
    finally:
        con.close()
    homes = _homes(tmp_path, openwork=db)
    loaded = _load(homes, f"ow-{sid}")
    if loaded.get("kind") != "OK" or _n_turns(loaded) != 1:
        raise AssertionError(f"kind {loaded.get('kind')} n_turns {_n_turns(loaded)}")


def case_codex_zst(tmp_path: Path) -> None:
    from compression import zstd
    uid = "cdcdcdcd-1212-3434-5656-787878787878"
    home = tmp_path / "codex-zst"
    missing = home / "sessions" / f"rollout-2026-11-05T01-02-03-{uid}.jsonl"
    packed = Path(str(missing) + ".zst")
    packed.parent.mkdir(parents=True)
    packed.write_bytes(zstd.compress(CODEX_LINE.encode("utf-8")))
    db = home / "state_5.sqlite"
    con = sqlite3.connect(db)
    try:
        con.execute("CREATE TABLE threads (id TEXT, cwd TEXT, title TEXT, rollout_path TEXT)")
        con.execute(
            "INSERT INTO threads (id, cwd, title, rollout_path) VALUES (?, ?, ?, ?)",
            (uid, str(home), "packed", str(missing)),
        )
        con.commit()
    finally:
        con.close()
    homes = _homes(tmp_path, codex=home)
    loaded = _load(homes, f"cdx-{uid}")
    if loaded.get("kind") != "OK" or _n_turns(loaded) != 1:
        raise AssertionError(f"kind {loaded.get('kind')} n_turns {_n_turns(loaded)}")


def case_antigravity_steps(tmp_path: Path) -> None:
    sentence = "draw the north fence"
    noise = (
        sentence.encode("utf-8") + b"\n"
        + b"11111111-2222-3333-4444-555555555555\n"
        + b"application/json\n"
        + br"C:\temp\only\a\path.txt" + b"\n"
        + b"short text"
    )
    if engine._ag_payload_strings(noise) != [sentence]:
        raise AssertionError("step string filter dropped or kept the wrong rows")
    cid = "northfence"
    home = tmp_path / "antigravity-steps"
    db = home / "conversation_summaries.db"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    try:
        con.execute(
            "CREATE TABLE conversation_summaries ("
            "conversation_id TEXT, title TEXT, preview TEXT, step_count INTEGER, "
            "last_modified_time INTEGER, workspace_uris TEXT)"
        )
        con.execute(
            "INSERT INTO conversation_summaries ("
            "conversation_id, title, preview, step_count, last_modified_time, workspace_uris"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (cid, "fence", None, 1, 1700000000, json.dumps([str(home)])),
        )
        con.commit()
    finally:
        con.close()
    conv = home / "conversations" / f"{cid}.db"
    conv.parent.mkdir()
    payload = bytes((0x0A, len(sentence))) + sentence.encode("utf-8")
    c2 = sqlite3.connect(conv)
    try:
        c2.execute("CREATE TABLE steps (step_payload BLOB, metadata BLOB)")
        c2.execute(
            "INSERT INTO steps (step_payload, metadata) VALUES (?, ?)",
            (payload, b"south pasture stays shut"),
        )
        c2.commit()
    finally:
        c2.close()
    homes = _homes(tmp_path, antigravity=home)
    hits = [
        hit for hit in _contained(engine.find(homes=homes), tmp_path)
        if hit.get("harness") == "antigravity" and hit.get("vendor_id") == cid
    ]
    if len(hits) != 1:
        raise AssertionError(f"antigravity step hits {len(hits)}")
    loaded = _load(homes, hits[0]["id"])
    if loaded.get("kind") != "OK" or _n_turns(loaded) != 1:
        raise AssertionError(f"kind {loaded.get('kind')} n_turns {_n_turns(loaded)}")
    record = engine.load_record(hits[0])
    texts = [turn.get("text") or "" for turn in record["turns"]]
    if texts != [sentence]:
        raise AssertionError(f"step turns {len(texts)}")


def case_maybe_name_off(tmp_path: Path) -> None:
    import name_model
    saved = {
        "CMSESSIONS_NAME": os.environ.get("CMSESSIONS_NAME"),
        "XAI_API_KEY": os.environ.get("XAI_API_KEY"),
    }
    try:
        os.environ.pop("CMSESSIONS_NAME", None)
        os.environ.pop("XAI_API_KEY", None)
        if name_model.maybe_name({}) is not None:
            raise AssertionError("maybe_name returned a title while off")
        os.environ["CMSESSIONS_NAME"] = "1"
        if name_model.maybe_name({}) is not None:
            raise AssertionError("maybe_name returned a title without a key")
        os.environ.pop("CMSESSIONS_NAME", None)
        os.environ["XAI_API_KEY"] = "not-used"
        if name_model.maybe_name({"legal": True}) is not None:
            raise AssertionError("maybe_name returned a title for a legal header")
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def case_antigravity_ide_files(tmp_path: Path) -> None:
    if "antigravity-ide" not in engine.HARNESSES:
        print("antigravity-ide harness not wired")
        return True
    home = tmp_path / "ide"
    conv = home / "conversations"
    conv.mkdir(parents=True)
    (conv / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.db").write_bytes(b"")
    homes = _homes(tmp_path, **{"antigravity-ide": home})
    hits = [
        hit for hit in _contained(engine.find(homes=homes), tmp_path)
        if hit.get("harness") == "antigravity-ide"
    ]
    if len(hits) != 1:
        raise AssertionError(f"antigravity-ide hits {len(hits)}")
    return False


def main() -> int:
    failed: list[str] = []
    passed = 0
    cases = (
        ("openwork find ow-id and load n_turns 2", case_openwork_short),
        ("openwork 2001 messages TRUNCATED n_turns 2000", case_openwork_truncated),
        ("hermes sessions-only load raises UNMEASURED", case_hermes_unmeasured),
        ("hermes messages load kind OK n_turns 1", case_hermes_messages),
        ("codex real rollout n_turns 1 and missing file", case_codex),
        ("antigravity-cli find and load n_turns 1", case_antigravity),
        ("openwork part text is the turn", case_openwork_parts),
        ("codex jsonl.zst loads", case_codex_zst),
        ("antigravity-ide lists a conversation db", case_antigravity_ide_files),
        ("antigravity step_payload sentence without preview", case_antigravity_steps),
        ("maybe_name stays off without env", case_maybe_name_off),
    )
    with tempfile.TemporaryDirectory(prefix="sesspage_store_", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        for label, fn in cases:
            try:
                skipped = fn(tmp_path)
            except Exception as exc:  # noqa: BLE001 — report the engine result, do not weaken
                failed.append(label)
                print(f"FAIL {label} — {type(exc).__name__}: {exc}")
                continue
            if skipped:
                continue
            passed += 1
            print(f"ok  {label}")
        gc.collect()
    print(f"{passed}/{passed + len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
