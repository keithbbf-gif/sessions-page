#!/usr/bin/env python3
"""Hermetic checks for the in-process sessions plug. No port and no live walk."""
from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _refusal(fn) -> bool:
    try:
        rec = fn()
    except Exception as exc:  # noqa: BLE001 — typed refusal or a hard failure
        return bool(getattr(exc, "kind", ""))
    if not isinstance(rec, dict):
        return False
    kind = str(rec.get("kind") or rec.get("error") or "")
    return kind not in ("", "OK")


def main() -> int:
    results = []

    def check(label, fn):
        try:
            ok = bool(fn())
            results.append((label, ok, "" if ok else "returned false"))
        except Exception as exc:  # noqa: BLE001 — one line per check
            results.append((label, False, f"{type(exc).__name__}: {exc}"))

    before_threads = {t.ident for t in threading.enumerate()}
    import plugin_api
    started = {t.ident for t in threading.enumerate()} - before_threads
    check("import skips tkinter", lambda: "tkinter" not in sys.modules)
    check("import does not start a server",
          lambda: not started and "http.server" not in sys.modules
          and "socketserver" not in sys.modules and "sessions_page" not in sys.modules)
    check("schema is cmsessions-plugin/1", lambda: plugin_api.SCHEMA == "cmsessions-plugin/1")

    temp_before = set(Path(tempfile.gettempdir()).iterdir())
    snap = plugin_api.snapshot()
    temp_after = set(Path(tempfile.gettempdir()).iterdir())
    check("snapshot port is None and window is desk",
          lambda: "port" in snap and snap["port"] is None and snap.get("window") == "desk"
          and snap.get("kind") == "OK" and snap.get("engine") == "builds/sessions-page")
    check("snapshot does not create a temp directory", lambda: temp_before == temp_after)
    check("snapshot leaves n null until a walk",
          lambda: "crash-recover" in (snap.get("verbs") or [])
          and all(row.get("n") is None for row in snap.get("homes") or []))

    def bad_call():
        import socket
        events = []
        orig = socket.socket

        class Watching(orig):
            def bind(self, address):
                events.append(("bind", address))
                return super().bind(address)

            def listen(self, backlog=0):
                events.append(("listen", backlog))
                return super().listen(backlog)

        socket.socket = Watching
        try:
            refused = _refusal(lambda: plugin_api.call({"action": "nope"}))
            refused = refused and _refusal(lambda: plugin_api.call({}))
            refused = refused and _refusal(lambda: plugin_api.call([]))
        finally:
            socket.socket = orig
        return refused and not events

    check("bad call is a typed error and does not listen", bad_call)
    import formats
    fmt = plugin_api.formats()
    check("formats returns the catalog",
          lambda: fmt == formats.catalog()
          and fmt.get("schema") == formats.SCHEMA
          and fmt.get("n") == len(formats.CATALOG))
    check("call and snapshot do not start a server",
          lambda: "tkinter" not in sys.modules and "http.server" not in sys.modules)

    failed = [label for label, ok, _detail in results if not ok]
    for label, ok, detail in results:
        print(("ok  " if ok else "FAIL") + " " + label + (f" — {detail}" if detail else ""))
    print(f"{len(results) - len(failed)}/{len(results)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
