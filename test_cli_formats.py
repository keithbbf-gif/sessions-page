#!/usr/bin/env python3
"""CLI check for `formats`. Does not open the desk and does not bind a port."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import sessions_page  # noqa: E402


def _report(text: str) -> None:
    """Print the result. A windowless process may have no stdout."""
    if sys.stdout is not None:
        try:
            print(text)
            return
        except OSError:
            pass
    err = sys.stderr
    if err is not None:
        try:
            err.write(text + "\n")
            return
        except OSError:
            pass
    out = HERE / "var" / "cli_formats_result.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")


def _formats_stdout() -> tuple[int, str]:
    """Run the formats command and capture what it prints."""
    sink = io.StringIO()
    previous = sys.stdout
    sys.stdout = sink
    try:
        code = sessions_page.main(["formats"])
    finally:
        sys.stdout = previous
    return code, sink.getvalue()


def main() -> int:
    # main(["desk"]) is not called. That path opens a window.
    try:
        code, text = _formats_stdout()
    except SystemExit as exc:
        _report(f"FAIL formats not accepted ({exc.code})")
        return 1
    if not text.strip():
        _report("FAIL formats produced no stdout")
        return 1
    rec = json.loads(text)
    gate = rec.get("gate")
    n = gate.get("n") if isinstance(gate, dict) else None
    ok = (
        code == 0
        and rec.get("kind") == "OK"
        and isinstance(gate, dict)
        and gate.get("schema") == "cmsessions-format-index/1"
        and isinstance(n, int)
        and not isinstance(n, bool)
        and n > 0
    )
    if not ok:
        _report(f"FAIL formats {rec.get('kind')!r} n={n!r}")
        return 1
    _report(f"ok formats n={n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
