"""Map an exception to an HTTP status and a public body.

``to_http`` returns ``{"status": int, "body": {"code": str, "message": str}}``.
``BadVerbError``, ``BadJsonError``, and ``NotFoundError`` keep the public
code and message from ``csm_core.errors``. Every other exception is status
500, code ``internal``, message ``Something went wrong.``

Tracebacks, exception arguments, and chained causes are not copied.
"""

from __future__ import annotations

import re

from .errors import ApiError

_CODE_STATUS: dict[str, int] = {
    "BAD_VERB": 400,
    "BAD_JSON": 400,
    "NOT_FOUND": 404,
}

_CODE_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")
_TRACE_MARK = "Traceback"
_INTERNAL_BODY = {"code": "internal", "message": "Something went wrong."}


def to_http(exc: BaseException) -> dict[str, int | dict[str, str]]:
    """Return a status and a body that has only code and message."""
    body = _known_body(exc)
    if body is None:
        return {"status": 500, "body": dict(_INTERNAL_BODY)}
    return {"status": _CODE_STATUS.get(body["code"], 400), "body": body}


def _known_body(exc: BaseException) -> dict[str, str] | None:
    if not isinstance(exc, ApiError):
        return None
    try:
        raw = exc.public()
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    code = raw.get("code")
    message = raw.get("message")
    if not isinstance(code, str) or not isinstance(message, str):
        return None
    if not _CODE_TOKEN.fullmatch(code) or not _safe_public(message):
        return None
    return {"code": code, "message": message}


def _safe_public(text: str) -> bool:
    if not text or len(text) > 200:
        return False
    if _TRACE_MARK in text or "\n" in text or "\r" in text:
        return False
    stripped = text.lstrip()
    if stripped.startswith("File ") or stripped.startswith('File "'):
        return False
    return True


__all__ = ["to_http"]
