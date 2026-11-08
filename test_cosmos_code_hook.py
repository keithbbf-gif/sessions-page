"""The Sessions hook has no port and does not bind a socket."""

from __future__ import annotations

import socket
from unittest.mock import patch

import cosmos_code_hook as hook


def test_descriptor_in_process() -> None:
    desc = hook.descriptor()
    assert desc["port"] is None
    assert desc["writes_live"] is False
    assert desc["via"] == "in-process"
    assert desc["name"] == "sessions"
    assert desc["module"] == "plugin_api"
    assert desc["window"] == "desk"
    assert desc["verbs"] == ["find", "load", "resume", "formats"]
    assert hook.SCHEMA == "cmsessions-cosmos-code-hook/1"


def test_open_plugin_returns_dict_without_bind() -> None:
    binds: list = []
    real = socket.socket

    def _socket(*args, **kwargs):
        sock = real(*args, **kwargs)
        original = sock.bind

        def bind(*bind_args, **bind_kwargs):
            binds.append(bind_args)
            return original(*bind_args, **bind_kwargs)

        sock.bind = bind
        return sock

    with patch("socket.socket", _socket):
        got = hook.open_plugin()
    assert isinstance(got, dict)
    assert binds == []


def main() -> int:
    test_descriptor_in_process()
    test_open_plugin_returns_dict_without_bind()
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
