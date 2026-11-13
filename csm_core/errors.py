"""Typed API errors for a bad verb, bad JSON, a missing resource, and resume.

Each error has a stable code and a short public message. The public
message is the class constant. Caller text, transcript text, and chained
tracebacks are not part of it.

FileNotFoundError, PermissionError, and OSError with winerror 10053
map to missing_file, access_denied, and connection_aborted.
"""

from __future__ import annotations

import re
from typing import ClassVar, Final, Mapping

BAD_VERB: Final[str] = "BAD_VERB"
BAD_JSON: Final[str] = "BAD_JSON"
NOT_FOUND: Final[str] = "NOT_FOUND"
HARNESS_MISSING: Final[str] = "harness_missing"
LEGAL_OMITTED: Final[str] = "legal_omitted"
NOT_RESUMABLE: Final[str] = "not_resumable"
MISSING_FILE: Final[str] = "missing_file"
ACCESS_DENIED: Final[str] = "access_denied"
CONNECTION_ABORTED: Final[str] = "connection_aborted"

# WSAECONNABORTED. Match OSError.winerror, not errno.
_WINERROR_CONNECTION_ABORTED: Final[int] = 10053

_TRACE_MARK = "Traceback (most recent call last)"
_PROFILE_ROOT = re.compile(
    r"(?i)(?:"
    r"(?:\\\\\?\\)?[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s:*?\"<>|]+"
    r"|/(?:Users|home)/[^/\s:*?\"<>|]+"
    r"|~[\\/]"
    r"|%(?:USERPROFILE|HOME)%"
    r"|\$(?:HOME|USERPROFILE|\{HOME\}|\{USERPROFILE\})"
    r")"
)

_OS_PUBLIC: Final[Mapping[str, str]] = {
    MISSING_FILE: "Missing file.",
    ACCESS_DENIED: "Access denied.",
    CONNECTION_ABORTED: "Connection aborted.",
}


class ApiError(Exception):
    """Base. Raise a subclass. str() is the public message only."""

    code: ClassVar[str] = ""
    public_message: ClassVar[str] = ""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        if type(self) is ApiError:
            raise TypeError(
                "raise BadVerbError, BadJsonError, NotFoundError, "
                "HarnessMissingError, LegalOmittedError, or NotResumableError"
            )
        text = _public_text(type(self).public_message)
        self.code = type(self).code
        self.public_message = text
        super().__init__(text)
        self.__cause__ = None
        self.__suppress_context__ = True

    def __str__(self) -> str:
        return self.public_message

    def public(self) -> dict[str, str]:
        return {"code": self.code, "message": self.public_message}


class BadVerbError(ApiError):
    """The verb is missing or not one this API accepts."""

    code: ClassVar[str] = BAD_VERB
    public_message: ClassVar[str] = "Unknown verb."


class BadJsonError(ApiError):
    """The request body is not a JSON object this API can read."""

    code: ClassVar[str] = BAD_JSON
    public_message: ClassVar[str] = "Invalid JSON."


class NotFoundError(ApiError):
    """The session, path, or other named resource is not there."""

    code: ClassVar[str] = NOT_FOUND
    public_message: ClassVar[str] = "Not found."


class HarnessMissingError(ApiError):
    """Resume cannot start because that harness is not installed.

    Arguments are ignored. The public message never includes transcript text.
    """

    code: ClassVar[str] = HARNESS_MISSING
    public_message: ClassVar[str] = "Harness is missing."

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        super().__init__()


class LegalOmittedError(ApiError):
    """A legal session is omitted and is not resumed.

    Arguments are ignored. The public message never includes transcript text.
    """

    code: ClassVar[str] = LEGAL_OMITTED
    public_message: ClassVar[str] = "Legal session omitted."

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        super().__init__()


class NotResumableError(ApiError):
    """This session has no resume command.

    Arguments are ignored. The public message never includes transcript text.
    """

    code: ClassVar[str] = NOT_RESUMABLE
    public_message: ClassVar[str] = "Session cannot be resumed."

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        super().__init__()


def _public_text(text: str) -> str:
    """Keep a short sentence. Drop a traceback if one was pasted in."""
    if not isinstance(text, str):
        return "Request failed."
    if _TRACE_MARK in text:
        text = text.split(_TRACE_MARK, 1)[0]
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("File ") or line.startswith("  File "):
            break
        if stripped:
            kept.append(stripped)
    out = " ".join(kept).strip()
    return out or "Request failed."


def stable_code(exc: BaseException) -> str | None:
    """Map a disk or socket OS error to a stable code, else None.

    FileNotFoundError and PermissionError are OSError subclasses, so
    they are matched before winerror 10053.
    """
    if isinstance(exc, FileNotFoundError):
        return MISSING_FILE
    if isinstance(exc, PermissionError):
        return ACCESS_DENIED
    winerror = getattr(exc, "winerror", None)
    if isinstance(exc, OSError) and winerror == _WINERROR_CONNECTION_ABORTED:
        return CONNECTION_ABORTED
    return None


def public_body(exc: BaseException) -> Mapping[str, str]:
    """Client body. A non-API error stays a fixed line with no traceback."""
    if isinstance(exc, ApiError):
        return exc.public()
    code = stable_code(exc)
    if code is not None:
        return {"code": code, "message": _OS_PUBLIC[code]}
    return {"code": "INTERNAL", "message": "Internal error."}


def _caller_text(exc: BaseException) -> str:
    """String arguments only. Skip the traceback object and any cause."""
    parts: list[str] = []
    for arg in exc.args:
        if isinstance(arg, str):
            parts.append(arg)
    return " ".join(parts)


def _replace_profile_paths(text: str) -> str:
    """Replace a user-profile path with a fixed phrase. Leave other words."""
    guard = 0
    while guard < 32:
        guard += 1
        match = _PROFILE_ROOT.search(text)
        if match is None:
            break
        end = match.end()
        while end < len(text) and text[end] not in "\r\n\"'<>|*?":
            end += 1
        if (
            end > match.end()
            and text[end - 1] in ".!?"
            and (end == len(text) or text[end].isspace() or text[end] in ",;:")
        ):
            end -= 1
        text = f"{text[: match.start()]} a local file {text[end:]}"
    else:
        return ""
    return " ".join(text.split())


def _one_safe_sentence(text: str) -> str:
    """One sentence, with no traceback and no user-profile path."""
    text = _replace_profile_paths(text)
    text = " ".join(text.split()).strip(" \t-:,;\"'")
    if not text or text == "a local file":
        return "Request failed."
    if _PROFILE_ROOT.search(text) or "traceback" in text.lower():
        return "Request failed."
    if re.search(r"(?i)\bFile \".*\", line \d+", text):
        return "Request failed."
    for index, char in enumerate(text):
        if char in ".!?":
            text = text[: index + 1]
            break
    else:
        text = f"{text}."
    text = " ".join(text.split()).strip()
    if not text.endswith((".", "!", "?")) or text == "a local file.":
        return "Request failed."
    if _PROFILE_ROOT.search(text) or "traceback" in text.lower():
        return "Request failed."
    return text


def public_message(exc: BaseException) -> str:
    """One sentence for a caller. No traceback and no user-profile path."""
    if not isinstance(exc, BaseException):
        return "Request failed."
    if isinstance(exc, ApiError):
        raw = exc.public_message if isinstance(exc.public_message, str) else ""
        return _one_safe_sentence(raw)
    code = stable_code(exc)
    if code is not None:
        return _one_safe_sentence(_OS_PUBLIC[code])
    return _one_safe_sentence(_public_text(_caller_text(exc)))


# Every code defined in this module, mapped to its public message.
CODES: Final[Mapping[str, str]] = {
    BAD_VERB: BadVerbError.public_message,
    BAD_JSON: BadJsonError.public_message,
    NOT_FOUND: NotFoundError.public_message,
    HARNESS_MISSING: HarnessMissingError.public_message,
    LEGAL_OMITTED: LegalOmittedError.public_message,
    NOT_RESUMABLE: NotResumableError.public_message,
    MISSING_FILE: _OS_PUBLIC[MISSING_FILE],
    ACCESS_DENIED: _OS_PUBLIC[ACCESS_DENIED],
    CONNECTION_ABORTED: _OS_PUBLIC[CONNECTION_ABORTED],
    "INTERNAL": "Internal error.",
}


__all__ = [
    "ACCESS_DENIED",
    "BAD_JSON",
    "BAD_VERB",
    "CODES",
    "CONNECTION_ABORTED",
    "HARNESS_MISSING",
    "LEGAL_OMITTED",
    "MISSING_FILE",
    "NOT_FOUND",
    "NOT_RESUMABLE",
    "ApiError",
    "BadJsonError",
    "BadVerbError",
    "HarnessMissingError",
    "LegalOmittedError",
    "NotFoundError",
    "NotResumableError",
    "public_body",
    "public_message",
    "stable_code",
]
