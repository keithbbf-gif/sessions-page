#!/usr/bin/env python3
"""Standalone sessions page.

    py -3.14 builds/sessions-page/sessions_page.py find
    py -3.14 builds/sessions-page/sessions_page.py import --id grok-<id> --out <dir>
    py -3.14 builds/sessions-page/sessions_page.py export --id <id> --out <dir>
    py -3.14 builds/sessions-page/sessions_page.py index
    py -3.14 builds/sessions-page/sessions_page.py recover --target <file> [--bak <file>] [--apply]
    py -3.14 builds/sessions-page/sessions_page.py resume --id <id> [--launch]
    py -3.14 builds/sessions-page/sessions_page.py serve --port 8786
    py -3.14 builds/sessions-page/sessions_page.py desk
    py -3.14 builds/sessions-page/sessions_page.py formats

The frozen no-args exe opens the modern Full Screen UI in a standalone window.
`desk` opens the native Tkinter desk window.
`serve` runs the loopback page. Cosmos Core picks the same engine up
later through cosmos/cosmos_session_tools_kit.py — already imported by the
existing /api/v1/session_tools route.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import secrets
import sys
import threading
import time
import types
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import engine

# Load the error map without executing csm_core/__init__.py. That init pulls
# scale_indexer, cluster_topology, replay_engine, and dual_lock_proxy, which
# stay off this page and off engine.dispatch.
if "csm_core" not in sys.modules:
    _csm_pkg = types.ModuleType("csm_core")
    _csm_pkg.__path__ = [str(HERE / "csm_core")]
    _csm_pkg.__package__ = "csm_core"
    sys.modules["csm_core"] = _csm_pkg
from csm_core.error_handlers import to_http
from csm_core.errors import (
    ApiError,
    BadJsonError,
    BadVerbError,
    HarnessMissingError,
    LegalOmittedError,
    NotFoundError,
    NotResumableError,
)

# Desk, the full-screen page, the classic page, and the deck plug already
# name these. Each one is an engine verb. /api/run and the matching CLI
# command call engine.dispatch. They are not local flash stubs.
ADVERTISED = (
    "find", "preview", "import", "export", "index", "recover", "resume",
    "load", "formats", "handoff", "anonymize", "crash-recover",
    "strip", "strip_dry",
)
_SERVE_HOST = "127.0.0.1"
_SERVE_PORT = 8786


def _soft_import(name: str):
    """Optional sibling modules. Absence must not stop this branch."""
    try:
        return importlib.import_module(name)
    except Exception:
        return None


_CSM_ERRORS = _soft_import("csm_core.errors")
_CSM_PERSIST = _soft_import("csm_core.persist")
_CSM_TOKENCTR = _soft_import("csm_core.tokenctr_bridge")


def _error_types() -> tuple[type, ...]:
    types: list[type] = [engine.PageError]
    mod = _OPTIONAL[0]
    extra = getattr(mod, "PageError", None) if mod is not None else None
    if isinstance(extra, type) and issubclass(extra, BaseException) and extra not in types:
        types.append(extra)
    return tuple(types)


def _verb_names() -> list[str]:
    """Engine verbs, with every advertised name present so /api/verbs matches the page."""
    names = list(engine.VERBS)
    have = set(names)
    for name in ADVERTISED:
        if name not in have:
            names.append(name)
            have.add(name)
    return names


def _dispatch(action: str, body: dict | None = None) -> dict:
    """Run one verb through the engine. There is no local flash stub."""
    payload = body if isinstance(body, dict) else {}
    name = str(action or payload.get("action") or payload.get("verb") or "").strip()
    return engine.dispatch(name, payload)


def _account_status() -> dict:
    """Token Center status. A missing bridge stays unavailable and opens no socket."""
    unavailable = {"status": "unavailable", "reason": "not_configured"}
    mod = _soft_import("csm_core.tokenctr_bridge")
    fn = getattr(mod, "account_status", None) if mod is not None else None
    if not callable(fn):
        return unavailable
    try:
        rec = fn()
    except Exception:
        return unavailable
    if not isinstance(rec, dict):
        return unavailable
    return rec


# Kept so the three optional imports stay live. None means that module is absent.
_OPTIONAL = (_CSM_ERRORS, _CSM_PERSIST, _CSM_TOKENCTR)

_PAGE_API: dict[str, type[ApiError]] = {
    "BAD_ACTION": BadVerbError,
    "BAD_INPUT": BadJsonError,
    "BAD_REQUEST": BadJsonError,
    "NOT_FOUND": NotFoundError,
    "NO_STORE": NotFoundError,
    "LEGAL_OMITTED": LegalOmittedError,
    "BINARY_ABSENT": HarnessMissingError,
    "NOT_RESUMABLE": NotResumableError,
}


def _public_ok(text: str) -> bool:
    """A short sentence with no path and no traceback."""
    if not isinstance(text, str) or not text or len(text) > 200:
        return False
    if any(mark in text for mark in ("\n", "\r", "\\", "/Users/", "/home/")):
        return False
    if ":\\" in text or ":/" in text:
        return False
    return True


def _mutate_budget() -> tuple[int, float]:
    raw = (os.environ.get("CMSESSIONS_MUTATE_RATE") or "").strip()
    if not raw:
        return 20, 10.0
    try:
        if "/" in raw:
            left, right = raw.split("/", 1)
            limit, window = int(left), float(right)
        else:
            limit, window = int(raw), 10.0
    except ValueError:
        return 20, 10.0
    if limit < 1 or window <= 0:
        return 20, 10.0
    return limit, window


def _action_of(body: dict) -> str:
    return str(body.get("action") or body.get("verb") or "").strip()


def _token_mutation(path: str, body: dict | None) -> bool:
    """Browser-facing writes. A missing token is refused when Origin is set."""
    if path == "/api/shutdown":
        return True
    if path != "/api/run" or not isinstance(body, dict):
        return False
    action = _action_of(body)
    if action in ("handoff", "strip", "open_folder"):
        return True
    if action == "resume" and body.get("launch") is True:
        return True
    if action in ("recover", "crash-recover") and body.get("apply") is True:
        return True
    return False


def _rate_mutation(path: str, body: dict | None) -> bool:
    if path == "/api/shutdown":
        return True
    if not isinstance(body, dict):
        return False
    action = _action_of(body)
    if action in ("handoff", "strip", "export", "import", "convert", "open_folder"):
        return True
    if action == "resume" and body.get("launch") is True:
        return True
    if action in ("recover", "crash-recover") and body.get("apply") is True:
        return True
    return False


def _page_error_body(exc: BaseException) -> tuple[int, dict]:
    """PageError as HTTP. detail is the public sentence, never str(exc)."""
    kind = str(getattr(exc, "kind", "") or "BAD_REQUEST")
    cls = _PAGE_API.get(kind)
    if cls is None:
        code = kind if re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", kind) else "BAD_REQUEST"
        return 400, {
            "error": kind,
            "code": code,
            "message": "Request failed.",
            "detail": "Request failed.",
        }
    api = cls()
    mapped = to_http(api)
    status = int(mapped.get("status") or 400)
    raw = mapped.get("body") if isinstance(mapped.get("body"), dict) else {}
    code = raw.get("code") if isinstance(raw.get("code"), str) else ""
    message = raw.get("message") if isinstance(raw.get("message"), str) else ""
    if status >= 500 or code == "internal":
        pub = api.public() if isinstance(api, ApiError) else {}
        code = str(pub.get("code") or "BAD_REQUEST")
        message = str(pub.get("message") or "Request failed.")
        status = 404 if isinstance(api, NotFoundError) else 400
    if not _public_ok(message):
        message = "Request failed."
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,40}", code or ""):
        code = "BAD_REQUEST"
    return status, {
        "error": kind,
        "code": code,
        "message": message,
        "detail": message,
    }


def _internal_body(exc: BaseException) -> tuple[int, dict]:
    mapped = to_http(exc)
    status = int(mapped.get("status") or 500)
    raw = mapped.get("body") if isinstance(mapped.get("body"), dict) else {}
    code = raw.get("code") if isinstance(raw.get("code"), str) else "internal"
    message = raw.get("message") if isinstance(raw.get("message"), str) else "Something went wrong."
    if not _public_ok(message):
        message = "Something went wrong."
    if code != "internal" and not _public_ok(code):
        code = "internal"
    return status, {
        "error": "INTERNAL",
        "code": code,
        "message": message,
        "detail": message,
    }


def _inject_token(data: bytes, nonce: str) -> bytes:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    if "</head>" not in text or 'name="cm-token"' in text:
        return data
    tag = f'<meta name="cm-token" content="{nonce}">'
    return text.replace("</head>", tag + "</head>", 1).encode("utf-8")


def _ui_dir() -> Path:
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen) / "ui"
    return HERE / "ui"


def _emit(text: str) -> None:
    if sys.stdout is None:
        return
    try:
        print(text)
    except OSError:
        return


def _print(rec: dict) -> int:
    _emit(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0 if rec.get("kind") in ("OK", "TRUNCATED", "DRY_RUN", "VERIFIED", "ALREADY_OK",
                                    "LAUNCHED", "OPENWORK_FOCUS", "UNPROVEN", "NO_BAK",
                                    "BINARY_ABSENT", "UNMEASURED", "DO_NOT_REINGEST") else 2


def _ours(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/verbs", timeout=0.4) as res:
            body = json.loads(res.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, ValueError, TimeoutError):
        return False
    verbs = body.get("verbs") if isinstance(body, dict) else None
    return isinstance(verbs, list) and "find" in verbs and "resume" in verbs


def _open_page(port: int) -> None:
    url = f"http://127.0.0.1:{port}/"
    if os.name == "nt":
        edge_candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for ep in edge_candidates:
            if os.path.exists(ep):
                try:
                    import subprocess
                    subprocess.Popen([ep, f"--app={url}"])
                    return
                except Exception:
                    pass
    webbrowser.open(url)


def _alert(text: str) -> None:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, "Sessions", 0x10)
            return
        except OSError:
            pass
    _emit(text)


def _serve(port: int, open_browser: bool = False) -> int:
    ui = _ui_dir()
    boot_nonce = secrets.token_hex(24)
    rate_lock = threading.Lock()
    rate_hits: dict[str, list[float]] = {}

    def _check_rate(bucket: str, limit: int, window_s: float) -> bool:
        now = time.monotonic()
        with rate_lock:
            hits = rate_hits.setdefault(bucket, [])
            cutoff = now - window_s
            if hits and hits[0] <= cutoff:
                hits = [stamp for stamp in hits if stamp > cutoff]
                rate_hits[bucket] = hits
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    allow = {
        "/": ui / "index.html",
        "/index.html": ui / "index.html",
        "/index_classic.html": ui / "index_classic.html",
        "/app.js": ui / "app.js",
        "/app.css": ui / "app.css",
        "/cmsessions_fullscreen.png": ui / "cmsessions_fullscreen.png",
        "/cmsessions_calendar_fullscreen.png": ui / "cmsessions_calendar_fullscreen.png",
        "/cmsessions_calendar_week_fullscreen.png": ui / "cmsessions_calendar_week_fullscreen.png",
        "/accounts.html": ui / "accounts.html",
        "/accounts.js": ui / "accounts.js",
        "/accounts.css": ui / "accounts.css",
        "/settings.html": ui / "settings.html",
        "/settings.js": ui / "settings.js",
        "/settings.css": ui / "settings.css",
    }

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:
            return

        def _cors(self) -> None:
            origin = self.headers.get("Origin") or ""
            if origin.startswith(("http://127.0.0.1", "http://localhost")):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CM-Token")

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(30)

        def _send(self, code: int, body: bytes, content_type: str, close: bool = False) -> None:
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if close:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, rec: dict) -> None:
            raw = json.dumps(rec, ensure_ascii=False).encode("utf-8")
            self._send(code, raw, "application/json; charset=utf-8")

        def do_OPTIONS(self) -> None:
            self._send(204, b"", "text/plain")

        def do_GET(self) -> None:
            try:
                self._get()
            except Exception as exc:  # noqa: BLE001
                status, payload = _internal_body(exc)
                try:
                    self._json(status, payload)
                except Exception:
                    return

        def _get(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/api/verbs":
                self._json(200, {"verbs": _verb_names(), "harnesses": list(engine.HARNESSES)})
                return
            if path == "/api/homes":
                self._json(200, {"homes": engine.home_status()})
                return
            if path == "/api/places":
                self._json(200, engine.places())
                return
            file = allow.get(path)
            if file is None or not file.is_file():
                self._json(404, {"kind": "NOT_FOUND", "path": path})
                return
            if file.suffix == ".css":
                kind = "text/css"
            elif file.suffix == ".js":
                kind = "text/javascript"
            elif file.suffix == ".png":
                kind = "image/png"
            else:
                kind = "text/html; charset=utf-8"
            data = file.read_bytes()
            if kind.startswith("text/html"):
                data = _inject_token(data, boot_nonce)
            self._send(200, data, kind)

        def _token_matches(self) -> bool:
            tok = self.headers.get("X-CM-Token")
            if not isinstance(tok, str) or len(tok) != len(boot_nonce):
                return False
            return secrets.compare_digest(tok, boot_nonce)

        def _mutation_allowed(self) -> bool:
            tok = self.headers.get("X-CM-Token")
            matched = self._token_matches()
            if tok is not None and not matched:
                return False
            if (self.headers.get("Origin") or self.headers.get("Referer")) and not matched:
                return False
            if os.environ.get("CMSESSIONS_REQUIRE_TOKEN") == "1" and not matched:
                return False
            return True

        def _allow_rate(self, mutating: bool) -> bool:
            host = str(self.client_address[0]) if self.client_address else "local"
            if mutating:
                limit, window = _mutate_budget()
                return _check_rate(f"mutate:{host}", limit, window)
            return _check_rate(f"read:{host}", 240, 60.0)

        def _forbidden(self) -> None:
            self._json(403, {
                "error": "FORBIDDEN",
                "code": "FORBIDDEN",
                "message": "Invalid or missing session token.",
            })

        def _too_many(self) -> None:
            self._json(429, {
                "error": "RATE_LIMIT",
                "code": "RATE_LIMIT",
                "message": "Too many requests.",
                "detail": "Too many requests.",
            })

        def do_POST(self) -> None:
            try:
                self._post()
            except Exception as exc:  # noqa: BLE001
                status, payload = _internal_body(exc)
                try:
                    self._json(status, payload)
                except Exception:
                    return

        def _post(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/api/shutdown":
                if not self._mutation_allowed():
                    self._forbidden()
                    return
                if not self._allow_rate(True):
                    self._too_many()
                    return
                self._json(200, {"kind": "OK"})
                threading.Thread(target=httpd.shutdown, daemon=True).start()
                return
            if path != "/api/run":
                self._json(404, {"kind": "NOT_FOUND", "path": path})
                return
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError:
                length = -1
            if length < 0 or length > 1_000_000:
                self._send(400, json.dumps({
                    "error": "BAD_REQUEST", "detail": "body length",
                }).encode("utf-8"), "application/json; charset=utf-8", close=True)
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
            if _token_mutation(path, body) and not self._mutation_allowed():
                self._forbidden()
                return
            if not self._allow_rate(_rate_mutation(path, body)):
                self._too_many()
                return
            action = str(body.get("action") or body.get("verb") or "").strip()
            if action == "account_status":
                self._json(200, _account_status())
                return
            try:
                rec = _dispatch(action, body)
            except _error_types() as exc:
                status, payload = _page_error_body(exc)
                self._json(status, payload)
                return
            except Exception as exc:  # noqa: BLE001
                status, payload = _internal_body(exc)
                self._json(status, payload)
                return
            self._json(200, rec)

    class Bound(ThreadingHTTPServer):
        daemon_threads = True

    try:
        httpd = Bound((_SERVE_HOST, port), Handler)
    except OSError as exc:
        _emit(json.dumps({"kind": "BIND_FAILED", "port": port, "detail": str(exc)}))
        return 2
    def _prewarm() -> None:
        if os.environ.get("CMSESSIONS_NO_PREWARM") or os.environ.get("CMSESSIONS_TEST_MODE"):
            return
        try:
            engine.find(limit=250)
        except Exception:
            pass
    threading.Thread(target=_prewarm, daemon=True).start()

    if open_browser:
        def _later() -> None:
            for _ in range(50):
                if _ours(port):
                    _open_page(port)
                    return
                time.sleep(0.05)
        threading.Thread(target=_later, daemon=True).start()
    _emit(json.dumps({"kind": "OK", "url": f"http://127.0.0.1:{port}/"}))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        httpd.server_close()
    return 0


def _launch_gui(preferred: int = 8786) -> int:
    """Open the Sessions page. A page that is already up is focused, not started twice."""
    for port in range(preferred, preferred + 10):
        if _ours(port):
            _open_page(port)
            return 0
        rc = _serve(port, open_browser=True)
        if rc == 0:
            return 0
    _alert("Sessions could not open a local page on ports 8786–8795.")
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None and getattr(sys, "frozen", False) and len(sys.argv) <= 1:
        return _launch_gui()
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
    srv.add_argument("--port", type=int, default=_SERVE_PORT)
    srv.add_argument("--no-browser", action="store_true")
    sub.add_parser("verbs")
    sub.add_parser("desk")
    sub.add_parser("formats")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "find":
            return _print(_dispatch("find", {
                "query": args.query, "harness": args.harness,
                "cwd": args.cwd, "limit": args.limit,
            }))
        if args.cmd == "import":
            body = {"id": args.id}
            if args.out:
                body["out"] = args.out
            return _print(_dispatch("import", body))
        if args.cmd == "export":
            body = {"id": args.id}
            if args.out:
                body["out"] = args.out
            return _print(_dispatch("export", body))
        if args.cmd == "index":
            body = {"out": args.out} if args.out else {}
            return _print(_dispatch("index", body))
        if args.cmd == "recover":
            body = {"target": args.target, "apply": args.apply}
            if args.bak:
                body["bak"] = args.bak
            return _print(_dispatch("recover", body))
        if args.cmd == "resume":
            return _print(_dispatch("resume", {"id": args.id, "launch": args.launch}))
        if args.cmd == "scan":
            return _print(_dispatch("scan", {"store": args.store}))
        if args.cmd == "load":
            body = {"id": args.id}
            if args.store:
                body["store"] = args.store
            return _print(_dispatch("load", body))
        if args.cmd == "verbs":
            return _print({"schema": engine.SCHEMA, "verb": "verbs", "kind": "OK",
                           "gate": {"verbs": _verb_names(), "harnesses": list(engine.HARNESSES)},
                           "legal_omitted": 0})
        if args.cmd == "serve":
            return _serve(args.port, open_browser=not args.no_browser)
        if args.cmd == "desk":
            import desk
            return desk.main()
        if args.cmd == "formats":
            return _print(_dispatch("formats", {}))
    except _error_types() as exc:
        kind = getattr(exc, "kind", "BAD_ACTION")
        print(json.dumps({"schema": engine.SCHEMA, "verb": args.cmd, "kind": kind,
                          "gate": {"detail": str(exc)}, "legal_omitted": int(kind == "LEGAL_OMITTED")}))
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
