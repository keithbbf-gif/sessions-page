"""Project groups from the last path segment of each hit's cwd.

No painted counts. The desk may mount an empty frame and ignore refresh.
"""

from __future__ import annotations


def _project_name(hit: dict) -> str:
    raw = hit.get("cwd")
    if raw is None:
        return "No project"
    text = str(raw).strip().replace("/", "\\").rstrip("\\")
    if not text:
        return "No project"
    return text.split("\\")[-1] or "No project"


def groups(hits) -> list[tuple[str, list]]:
    """Group hit dicts by the last segment of cwd.

    A blank cwd is "No project". Names sort ascending. Hits in a name
    stay in input order. Non-dicts are skipped.
    """
    buckets: dict[str, list] = {}
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        name = _project_name(hit)
        buckets.setdefault(name, []).append(hit)
    return [(name, buckets[name]) for name in sorted(buckets)]


def build(parent, desk) -> None:
    """Mount an empty frame. It is not packed or gridded, so it stays hidden."""
    import tkinter as tk

    tk.Frame(parent)
    return None


def refresh(desk, hits) -> None:
    """No-op."""
    return None
