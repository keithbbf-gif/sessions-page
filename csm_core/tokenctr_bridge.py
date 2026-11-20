"""Read-only Token Center account status and usage gauge.

Network is used only for an http(s) loopback base URL or the explicit live
host ``https://api.tokenctr.com``. Paths are limited to ``/v1/account``,
``/v1/usage``, ``/v1/logs``, and ``/v1/statement``. Any other host is refused
with reason ``not_local``. This module does not charge, create an account,
or return API keys.

``CMSESSIONS_TOKENCTR_URL`` or ``SOLARO_TOKENCTR_URL`` sets the base. When
neither is set to a usable URL and ``SOLARO_TOKENCTR_LIVE=1`` or
``CMSESSIONS_TOKENCTR_LIVE=1``, the base is ``https://api.tokenctr.com``.
A Bearer token is read from ``TOKENCTR_API_KEY`` only for that host and is
never stored or echoed. HTTP 401 and 403 from an allowlisted host, including
the live host, return ``reason="auth_required"``.

When ``CMSESSIONS_TOKENCTR_FIXTURE`` is ``1``, ``account_status`` and
``usage_gauge`` return a fixed dict and do not open a socket.
"""


from __future__ import annotations

import http.client
import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request

import importlib
import sys
from pathlib import Path

from .tokenctr_types import account_status_view

_SOLARO_PROBED = False


def _probe_solaro_tokenctr():
    """Import solaro_core.tokenctr when it is installed or sits beside COSMOS.

    parents[3] is the source-tree sibling named in the bridge contract
    (``.../COSMOS/solaro_core``). parents[4] is ``V:\\A\\Ai\\solaro_core``.
    A missing package is ignored. This does not replace the local rules below.
    """
    global _SOLARO_PROBED
    if _SOLARO_PROBED:
        return
    _SOLARO_PROBED = True
    try:
        importlib.import_module("solaro_core.tokenctr")
        return
    except Exception:
        pass
    try:
        here = Path(__file__).resolve()
    except Exception:
        return
    for index in (3, 4):
        if len(here.parents) <= index:
            continue
        folder = here.parents[index] / "solaro_core"
        if not folder.is_dir():
            continue
        parent = str(folder.parent)
        if parent not in sys.path:
            sys.path.append(parent)
        try:
            importlib.import_module("solaro_core.tokenctr")
            return
        except Exception:
            continue


_ENV_KEYS = ("CMSESSIONS_TOKENCTR_URL", "SOLARO_TOKENCTR_URL")
_LIVE_FLAGS = ("SOLARO_TOKENCTR_LIVE", "CMSESSIONS_TOKENCTR_LIVE")
_FIXTURE_ENV = "CMSESSIONS_TOKENCTR_FIXTURE"
_LIVE_ORIGIN = "https://api.tokenctr.com"
_LIVE_HOST = "api.tokenctr.com"
_TIMEOUT_S = 3.0
_MAX_BYTES = 65536
_MAX_URL = 512
_STATUS_SUFFIX = "/v1/account"
_ALLOWED_PREFIXES = ("/v1/account", "/v1/usage", "/v1/logs", "/v1/statement")
_QUERY_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~%+-=&")

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


def _auth_required(code: int) -> dict[str, object]:
    return {"status": "unavailable", "reason": "auth_required", "http_status": code}


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
    """Do not follow redirects. A redirect could leave the allowlist or mutate."""

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
    if head[:3] in ("sk-", "ck_") or head == "xai-" or head == "AIza" or text.startswith("AQ."):
        return True
    return False


def _configured_secret_values() -> list[str]:
    found: list[str] = []
    for name in ("TOKENCTR_API_KEY", "SOLARO_TOKEN"):
        raw = os.environ.get(name)
        if raw is None:
            continue
        text = str(raw).strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
            text = text[1:-1].strip()
        if text:
            found.append(text)
    return found


def _matches_configured_secret(value: str) -> bool:
    text = value.strip()
    for secret in _configured_secret_values():
        if text == secret or text.lower() == "bearer " + secret.lower():
            return True
    return False


def _url_embeds_secret(url: str) -> bool:
    for secret in _configured_secret_values():
        if secret and secret in url:
            return True
    return False


def _live_flag() -> bool:
    for name in _LIVE_FLAGS:
        if str(os.environ.get(name, "")).strip() == "1":
            return True
    return False


def _raw_base_env() -> str | None:
    """Configured base text, ``""`` when blank with no live flag, or None when unset.

    The first non-blank ``CMSESSIONS_TOKENCTR_URL`` or ``SOLARO_TOKENCTR_URL``
    wins. When every present URL variable is blank, or both names are unset,
    ``SOLARO_TOKENCTR_LIVE=1`` or ``CMSESSIONS_TOKENCTR_LIVE=1`` selects
    ``https://api.tokenctr.com``. A blank URL with no live flag stays
    unconfigured and opens no socket.
    """
    found_blank = False
    for name in _ENV_KEYS:
        if name not in os.environ:
            continue
        raw = os.environ.get(name)
        if raw is not None and str(raw).strip():
            return str(raw)
        found_blank = True
    if _live_flag():
        return _LIVE_ORIGIN
    if found_blank:
        return ""
    return None


def _env_base() -> str | None:
    """Return the configured base, an empty string when blank, or None when unusable."""
    raw = _raw_base_env()
    if raw is None:
        return None
    text = str(raw).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    if not text:
        return ""
    if len(text) > _MAX_URL or "\\" in text or "\x00" in text:
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


def _port_ok(host: str, scheme: str, port: int | None) -> bool:
    if port == 0:
        return False
    name = host.strip().lower().rstrip(".")
    if name == _LIVE_HOST:
        return scheme == "https" and port in (None, 443)
    if _is_loopback(host):
        return scheme in ("http", "https")
    return False


def _path_allowed(path: str) -> bool:
    if not path.startswith("/"):
        return False
    if "\\" in path or ".." in path or "\x00" in path or "//" in path:
        return False
    lowered = path.lower()
    matched = False
    for prefix in _ALLOWED_PREFIXES:
        if lowered == prefix or lowered.startswith(prefix + "/"):
            matched = True
            break
    if not matched:
        return False
    return not _blocked_path(path)


def _query_ok(query: str) -> bool:
    if len(query) > 256:
        return False
    return all(ch in _QUERY_CHARS for ch in query)


def _netloc(host: str, port: int | None) -> str:
    host_out = f"[{host}]" if ":" in host else host
    if port is not None:
        return f"{host_out}:{port}"
    return host_out


def _status_url(base: str) -> str | None:
    if not isinstance(base, str) or "\\" in base or "\x00" in base:
        return None
    parts = urllib.parse.urlsplit(base)
    if parts.scheme not in ("http", "https"):
        return None
    if parts.username or parts.password or parts.query or parts.fragment:
        return None
    host = parts.hostname
    if not host:
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    if not _port_ok(host, parts.scheme, port):
        return None
    path = parts.path or ""
    if ".." in path or "\\" in path or "//" in path:
        return None
    if _blocked_path(path):
        return None
    trimmed = path.rstrip("/")
    if trimmed.lower().endswith(_STATUS_SUFFIX):
        status_path = trimmed if trimmed.startswith("/") else "/" + trimmed
    else:
        status_path = (trimmed.rstrip("/") + _STATUS_SUFFIX) if trimmed else _STATUS_SUFFIX
    if not _path_allowed(status_path):
        return None
    url = urllib.parse.urlunsplit((parts.scheme, _netloc(host, port), status_path, "", ""))
    check = urllib.parse.urlsplit(url)
    try:
        check_port = check.port
    except ValueError:
        return None
    if check.hostname is None or not _port_ok(check.hostname, check.scheme, check_port):
        return None
    if check.scheme not in ("http", "https") or check.username or check.password:
        return None
    if _url_embeds_secret(url):
        return None
    return url


def _canonical_get(url: str) -> str | None:
    """Idempotent allowlist check for one fully built GET URL."""
    if not isinstance(url, str) or not url or len(url) > _MAX_URL:
        return None
    if "\\" in url or "\x00" in url or ".." in url:
        return None
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    if parts.username or parts.password or parts.fragment:
        return None
    host = parts.hostname
    if not host:
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    if not _port_ok(host, parts.scheme, port):
        return None
    path = parts.path or ""
    if not _path_allowed(path):
        return None
    if parts.query and not _query_ok(parts.query):
        return None
    if _url_embeds_secret(url):
        return None
    built = urllib.parse.urlunsplit((parts.scheme, _netloc(host, port), path, parts.query, ""))
    check = urllib.parse.urlsplit(built)
    try:
        check_port = check.port
    except ValueError:
        return None
    if check.hostname is None or not _port_ok(check.hostname, check.scheme, check_port):
        return None
    if check.username or check.password:
        return None
    return built


def _split_suffix(suffix: str) -> tuple[str, str] | None:
    if not isinstance(suffix, str):
        return None
    text = suffix.strip()
    if not text or len(text) > 256:
        return None
    if not text.startswith("/") or text.startswith("//"):
        return None
    if "\\" in text or ".." in text or "://" in text or "\x00" in text or "@" in text:
        return None
    parts = urllib.parse.urlsplit(text)
    if parts.scheme or parts.netloc or parts.fragment:
        return None
    if not _path_allowed(parts.path):
        return None
    if parts.query and not _query_ok(parts.query):
        return None
    return parts.path, parts.query


def _origin(base: str) -> str | None:
    status = _status_url(base)
    if not status:
        return None
    parts = urllib.parse.urlsplit(status)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def _join_endpoint(base: str, suffix: str) -> str | None:
    split = _split_suffix(suffix)
    if split is None:
        return None
    path, query = split
    origin = _origin(base)
    if not origin:
        return None
    url = origin + path
    if query:
        url = url + "?" + query
    if _canonical_get(url) != url:
        return None
    return url


def _bearer_headers(url: str) -> dict[str, str]:
    """Attach TOKENCTR_API_KEY only when the request stays on the live host."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").strip().lower().rstrip(".")
    if host != _LIVE_HOST or parts.scheme != "https":
        return {}
    raw = os.environ.get("TOKENCTR_API_KEY")
    if raw is None:
        return {}
    token = str(raw).strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        token = token[1:-1].strip()
    if not token or any(ch in token for ch in "\r\n\x00"):
        return {}
    return {"Authorization": "Bearer " + token}


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
        if _looks_like_secret(value) or _matches_configured_secret(value):
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


def _perform_get(url: str) -> dict[str, object]:
    if _canonical_get(url) != url or _url_embeds_secret(url):
        return _unavailable("not_local")
    headers = {"Accept": "application/json"}
    headers.update(_bearer_headers(url))
    req = urllib.request.Request(url, data=None, headers=headers, method="GET")
    if req.get_method() != "GET" or req.data is not None:
        return _unavailable("refused")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _RefuseRedirect(),
    )
    try:
        with opener.open(req, timeout=_TIMEOUT_S) as res:
            code = res.getcode() or 0
            if code in (401, 403):
                return _auth_required(int(code))
            if code != 200:
                return _unavailable("http_error")
            raw = res.read(_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        _close_quiet(exc)
        if exc.code in (401, 403):
            return _auth_required(int(exc.code))
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
    if isinstance(payload, list):
        payload = {"data": payload}
    cleaned = _sanitize(payload)
    if not isinstance(cleaned, dict):
        return _unavailable("bad_payload")
    status = cleaned.get("status")
    if not isinstance(status, str) or not status.strip() or len(status) > 64:
        cleaned["status"] = "ok"
    else:
        cleaned["status"] = status.strip()
    return cleaned


def _get_status(url: str) -> dict[str, object]:
    # Re-check immediately before the only network call. One attempt, no retry.
    if _status_url(url) != url:
        return _unavailable("not_local")
    return _perform_get(url)


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
    raw = _raw_base_env()
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

    Does not charge or create an account. account_label is null when the URL
    is unset or blank, and no socket is opened. When
    ``CMSESSIONS_TOKENCTR_FIXTURE`` is ``1``, returns the fixed test reading
    and does not open a socket. Any other URL is used only if it is loopback
    or ``https://api.tokenctr.com``.
    """
    _probe_solaro_tokenctr()
    if _fixture_enabled():
        # Test fixture only. Do not reshape this through account_status_view.
        return _fixture_status()
    raw = _raw_base_env()
    if raw is None or not str(raw).strip():
        return account_status_view(None, configured=False)
    base = _env_base()
    if base == "":
        return account_status_view(None, configured=False)
    return account_status_view(_account_report(), configured=True)


def fetch_endpoint(suffix: str) -> dict[str, object]:
    """Allowlisted GET. ``suffix`` is ``/v1/account``, ``/v1/usage``, ``/v1/logs``, or ``/v1/statement``.

    A host that is not loopback and not ``api.tokenctr.com`` returns
    ``reason="not_local"``. Mutation paths are refused the same way.
    """
    _probe_solaro_tokenctr()
    raw = _raw_base_env()
    if raw is None or not str(raw).strip():
        return {"status": "unavailable", "reason": "not_configured"}
    base = _env_base()
    if base == "":
        return {"status": "unavailable", "reason": "not_configured"}
    if base is None:
        return _unavailable("not_local")
    url = _join_endpoint(base, suffix)
    if url is None or _canonical_get(url) != url:
        return _unavailable("not_local")
    return _perform_get(url)


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
    opened when the URL is unset or blank. A configured allowlisted status
    document is read, not invented. used and limit stay null when that
    document does not measure them.
    """
    _probe_solaro_tokenctr()
    if _fixture_enabled():
        return _fixture_status()
    raw = _raw_base_env()
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


__all__ = ["account_status", "fetch_endpoint", "usage_gauge"]
