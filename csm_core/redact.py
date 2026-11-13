"""Mask strings that look like tokens, keys, or secrets.

The original value is never logged.
"""

from __future__ import annotations

import re

_MASK = "[REDACTED:{kind}]"

# Specific shapes before the general sk- and bearer rules.
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"
            r".*?"
            r"-----END (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----",
            re.S,
        ),
    ),
    ("slack-webhook", re.compile(r"https://hooks\.slack\.com/services/\S+")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{12,}")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("xai_key", re.compile(r"\bxai-[A-Za-z0-9_\-]{16,}")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{16,}")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("google-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("vertex-key", re.compile(r"\bAQ\.[A-Za-z0-9_\-]{20,}")),
    (
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
        ),
    ),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.=]{12,}")),
    (
        "secret-assign",
        re.compile(
            r"(?i)\b(api[_\-]?key|access[_\-]?token|auth[_\-]?token|secret|"
            r"password|passwd|client[_\-]?secret)\b\s*[:=]\s*[\"']?"
            r"([A-Za-z0-9_\-\.\/\+=]{8,})[\"']?"
        ),
    ),
    ("long-hex", re.compile(r"\b[0-9a-fA-F]{40,}\b")),
)


def redact(text: str) -> str:
    """Return text with token-shaped strings replaced by masks."""
    if not text:
        return ""
    if not isinstance(text, str):
        raise TypeError("redact() expects str")
    out = text
    for kind, rx in _RULES:
        if kind == "secret-assign":
            out = rx.sub(lambda match, _k=kind: f"{match.group(1)}={_MASK.format(kind=_k)}", out)
        else:
            out = rx.sub(_MASK.format(kind=kind), out)
    return out
