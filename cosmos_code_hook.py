"""In-process Sessions plugin for COSMOS CODE.

The standalone app is the desk window and does not need this hook.
COSMOS calls the same engine through cosmos_session_tools_kit.py.
This descriptor is the Cosmos Code plug. It does not open a port,
start a process, or write live/. The applied cosmos_code tree has
no plugin list to extend.
"""

from __future__ import annotations

SCHEMA = "cmsessions-cosmos-code-hook/1"


def descriptor() -> dict:
    """Name the Sessions plugin. It stays in-process on the desk."""
    return {
        "schema": SCHEMA,
        "name": "sessions",
        "via": "in-process",
        "module": "plugin_api",
        "port": None,
        "window": "desk",
        "writes_live": False,
        "verbs": ["find", "load", "resume", "formats"],
    }


def open_plugin() -> dict:
    """Return plugin_api.snapshot(). A missing module is ENGINE_MISSING."""
    try:
        import plugin_api
    except ImportError:
        return {
            "schema": SCHEMA,
            "kind": "ENGINE_MISSING",
            "module": "plugin_api",
        }
    return plugin_api.snapshot()
