#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone sessions page.

    py -3.14 builds/sessions-page/sessions_page.py find
    py -3.14 builds/sessions-page/sessions_page.py import --id grok-<id> --out <dir>
    py -3.14 builds/sessions-page/sessions_page.py export --id <id> --out <dir>
    py -3.14 builds/sessions-page/sessions_page.py index
    py -3.14 builds/sessions-page/sessions_page.py recover --target <file> [--bak <file>] [--apply]
    py -3.14 builds/sessions-page/sessions_page.py resume --id <id> [--launch]
    py -3.14 builds/sessions-page/sessions_page.py serve --port 8786

Loopback only. The page and the CLI are the product. Cosmos Core picks the
same engine up later through cosmos/cosmos_session_tools_kit.py — already
imported by the existing /api/v1/session_tools route.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import engine  # noqa: E402


def _ui_dir() -> Path:
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen) / "ui"
    return HERE / "ui"


def _print(rec: dict) -> int:
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0 if rec.get("kind") in ("OK", "TRUNCATED", "DRY_RUN", "VERIFIED", "ALREADY_OK",
                                    "LAUNCHED", "OPENWORK_FOCUS", "UNPROVEN", "NO_BAK",
                                    "BINARY_ABSENT", "UNMEASURED", "DO_NOT_REINGEST") else 2


def _serve(port: int) -> int:
    ui = _ui_dir()
    allow = {
        "/": ui / "index.html",
        "/index.html": ui / "index.html",
        "/app.js": ui / "app.js",
        "/app.css": ui / "app.css",
    }

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:
            return

        def _cors(self) -> None:
            origin = self.headers.get("Origin") or ""
            if origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost"):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, rec: dict) -> None:
            raw = json.dumps(rec, ensure_ascii=False).encode("utf-8")
            self._send(code, raw, "application/json; charset=utf-8")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send(204, b"", "text/plain")

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/api/verbs":
                self._json(200, {"verbs": list(engine.VERBS), "harnesses": list(engine.HARNESSES)})
                return
            if path == "/api/homes":
                self._json(200, {"homes": engine.home_status()})
                return
            file = allow.get(path)
            if file is None or not file.is_file():
                self._json(404, {"kind": "NOT_FOUND", "path": path})
                return
            kind = "text/css" if file.suffix == ".css" else "text/javascript" if file.suffix == ".js" else "text/html; charset=utf-8"
            self._send(200, file.read_bytes(), kind)

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path != "/api/run":
                self._json(404, {"kind": "NOT_FOUND", "path": path})
                return
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError:
                length = 0
            if length > 1_000_000:
                self._json(400, {"error": "BAD_REQUEST", "detail": "body too large"})
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except ValueError as exc:
                self._json(400, {"error": "BAD_REQUEST", "detail": str(exc)})
                return
            if not isinstance(body, dict):
                self._json(400, {"error": "BAD_REQUEST", "detail": "body must be an object"})
                return
            try:
                rec = engine.dispatch(str(body.get("action") or ""), body)
            except engine.PageError as exc:
                self._json(400, {"error": exc.kind, "detail": str(exc)})
                return
            self._json(200, rec)

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        print(json.dumps({"kind": "BIND_FAILED", "port": port, "detail": str(exc)}))
        return 2
    print(json.dumps({"kind": "OK", "url": f"http://127.0.0.1:{port}/"}))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sessions_page")
    sub = parser.add_subparsers(dest="cmd", required=True)

    find = sub.add_parser("find")
    find.add_argument("--query", default="")
    find.add_argument("--harness", default="")
    find.add_argument("--cwd", default="")
    find.add_argument("--limit", type=int, default=engine.DEFAULT_LIMIT)

    imp = sub.add_parser("import")
    imp.add_argument("--id", required=True)
    imp.add_argument("--out", default="")

    exp = sub.add_parser("export")
    exp.add_argument("--id", required=True)
    exp.add_argument("--out", default="")

    idx = sub.add_parser("index")
    idx.add_argument("--out", default="")

    rec = sub.add_parser("recover")
    rec.add_argument("--target", required=True)
    rec.add_argument("--bak", default="")
    rec.add_argument("--apply", action="store_true")

    res = sub.add_parser("resume")
    res.add_argument("--id", required=True)
    res.add_argument("--launch", action="store_true")

    sc = sub.add_parser("scan")
    sc.add_argument("--store", required=True)

    ld = sub.add_parser("load")
    ld.add_argument("--id", required=True)
    ld.add_argument("--store", default="")

    srv = sub.add_parser("serve")
    srv.add_argument("--port", type=int, default=8786)
    sub.add_parser("verbs")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "find":
            return _print(engine.find(query=args.query, harness=args.harness, cwd=args.cwd, limit=args.limit))
        if args.cmd == "import":
            out = Path(args.out) if args.out else engine.var_dir() / "exports"
            return _print(engine.import_session(args.id, out))
        if args.cmd == "export":
            out = Path(args.out) if args.out else engine.var_dir() / "exports"
            return _print(engine.export_md(args.id, out))
        if args.cmd == "index":
            out = Path(args.out) if args.out else None
            return _print(engine.build_index(out))
        if args.cmd == "recover":
            bak = Path(args.bak) if args.bak else engine.nearest_bak(Path(args.target))
            return _print(engine.recover(Path(args.target), bak, apply=args.apply))
        if args.cmd == "resume":
            return _print(engine.resume(args.id, launch=args.launch))
        if args.cmd == "scan":
            return _print(engine.scan(Path(args.store)))
        if args.cmd == "load":
            body = {"id": args.id}
            if args.store:
                body["store"] = args.store
            return _print(engine.dispatch("load", body))
        if args.cmd == "verbs":
            return _print({"schema": engine.SCHEMA, "verb": "verbs", "kind": "OK",
                           "gate": {"verbs": list(engine.VERBS), "harnesses": list(engine.HARNESSES)},
                           "legal_omitted": 0})
        if args.cmd == "serve":
            return _serve(args.port)
    except engine.PageError as exc:
        print(json.dumps({"schema": engine.SCHEMA, "verb": args.cmd, "kind": exc.kind,
                          "gate": {"detail": str(exc)}, "legal_omitted": int(exc.kind == "LEGAL_OMITTED")}))
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
