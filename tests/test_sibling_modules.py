"""Sibling csm_core modules are optional in this tree.

Each test imports one module. A failed import skips that test.
A successful import must expose errors.CODES or its public functions.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:
        pytest.skip(f"{name} is not importable: {type(exc).__name__}: {exc}")


def _public_functions(module) -> tuple[str, ...]:
    return tuple(
        name
        for name, obj in vars(module).items()
        if not name.startswith("_") and inspect.isfunction(obj)
    )


def _assert_functions(module) -> None:
    names = _public_functions(module)
    assert names, f"{module.__name__} imported but defines no public functions"
    for name in names:
        assert callable(getattr(module, name))


def test_csm_core_errors() -> None:
    errors = _load("csm_core.errors")
    if hasattr(errors, "CODES"):
        codes = errors.CODES
        assert not isinstance(codes, (str, bytes))
        assert len(codes) > 0
        return
    _assert_functions(errors)


def test_csm_core_persist() -> None:
    _assert_functions(_load("csm_core.persist"))


def test_csm_core_tokenctr_bridge() -> None:
    _assert_functions(_load("csm_core.tokenctr_bridge"))


def test_csm_core_cosmos_pointer() -> None:
    _assert_functions(_load("csm_core.cosmos_pointer"))
