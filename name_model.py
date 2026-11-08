"""Optional one-line title. Off unless CMSESSIONS_NAME=1 and XAI_API_KEY are set."""
from __future__ import annotations

import json
import os
import urllib.request

_URL = "https://api.x.ai/v1/chat/completions"
_MODEL = "grok-4.20-0309-non-reasoning"
_TIMEOUT = 20
_MAX = 80
_FIELDS = (
    ("vendor", "vendor"),
    ("session_id", "session_id"),
    ("title", "title"),
    ("placeholder", "title"),
    ("placeholder_title", "title"),
    ("n_turns", "n_turns"),
    ("turn_count", "n_turns"),
    ("turns", "n_turns"),
    ("date", "date"),
)


def _full_path(text: str) -> bool:
    if text.startswith("\\\\") or text.startswith("/") or text.startswith("~"):
        return True
    if text.lower().startswith("file:"):
        return True
    if len(text) >= 3 and text[1] == ":" and text[2] in "\\/":
        return True
    return "\\" in text


def _field_text(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = " ".join(value.split())
    else:
        return None
    if not text or len(text) > 160 or _full_path(text):
        return None
    return text


def _user_message(header: dict) -> str:
    picked: dict[str, str] = {}
    for src, dst in _FIELDS:
        if dst in picked or src not in header:
            continue
        text = _field_text(header.get(src))
        if text is not None:
            picked[dst] = text
    return json.dumps(picked, ensure_ascii=False, separators=(",", ":"))


def _reply_line(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, list):
        bits: list[str] = []
        for part in content:
            if isinstance(part, str):
                bits.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                bits.append(part["text"])
        content = " ".join(bits)
    if not isinstance(content, str):
        return None
    stripped = content.strip()
    if not stripped:
        return None
    line = stripped.splitlines()[0].strip()
    if not line:
        return None
    if len(line) > _MAX:
        line = line[:_MAX].rstrip()
    return line or None


def maybe_name(header: dict) -> str | None:
    """One title line, or None. No call when naming is off or the row is legal."""
    if not isinstance(header, dict) or header.get("legal") is True:
        return None
    if os.environ.get("CMSESSIONS_NAME") != "1":
        return None
    key = os.environ.get("XAI_API_KEY")
    if not key:
        return None
    message = _user_message(header)
    body = json.dumps({
        "model": _MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Reply with one session title line, at most 80 characters.",
            },
            {"role": "user", "content": message},
        ],
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _URL,
        data=body,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as res:
            raw = res.read(65536)
        return _reply_line(json.loads(raw.decode("utf-8")))
    except Exception:
        return None
