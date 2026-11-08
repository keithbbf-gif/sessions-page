#!/usr/bin/env python3
"""Frozen product_root writes beside the exe, not next to engine.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402


def main() -> int:
    engine_dir = Path(engine.__file__).resolve().parent
    if getattr(sys, "frozen", False):
        print("FAIL frozen is already set")
        return 1
    got = engine.product_root()
    if got != engine_dir:
        print(f"FAIL unfrozen product_root {got} != {engine_dir}")
        return 1
    print("ok  unfrozen product_root is the directory that contains engine.py")

    engine_var = engine_dir / "var"
    existed = engine_var.exists()
    with tempfile.TemporaryDirectory(prefix="sesspage_frozen_") as tmp:
        exe = Path(tmp) / "dist" / "sessions_page.exe"
        sys.frozen = True
        sys.executable = str(exe)
        parent = exe.resolve().parent
        got = engine.product_root()
        if got != parent:
            print(f"FAIL frozen product_root {got} != {parent}")
            return 1
        print("ok  frozen product_root is the exe parent")

        made = engine.var_dir()
        if made != parent / "var" or not made.is_dir():
            print(f"FAIL var_dir {made}")
            return 1
        if made.resolve() == engine_var.resolve():
            print("FAIL var_dir wrote beside engine.py")
            return 1
        if not existed and engine_var.exists():
            print("FAIL var directory appeared next to engine.py")
            return 1
        print("ok  var_dir creates <exe parent>/var and not beside engine.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
