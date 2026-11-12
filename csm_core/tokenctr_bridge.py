"""Read-only Token Center account status and usage gauge.

Network is used only when CMSESSIONS_TOKENCTR_URL is an http(s) loopback
base URL. The call is a single GET of ``{base}/account/status``. This module
does not charge, create an account, send credentials, or return API keys.
usage_gauge copies used and limit only when that response measures them.
account_status returns status, reason, account_label, used, and limit.
account_label is null when the URL is unset or blank. Email addresses are
not copied from secret files.

When CMSESSIONS_TOKENCTR_FIXTURE is ``1``, account_status and usage_gauge
return a fixed dict and do not open a socket. That path is for tests only.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .tokenctr_types import account_status_view

_ENV = "CMSESSIONS_TOKENCTR_URL"
_FIXTURE_ENV = "CMSESSIONS_TOKENCTR_FIXTURE"
_TIMEOUT_S = 3.0
_MAX_BYTES = 65536
_MAX_URL = 512
_STATUS_SUFFIX = "/account/status"

# Path segments that must never be requested. Status is not a mutation.
_BLOCKED_SEGMENTS = frozenset({
    "charge",
    "spend",
    "purchase",
    "signup",
    "sign-up",
    "register",
    "create",
    "checkout",
    "debit",
    "billing",
    "payment",
    "subscribe",
    "upgrade",
})

_SECRET_NAME_PARTS = (
    "apikey",
    "apisecret",
    "secret",
    "password",
    "passwd",
    "authorization",
    "credential",
    "privatekey",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "bearertoken",
    "clientsecret",
    "signingkey",
    "authtoken",
    "sessionkey",
    "sessiontoken",
)


class _Drop:
    """Marks a value that must not appear in the returned dict."""


_DROP = _Drop()


def _unavailable(reason: str) -> dict[str, object]:
    """Status dict. Reason is a short code, never an exception or body."""
    return {"status": "unavailable", "reason": reason}


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    reason = getattr(exc, "reason", None)
    if reason is exc:
        return False
    if isinstance(reason, TimeoutError):
        return True
    if isinstance(reason, str) and "timed out" in reason.lower():
        return True
    return False


def _close_quiet(exc: urllib.error.HTTPError) -> None:
    """Release the error socket. Do not read or log the body."""
    try:
        exc.close()
    except Exception:
        return


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """Do not follow redirects. A redirect could leave loopback or mutate."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _secret_key(name: str) -> bool:
    norm = "".join(ch for ch in name.lower() if ch.isalnum())
    if not norm:
        return True
    return any(part in norm for part in _SECRET_NAME_PARTS)


def _looks_like_secret(value: str) -> bool:
    text = value.strip()
    if len(text) < 20:
        return False
    if text[:7].lower() == "bearer ":
        return True
    head = text[:4]
    if head[:3] == "sk-" or head == "xai-" or head == "AIza" or text.startswith("AQ."):
        return True
    return False


def _env_base() -> str | None:
    """Return the configured base, an empty string when blank, or None when unusable."""
    raw = os.environ.get(_ENV)
    if raw is None:
        return None
    text = str(raw).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    if not text:
        return ""
    if len(text) > _MAX_URL:
        return None
    return text


def _is_loopback(host: str) -> bool:
    name = host.strip().lower().rstrip(".")
    if name == "localhost":
        return True
    try:
        return bool(ipaddress.ip_address(name).is_loopback)
    except ValueError:
        return False


def _blocked_path(path: str) -> bool:
    for segment in path.split("/"):
        if segment.lower() in _BLOCKED_SEGMENTS:
            return True
    return False


def _status_url(base: str) -> str | None:
    parts = urllib.parse.urlsplit(base)
    if parts.scheme not in ("http", "https"):
        return None
    if parts.username or parts.password or parts.query or parts.fragment:
        return None
    host = parts.hostname
    if not host or not _is_loopback(host):
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    if port == 0:
        return None
    path = parts.path or ""
    if _blocked_path(path):
        return None
    trimmed = path.rstrip("/")
    if trimmed.lower().endswith(_STATUS_SUFFIX) or trimmed.lower().endswith("/status"):
        status_path = trimmed if trimmed.startswith("/") else "/" + trimmed
    else:
        status_path = (trimmed.rstrip("/") + _STATUS_SUFFIX) if trimmed else _STATUS_SUFFIX
    if _blocked_path(status_path):
        return None
    host_out = f"[{host}]" if ":" in host else host
    netloc = f"{host_out}:{port}" if port is not None else host_out
    url = urllib.parse.urlunsplit((parts.scheme, netloc, status_path, "", ""))
    check = urllib.parse.urlsplit(url)
    if check.hostname is None or not _is_loopback(check.hostname):
        return None
    if check.scheme not in ("http", "https") or check.username or check.password:
        return None
    return url


def _sanitize(value: object, depth: int = 0) -> object:
    if depth > 6:
        return _DROP
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return _DROP
        return value
    if isinstance(value, str):
        if _looks_like_secret(value):
            return _DROP
        if len(value) > 512:
            return value[:512]
        return value
    if isinstance(value, list):
        cleaned: list[object] = []
        for item in value[:32]:
            child = _sanitize(item, depth + 1)
            if child is _DROP:
                continue
            cleaned.append(child)
        return cleaned
    if isinstance(value, dict):
        cleaned_dict: dict[str, object] = {}
        for key, item in list(value.items())[:64]:
            if not isinstance(key, str) or _secret_key(key):
                continue
            child = _sanitize(item, depth + 1)
            if child is _DROP:
                continue
            cleaned_dict[key] = child
        return cleaned_dict
    return _DROP


def _get_status(url: str) -> dict[str, object]:
    # Re-check immediately before the only network call. One attempt, no retry.
    if _status_url(url) != url:
        return _unavailable("not_local")
    req = urllib.request.Request(
        url,
        data=None,
        headers={"Accept": "application/json"},
        method="GET",
    )
    if req.get_method() != "GET" or req.data is not None:
        return _unavailable("refused")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _RefuseRedirect(),
    )
    try:
        with opener.open(req, timeout=_TIMEOUT_S) as res:
            code = res.getcode() or 0
            if code != 200:
                return _unavailable("http_error")
            raw = res.read(_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        _close_quiet(exc)
        if 300 <= exc.code < 400:
            return _unavailable("redirect_refused")
        return _unavailable("http_error")
    except urllib.error.URLError as exc:
        if _is_timeout(exc):
            return _unavailable("timeout")
        return _unavailable("unreachable")
    except TimeoutError:
        return _unavailable("timeout")
    except http.client.HTTPException:
        return _unavailable("http_error")
    except Exception as exc:
        if _is_timeout(exc):
            return _unavailable("timeout")
        return _unavailable("unreachable")
    if len(raw) > _MAX_BYTES:
        return _unavailable("too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return _unavailable("bad_json")
    cleaned = _sanitize(payload)
    if not isinstance(cleaned, dict):
        return _unavailable("bad_payload")
    status = cleaned.get("status")
    if not isinstance(status, str) or not status.strip() or len(status) > 64:
        cleaned["status"] = "ok"
    else:
        cleaned["status"] = status.strip()
    return cleaned


def _fixture_enabled() -> bool:
    raw = os.environ.get(_FIXTURE_ENV)
    if raw is None:
        return False
    return str(raw).strip() == "1"


def _fixture_status() -> dict[str, object]:
    """Fixed hermetic reading. A new dict so callers cannot mutate the next call."""
    return {
        "status": "ok",
        "reason": None,
        "account_label": "fixture",
        "used": 0,
        "limit": 1,
    }


def _account_report() -> dict[str, object]:
    """Sanitized status document for the gauge. Not the public five-key view.

    No socket is opened when the URL is unset or blank. Secret files are not read.
    """
    raw = os.environ.get(_ENV)
    if raw is None or not str(raw).strip():
        return {"status": "unavailable", "reason": "not_configured"}
    base = _env_base()
    if base == "":
        return {"status": "unavailable", "reason": "not_configured"}
    if base is None:
        return {"status": "unavailable", "reason": "not_local"}
    url = _status_url(base)
    if url is None:
        return {"status": "unavailable", "reason": "not_local"}
    return _get_status(url)


def account_status() -> dict[str, object]:
    """Return status, reason, account_label, used, and limit.

    Does not charge or create an account. account_label is null when
    ``CMSESSIONS_TOKENCTR_URL`` is unset or blank, and no socket is opened.
    Email addresses are not copied from secret files. When
    ``CMSESSIONS_TOKENCTR_FIXTURE`` is ``1``, returns the fixed test reading
    and does not open a socket. Any other URL is used only if it is loopback.
    """
    if _fixture_enabled():
        # Test fixture only. Do not reshape this through account_status_view.
        return _fixture_status()
    raw = os.environ.get(_ENV)
    if raw is None or not str(raw).strip():
        return account_status_view(None, configured=False)
    base = _env_base()
    if base == "":
        return account_status_view(None, configured=False)
    return account_status_view(_account_report(), configured=True)


_UNAVAILABLE = {"used": None, "limit": None, "status": "unavailable"}

# Names that are measurements. A missing name stays null. It is never filled in.
_USED_KEYS = ("used", "tokens_used", "usage_used", "total_tokens")
_LIMIT_KEYS = ("limit", "token_limit", "usage_limit")
_PASS_KEYS = (
    "tokens_in",
    "tokens_out",
    "prompt_tokens",
    "completion_tokens",
    "input_tokens",
    "output_tokens",
    "calls",
    "unpriced_calls",
    "usd",
    "usd_spent_today",
    "measured_usd",
    "credits_face_usd",
    "free_used_face_usd",
    "free_quota_face_usd",
    "total_tokens",
    "tokens_used",
)
_NEST_KEYS = ("usage", "gauge", "meter")


def _finite_number(value: object) -> int | float | None:
    """JSON numbers only. Booleans and strings are not measurements."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    return None


def _gauge_sources(report: dict[str, object]) -> list[dict[str, object]]:
    sources = [report]
    for key in _NEST_KEYS:
        child = report.get(key)
        if isinstance(child, dict):
            sources.append(child)
    return sources


def _first_number(sources: list[dict[str, object]], keys: tuple[str, ...]) -> int | float | None:
    for source in sources:
        for key in keys:
            if key not in source:
                continue
            number = _finite_number(source.get(key))
            if number is not None:
                return number
    return None


def _pair_sum(source: dict[str, object], left: str, right: str) -> int | float | None:
    inn = _finite_number(source.get(left))
    out = _finite_number(source.get(right))
    if inn is None or out is None:
        return None
    return inn + out


def _measured_used(sources: list[dict[str, object]]) -> int | float | None:
    found = _first_number(sources, _USED_KEYS)
    if found is not None:
        return found
    for source in sources:
        tokens = source.get("tokens")
        if isinstance(tokens, dict):
            paired = _pair_sum(tokens, "in", "out")
            if paired is None:
                paired = _pair_sum(tokens, "input", "output")
            if paired is not None:
                return paired
        number = _finite_number(tokens)
        if number is not None:
            return number
        paired = _pair_sum(source, "tokens_in", "tokens_out")
        if paired is None:
            paired = _pair_sum(source, "prompt_tokens", "completion_tokens")
        if paired is None:
            paired = _pair_sum(source, "input_tokens", "output_tokens")
        if paired is not None:
            return paired
    return None


def _measured_fields(sources: list[dict[str, object]]) -> dict[str, object]:
    found: dict[str, object] = {}
    for source in sources:
        for key in _PASS_KEYS:
            if key in found or key not in source:
                continue
            number = _finite_number(source.get(key))
            if number is not None:
                found[key] = number
        tokens = source.get("tokens")
        if not isinstance(tokens, dict):
            continue
        for src_key, dest in (
            ("in", "tokens_in"),
            ("out", "tokens_out"),
            ("input", "tokens_in"),
            ("output", "tokens_out"),
        ):
            if dest in found or src_key not in tokens:
                continue
            number = _finite_number(tokens.get(src_key))
            if number is not None:
                found[dest] = number
    return found


def usage_gauge() -> dict[str, object]:
    """Return measured usage, or used and limit null with status unavailable.

    When ``CMSESSIONS_TOKENCTR_FIXTURE`` is ``1``, returns the same fixed
    test dict as ``account_status`` and does not open a socket. No socket is
    opened when ``CMSESSIONS_TOKENCTR_URL`` is unset or blank. A configured
    loopback status document is read, not invented. used and limit stay null
    when that document does not measure them.
    """
    if _fixture_enabled():
        return _fixture_status()
    raw = os.environ.get(_ENV)
    if raw is None or not str(raw).strip():
        return dict(_UNAVAILABLE)
    report = _account_report()
    if not isinstance(report, dict) or report.get("status") == "unavailable":
        out = dict(_UNAVAILABLE)
        if isinstance(report, dict):
            reason = report.get("reason")
            if isinstance(reason, str) and reason.isidentifier() and len(reason) <= 32:
                out["reason"] = reason
        return out
    sources = _gauge_sources(report)
    used = _measured_used(sources)
    limit = _first_number(sources, _LIMIT_KEYS)
    fields = _measured_fields(sources)
    if used is None and limit is None and not fields:
        return dict(_UNAVAILABLE)
    measured: dict[str, object] = {"used": used, "limit": limit, "status": "measured"}
    for key, number in fields.items():
        if key not in ("used", "limit", "status"):
            measured[key] = number
    return measured


__all__ = ["account_status", "usage_gauge"]
