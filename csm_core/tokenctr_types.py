"""TokenCTR account status, usage, and unavailable records.

The TokenCTR tree was present at V:\\A\\Ai\\COSMOS\\tokenctr.
V:\\GitHub\\tokenctr was absent. This module does not open a socket and does
not store API keys, verifiers, or webhook URLs.

Account status follows GET /v1/account in
V:\\A\\Ai\\COSMOS\\tokenctr\\cosmos_pay_gateway.py (the /v1/account branch),
Store.keys_for, Store.account_profile, and Store.get_settings in that file.
The wire field ``account`` is the hashed account id, not an email. Key rows
are the truncated metadata keys_for returns. ``slack_webhook`` is not a field.

Usage follows PayGateway.usage_today_view in that gateway file,
ActivityLog.usage_today and usage_payload in
V:\\A\\Ai\\COSMOS\\tokenctr\\cosmos_pay_activity.py, and Meter.rollup_day in
V:\\A\\Ai\\COSMOS\\tokenctr\\cosmos_pay_meter.py. CallUsage follows OrUsage
in V:\\A\\Ai\\COSMOS\\tokenctr\\cosmos_pay_or_usage.py. A missing generation
cost stays None. The day view's dollar sum follows the activity query, which
adds nothing for NULL usd.

Unavailable follows the payment-processor 503 ``no_processor`` body in
cosmos_pay_gateway.py, ConnectError ``provider_unavailable`` in
V:\\A\\Ai\\COSMOS\\tokenctr\\cosmos_pay_connect.py, RailError
``STREAM_UNAVAILABLE`` in V:\\A\\Ai\\COSMOS\\tokenctr\\cosmos_pay_groq_rail.py
and the same code in cosmos_pay_openai_rail.py, cosmos_pay_xai_rail.py,
cosmos_pay_deepseek_rail.py, cosmos_pay_azure_rail.py,
cosmos_pay_generic_rail.py, cosmos_pay_local_rail.py, and
cosmos_pay_openrouter_rail.py, plus KeyPool LaneSaturated ``lane_saturated``
and NoSupply in V:\\A\\Ai\\COSMOS\\tokenctr\\cosmos_pay_keypool.py.
``classify_status`` in cosmos_pay_or_usage.py maps a rate or pool 429 to
``lane_saturated``. Local read-only status reasons also match
V:\\A\\Ai\\sessions-page-teams\\tokenctr\\csm_core\\tokenctr_bridge.py.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping, Sequence


# Public promises on GET /v1/account. Not credentials.
ACCOUNT_PROMISES: tuple[str, ...] = (
    "essentials free forever",
    "toll-free under $100/mo",
    "provider discounts pass at full value",
    "data opt-in, anonymized, never sold",
)

# Machine codes from the TokenCTR tree. ``reason`` on Unavailable uses these
# or a local bridge reason. None of them is an API key.
TREE_UNAVAILABLE_CODES: frozenset[str] = frozenset({
    "no_processor",
    "provider_unavailable",
    "STREAM_UNAVAILABLE",
    "lane_saturated",
    "no_supply",
    "free_lane_unconfigured",
    "paid_lane_unconfigured",
    "processor_not_configured",
    "cooling_down",
})

# Reasons returned by csm_core.tokenctr_bridge.account_status with no socket
# payload. Kept here so the status contract has one place for them.
BRIDGE_UNAVAILABLE_REASONS: frozenset[str] = frozenset({
    "not_configured",
    "not_local",
    "refused",
    "http_error",
    "redirect_refused",
    "timeout",
    "unreachable",
    "too_large",
    "bad_json",
    "bad_payload",
})

# Public keys of csm_core.tokenctr_bridge.account_status. No email field.
ACCOUNT_STATUS_KEYS: tuple[str, ...] = (
    "status",
    "reason",
    "account_label",
    "used",
    "limit",
)

_LABEL_KEYS: tuple[str, ...] = ("account_label", "display_name", "label")
_VIEW_USED_KEYS: tuple[str, ...] = ("used", "tokens_used", "usage_used", "total_tokens")
_VIEW_LIMIT_KEYS: tuple[str, ...] = ("limit", "token_limit", "usage_limit")
_VIEW_NESTS: tuple[str, ...] = ("usage", "gauge", "meter")
_EMAIL_IN_TEXT = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_REASON_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")

_SECRET_NAME_PARTS: tuple[str, ...] = (
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
    "bearertoken",
    "clientsecret",
    "signingkey",
    "authtoken",
    "sessionkey",
    "sessiontoken",
    "slackwebhook",
    "verifier",
)


def _norm_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def is_secret_name(name: str) -> bool:
    """True when a mapping key must not be copied onto a status record."""
    norm = _norm_name(name)
    if not norm:
        return True
    return any(part in norm for part in _SECRET_NAME_PARTS)


def is_secret_value(value: str) -> bool:
    """True for raw credential shapes. Hashed account ids are not matched."""
    text = value.strip()
    if len(text) < 12:
        return False
    if text[:7].lower() == "bearer ":
        return True
    if text.startswith(("sk-", "ck_", "xai-", "AIza", "AQ.")):
        return True
    return False


def _finite_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(name)
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(name)
    return number


def _whole_int(value: object, name: str) -> int:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        raise TypeError(name)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return int(value)
    raise TypeError(name)


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(name)
    text = value.strip()
    if text == "":
        return None
    if is_secret_value(text):
        return None
    if len(text) > 512:
        return text[:512]
    return text


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(name)
    text = value.strip()
    if text == "" or is_secret_value(text):
        raise ValueError(name)
    if len(text) > 512:
        return text[:512]
    return text


@dataclass(frozen=True)
class AccountKey:
    """One keys_for row. ``key_hash`` is the truncated display form, not key material."""

    key_hash: str
    label: str
    created_at: str | None
    revoked: bool
    daily_cap_usd: float | None

    def __post_init__(self) -> None:
        shown = _require_text(self.key_hash, "key_hash")
        if shown.startswith("ck_") or is_secret_value(shown):
            raise ValueError("key_hash")
        object.__setattr__(self, "key_hash", shown)
        label = self.label if isinstance(self.label, str) else ""
        if is_secret_value(label):
            label = ""
        object.__setattr__(self, "label", label[:256])
        object.__setattr__(self, "created_at", _optional_text(self.created_at, "created_at"))
        if not isinstance(self.revoked, bool):
            raise TypeError("revoked")
        cap = self.daily_cap_usd
        if cap is not None:
            object.__setattr__(self, "daily_cap_usd", _finite_float(cap, "daily_cap_usd"))

    def as_dict(self) -> dict[str, object]:
        return {
            "key_hash": self.key_hash,
            "label": self.label,
            "created_at": self.created_at,
            "revoked": self.revoked,
            "daily_cap_usd": self.daily_cap_usd,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> AccountKey:
        cap = payload.get("daily_cap_usd")
        return cls(
            key_hash=str(payload.get("key_hash") or ""),
            label=str(payload.get("label") or "") if payload.get("label") is not None else "",
            created_at=payload.get("created_at") if isinstance(payload.get("created_at"), str) else None,
            revoked=bool(payload.get("revoked")),
            daily_cap_usd=None if cap is None else cap,  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class AccountSettings:
    """Defaults from Store.get_settings. The Slack webhook URL is never stored."""

    autotopup_enabled: bool = False
    autotopup_cap_usd: float = 0.0
    data_aggregates: bool = True
    data_per_run: bool = False
    alert_thresholds: tuple[float, ...] = (0.5, 0.8, 1.0)
    slack_webhook_set: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.autotopup_enabled, bool):
            raise TypeError("autotopup_enabled")
        if not isinstance(self.data_aggregates, bool) or not isinstance(self.data_per_run, bool):
            raise TypeError("data_contribution")
        if not isinstance(self.slack_webhook_set, bool):
            raise TypeError("slack_webhook_set")
        object.__setattr__(
            self, "autotopup_cap_usd", _finite_float(self.autotopup_cap_usd, "autotopup_cap_usd")
        )
        thresholds = self.alert_thresholds
        if isinstance(thresholds, list):
            thresholds = tuple(thresholds)
        if not isinstance(thresholds, tuple):
            raise TypeError("alert_thresholds")
        cleaned: list[float] = []
        for item in thresholds:
            cleaned.append(_finite_float(item, "alert_thresholds"))
        object.__setattr__(self, "alert_thresholds", tuple(cleaned))

    def as_dict(self) -> dict[str, object]:
        alerts: dict[str, object] = {"thresholds": list(self.alert_thresholds)}
        if self.slack_webhook_set:
            alerts["slack_webhook_set"] = True
        return {
            "autotopup": {
                "enabled": self.autotopup_enabled,
                "cap_usd": self.autotopup_cap_usd,
            },
            "data_contribution": {
                "aggregates": self.data_aggregates,
                "per_run": self.data_per_run,
            },
            "alerts": alerts,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object] | None) -> AccountSettings:
        if not isinstance(payload, Mapping):
            return cls()
        auto = payload.get("autotopup")
        data = payload.get("data_contribution")
        alerts = payload.get("alerts")
        enabled = False
        cap = 0.0
        if isinstance(auto, Mapping):
            enabled = bool(auto.get("enabled"))
            if auto.get("cap_usd") is not None:
                cap = _finite_float(auto.get("cap_usd"), "autotopup_cap_usd")
        aggregates = True
        per_run = False
        if isinstance(data, Mapping):
            if "aggregates" in data:
                aggregates = bool(data.get("aggregates"))
            if "per_run" in data:
                per_run = bool(data.get("per_run"))
        thresholds: tuple[float, ...] = (0.5, 0.8, 1.0)
        webhook_set = False
        if isinstance(alerts, Mapping):
            raw = alerts.get("thresholds")
            if isinstance(raw, (list, tuple)):
                thresholds = tuple(_finite_float(item, "alert_thresholds") for item in raw)
            hook = alerts.get("slack_webhook")
            webhook_set = isinstance(hook, str) and hook.strip() != ""
        return cls(
            autotopup_enabled=enabled,
            autotopup_cap_usd=cap,
            data_aggregates=aggregates,
            data_per_run=per_run,
            alert_thresholds=thresholds,
            slack_webhook_set=webhook_set,
        )


@dataclass(frozen=True)
class AccountStatus:
    """GET /v1/account. ``status`` defaults to ok; the gateway omits that key."""

    account: str
    plan: str
    credits_face_usd: float
    keys: tuple[AccountKey, ...] = ()
    active_keys_count: int | None = None
    email: str | None = None
    display_name: str | None = None
    created_at: str | None = None
    settings: AccountSettings | None = None
    promises: tuple[str, ...] = ACCOUNT_PROMISES
    status: str = "ok"

    def __post_init__(self) -> None:
        object.__setattr__(self, "account", _require_text(self.account, "account"))
        object.__setattr__(self, "plan", _require_text(self.plan, "plan"))
        object.__setattr__(
            self, "credits_face_usd", _finite_float(self.credits_face_usd, "credits_face_usd")
        )
        keys = self.keys
        if isinstance(keys, list):
            keys = tuple(keys)
        if not isinstance(keys, tuple) or not all(isinstance(item, AccountKey) for item in keys):
            raise TypeError("keys")
        object.__setattr__(self, "keys", keys)
        count = self.active_keys_count
        if count is None:
            count = sum(1 for item in keys if not item.revoked)
        object.__setattr__(self, "active_keys_count", _whole_int(count, "active_keys_count"))
        object.__setattr__(self, "email", _optional_text(self.email, "email"))
        object.__setattr__(self, "display_name", _optional_text(self.display_name, "display_name"))
        object.__setattr__(self, "created_at", _optional_text(self.created_at, "created_at"))
        settings = self.settings if self.settings is not None else AccountSettings()
        if not isinstance(settings, AccountSettings):
            raise TypeError("settings")
        object.__setattr__(self, "settings", settings)
        promises = self.promises
        if isinstance(promises, list):
            promises = tuple(promises)
        if not isinstance(promises, tuple):
            raise TypeError("promises")
        cleaned: list[str] = []
        for item in promises:
            text = _optional_text(item, "promises")
            if text is not None:
                cleaned.append(text)
        object.__setattr__(self, "promises", tuple(cleaned))
        object.__setattr__(self, "status", _require_text(self.status, "status"))

    def as_dict(self) -> dict[str, object]:
        settings = self.settings if self.settings is not None else AccountSettings()
        return {
            "status": self.status,
            "account": self.account,
            "plan": self.plan,
            "credits_face_usd": self.credits_face_usd,
            "keys": [item.as_dict() for item in self.keys],
            "active_keys_count": self.active_keys_count,
            "settings": settings.as_dict(),
            "email": self.email,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "promises": list(self.promises),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> AccountStatus:
        if payload.get("status") == "unavailable":
            raise ValueError("unavailable payload is not an account status")
        raw_keys = payload.get("keys")
        keys: list[AccountKey] = []
        if isinstance(raw_keys, Sequence) and not isinstance(raw_keys, (str, bytes)):
            for item in list(raw_keys)[:64]:
                if isinstance(item, Mapping):
                    keys.append(AccountKey.from_mapping(item))
        raw_settings = payload.get("settings")
        settings = AccountSettings.from_mapping(raw_settings if isinstance(raw_settings, Mapping) else None)
        promises = payload.get("promises")
        promise_values: tuple[str, ...] = ACCOUNT_PROMISES
        if isinstance(promises, Sequence) and not isinstance(promises, (str, bytes)):
            promise_values = tuple(str(item) for item in list(promises)[:16] if isinstance(item, str))
        account = payload.get("account")
        if not isinstance(account, str) or account.strip() == "":
            account = payload.get("account_hash")
        count = payload.get("active_keys_count")
        return cls(
            account=str(account or ""),
            plan=str(payload.get("plan") or ""),
            credits_face_usd=payload.get("credits_face_usd", 0.0),  # type: ignore[arg-type]
            keys=tuple(keys),
            active_keys_count=count if isinstance(count, int) and not isinstance(count, bool) else None,
            email=payload.get("email") if isinstance(payload.get("email"), str) else None,
            display_name=payload.get("display_name") if isinstance(payload.get("display_name"), str) else None,
            created_at=payload.get("created_at") if isinstance(payload.get("created_at"), str) else None,
            settings=settings,
            promises=promise_values,
            status=str(payload.get("status") or "ok"),
        )


@dataclass(frozen=True)
class UsageRollup:
    """One Meter.rollup_day row: lane, model, runs, tokens, measured dollars."""

    lane: str | None
    model: str | None
    runs: int
    tokens_in: int
    tokens_out: int
    measured_usd: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "lane", _optional_text(self.lane, "lane"))
        object.__setattr__(self, "model", _optional_text(self.model, "model"))
        object.__setattr__(self, "runs", _whole_int(self.runs, "runs"))
        object.__setattr__(self, "tokens_in", _whole_int(self.tokens_in, "tokens_in"))
        object.__setattr__(self, "tokens_out", _whole_int(self.tokens_out, "tokens_out"))
        object.__setattr__(self, "measured_usd", _finite_float(self.measured_usd, "measured_usd"))

    def as_dict(self) -> dict[str, object]:
        return {
            "lane": self.lane,
            "model": self.model,
            "runs": self.runs,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "measured_usd": self.measured_usd,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> UsageRollup:
        return cls(
            lane=payload.get("lane") if isinstance(payload.get("lane"), str) else None,
            model=payload.get("model") if isinstance(payload.get("model"), str) else None,
            runs=payload.get("runs", 0),  # type: ignore[arg-type]
            tokens_in=payload.get("tokens_in", 0),  # type: ignore[arg-type]
            tokens_out=payload.get("tokens_out", 0),  # type: ignore[arg-type]
            measured_usd=payload.get("measured_usd", 0.0),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class Usage:
    """GET /v1/usage/today. Activity counters and the meter rollup share this record.

    ``usd_spent_today`` accepts the gateway key or activity's ``usd``.
    ``tokens_in`` accepts ``prompt_tokens``. ``tokens_out`` accepts
    ``completion_tokens``. Those aliases are the activity usage_today names.
    """

    day: str
    free_used_face_usd: float = 0.0
    free_quota_face_usd: float = 0.0
    credits_face_usd: float = 0.0
    usd_spent_today: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    unpriced_calls: int = 0
    rollup: tuple[UsageRollup, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "day", _require_text(self.day, "day"))
        object.__setattr__(self, "free_used_face_usd", _finite_float(self.free_used_face_usd, "free_used_face_usd"))
        object.__setattr__(self, "free_quota_face_usd", _finite_float(self.free_quota_face_usd, "free_quota_face_usd"))
        object.__setattr__(self, "credits_face_usd", _finite_float(self.credits_face_usd, "credits_face_usd"))
        object.__setattr__(self, "usd_spent_today", _finite_float(self.usd_spent_today, "usd_spent_today"))
        object.__setattr__(self, "tokens_in", _whole_int(self.tokens_in, "tokens_in"))
        object.__setattr__(self, "tokens_out", _whole_int(self.tokens_out, "tokens_out"))
        object.__setattr__(self, "calls", _whole_int(self.calls, "calls"))
        object.__setattr__(self, "unpriced_calls", _whole_int(self.unpriced_calls, "unpriced_calls"))
        rollup = self.rollup
        if isinstance(rollup, list):
            rollup = tuple(rollup)
        if not isinstance(rollup, tuple) or not all(isinstance(item, UsageRollup) for item in rollup):
            raise TypeError("rollup")
        object.__setattr__(self, "rollup", rollup)

    def as_dict(self) -> dict[str, object]:
        return {
            "day": self.day,
            "free_used_face_usd": self.free_used_face_usd,
            "free_quota_face_usd": self.free_quota_face_usd,
            "credits_face_usd": self.credits_face_usd,
            "usd_spent_today": self.usd_spent_today,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "calls": self.calls,
            "unpriced_calls": self.unpriced_calls,
            "rollup": [item.as_dict() for item in self.rollup],
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> Usage:
        spent = payload.get("usd_spent_today", payload.get("usd", 0.0))
        tokens_in = payload.get("tokens_in", payload.get("prompt_tokens", 0))
        tokens_out = payload.get("tokens_out", payload.get("completion_tokens", 0))
        raw_roll = payload.get("rollup")
        rollup: list[UsageRollup] = []
        if isinstance(raw_roll, Sequence) and not isinstance(raw_roll, (str, bytes)):
            for item in list(raw_roll)[:256]:
                if isinstance(item, Mapping):
                    rollup.append(UsageRollup.from_mapping(item))
        day = payload.get("day")
        return cls(
            day=str(day or ""),
            free_used_face_usd=payload.get("free_used_face_usd", 0.0),  # type: ignore[arg-type]
            free_quota_face_usd=payload.get("free_quota_face_usd", 0.0),  # type: ignore[arg-type]
            credits_face_usd=payload.get("credits_face_usd", 0.0),  # type: ignore[arg-type]
            usd_spent_today=spent,  # type: ignore[arg-type]
            tokens_in=tokens_in,  # type: ignore[arg-type]
            tokens_out=tokens_out,  # type: ignore[arg-type]
            calls=payload.get("calls", 0),  # type: ignore[arg-type]
            unpriced_calls=payload.get("unpriced_calls", 0),  # type: ignore[arg-type]
            rollup=tuple(rollup),
        )


@dataclass(frozen=True)
class CallUsage:
    """OrUsage: one generation. ``cost is None`` means the provider omitted it."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    cost: float | None = None
    generation_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("prompt_tokens", "completion_tokens", "cached_tokens"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _whole_int(value, name))
        if self.cost is not None:
            object.__setattr__(self, "cost", _finite_float(self.cost, "cost"))
        object.__setattr__(self, "generation_id", _optional_text(self.generation_id, "generation_id"))

    @property
    def cost_state(self) -> str:
        if self.cost is None:
            return "missing"
        return "measured"

    def as_dict(self) -> dict[str, object]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_tokens": self.cached_tokens,
            "cost": self.cost,
            "cost_state": self.cost_state,
            "generation_id": self.generation_id,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> CallUsage:
        def _opt_int(name: str) -> int | None:
            if name not in payload or payload.get(name) is None:
                return None
            return _whole_int(payload.get(name), name)

        cost: float | None
        if "cost" not in payload or payload.get("cost") is None:
            cost = None
        else:
            cost = _finite_float(payload.get("cost"), "cost")
        generation = payload.get("generation_id")
        return cls(
            prompt_tokens=_opt_int("prompt_tokens"),
            completion_tokens=_opt_int("completion_tokens"),
            cached_tokens=_opt_int("cached_tokens"),
            cost=cost,
            generation_id=generation if isinstance(generation, str) else None,
        )


@dataclass(frozen=True)
class Unavailable:
    """A refused or unreachable TokenCTR status. ``status`` is always unavailable.

    ``reason`` is a tree code or a tokenctr_bridge reason. ``message`` is a
    short public string. Bodies, prompts, and credentials are not fields.
    """

    reason: str
    code: str | None = None
    http_status: int | None = None
    message: str | None = None
    status: str = "unavailable"

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _require_text(self.reason, "reason"))
        if self.code is not None:
            object.__setattr__(self, "code", _require_text(self.code, "code"))
        if self.http_status is not None:
            code = _whole_int(self.http_status, "http_status")
            if code < 0 or code > 599:
                raise ValueError("http_status")
            object.__setattr__(self, "http_status", code)
        object.__setattr__(self, "message", _optional_text(self.message, "message"))
        if self.status != "unavailable":
            raise ValueError("status")

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {"status": "unavailable", "reason": self.reason}
        if self.code is not None:
            out["code"] = self.code
        if self.http_status is not None:
            out["http_status"] = self.http_status
        if self.message is not None:
            out["message"] = self.message
        return out

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> Unavailable:
        error = payload.get("error")
        if isinstance(error, Mapping) and isinstance(error.get("code"), str):
            code = str(error.get("code"))
            message = error.get("message") if isinstance(error.get("message"), str) else None
            http = payload.get("http_status")
            return cls(
                reason=code,
                code=code,
                http_status=http if isinstance(http, int) and not isinstance(http, bool) else None,
                message=message,
            )
        reason = payload.get("reason")
        if not isinstance(reason, str) or reason.strip() == "":
            code = payload.get("code")
            if isinstance(code, str):
                reason = code
            else:
                raise ValueError("reason")
        http = payload.get("http_status")
        message = payload.get("message") if isinstance(payload.get("message"), str) else None
        code_value = payload.get("code") if isinstance(payload.get("code"), str) else None
        return cls(
            reason=str(reason),
            code=code_value,
            http_status=http if isinstance(http, int) and not isinstance(http, bool) else None,
            message=message,
        )

    @classmethod
    def payment_processor(cls) -> Unavailable:
        """Gateway 503 when no payment processor is configured."""
        return cls(
            reason="no_processor",
            code="no_processor",
            http_status=503,
            message="payment processor unavailable",
        )

    @classmethod
    def provider(cls) -> Unavailable:
        """Connect 502 when the provider cannot be reached to verify a key."""
        return cls(
            reason="provider_unavailable",
            code="provider_unavailable",
            http_status=502,
            message="Couldn't reach the provider to verify the key. Try again shortly.",
        )

    @classmethod
    def stream(cls) -> Unavailable:
        """RailError when the body is not a billable chunk stream."""
        return cls(
            reason="STREAM_UNAVAILABLE",
            code="STREAM_UNAVAILABLE",
            message="STREAM_UNAVAILABLE",
        )

    @classmethod
    def lane_saturated(cls) -> Unavailable:
        """Key pool or classify_status when the lane cannot take the call."""
        return cls(
            reason="lane_saturated",
            code="lane_saturated",
            http_status=429,
            message="lane saturated",
        )

    @classmethod
    def no_supply(cls, code: str = "no_supply") -> Unavailable:
        """No key in the requested lane, or the model is not in the registry."""
        chosen = _require_text(code, "code")
        return cls(reason=chosen, code=chosen, http_status=503, message=chosen)

    @classmethod
    def bridge(cls, reason: str) -> Unavailable:
        """Local account_status miss. Does not contact TokenCTR."""
        chosen = _require_text(reason, "reason")
        if chosen not in BRIDGE_UNAVAILABLE_REASONS:
            raise ValueError("reason")
        return cls(reason=chosen)


def _view_number(value: object) -> int | float | None:
    """JSON numbers only. Booleans are not measurements."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _contains_email(value: str) -> bool:
    return _EMAIL_IN_TEXT.search(value) is not None


def _view_sources(report: Mapping[str, object]) -> list[Mapping[str, object]]:
    sources: list[Mapping[str, object]] = [report]
    for key in _VIEW_NESTS:
        child = report.get(key)
        if isinstance(child, Mapping):
            sources.append(child)
    return sources


def _first_view_number(
    sources: list[Mapping[str, object]], keys: tuple[str, ...]
) -> int | float | None:
    for source in sources:
        for key in keys:
            if is_secret_name(key) or key not in source:
                continue
            number = _view_number(source.get(key))
            if number is not None:
                return number
    return None


def _pair_view(source: Mapping[str, object], left: str, right: str) -> int | float | None:
    inn = _view_number(source.get(left))
    out = _view_number(source.get(right))
    if inn is None or out is None:
        return None
    return inn + out


def _view_used(sources: list[Mapping[str, object]]) -> int | float | None:
    found = _first_view_number(sources, _VIEW_USED_KEYS)
    if found is not None:
        return found
    for source in sources:
        tokens = source.get("tokens")
        if isinstance(tokens, Mapping):
            paired = _pair_view(tokens, "in", "out")
            if paired is None:
                paired = _pair_view(tokens, "input", "output")
            if paired is not None:
                return paired
        number = _view_number(tokens)
        if number is not None:
            return number
        paired = _pair_view(source, "tokens_in", "tokens_out")
        if paired is None:
            paired = _pair_view(source, "prompt_tokens", "completion_tokens")
        if paired is None:
            paired = _pair_view(source, "input_tokens", "output_tokens")
        if paired is not None:
            return paired
    return None


def _view_reason(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if _REASON_CODE.fullmatch(text) is None or _contains_email(text) or is_secret_value(text):
        return None
    return text


def _view_status(value: object) -> str:
    if isinstance(value, str):
        text = value.strip()
        if (
            text
            and len(text) <= 64
            and not _contains_email(text)
            and not is_secret_value(text)
        ):
            return text
    return "ok"


def _label_from_mapping(payload: Mapping[str, object], depth: int = 0) -> str | None:
    """A display label. Email addresses are not labels and secret files are not read."""
    if depth > 2:
        return None
    for key in _LABEL_KEYS:
        if is_secret_name(key) or key not in payload:
            continue
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or len(text) > 256 or _contains_email(text) or is_secret_value(text):
            continue
        return text
    for key in ("profile", "user", "account_profile"):
        child = payload.get(key)
        if isinstance(child, Mapping):
            found = _label_from_mapping(child, depth + 1)
            if found is not None:
                return found
    return None


def account_status_view(
    report: Mapping[str, object] | None = None,
    *,
    configured: bool,
) -> dict[str, object]:
    """Five-key account status. account_label is None when unconfigured.

    Does not open files. An email address is never copied into account_label,
    including an address that was stored in a secret file.
    """
    if not configured:
        return {
            "status": "unavailable",
            "reason": "not_configured",
            "account_label": None,
            "used": None,
            "limit": None,
        }
    if not isinstance(report, Mapping):
        return {
            "status": "unavailable",
            "reason": "bad_payload",
            "account_label": None,
            "used": None,
            "limit": None,
        }
    status = _view_status(report.get("status"))
    reason = _view_reason(report.get("reason"))
    if status == "unavailable" and reason is None:
        reason = "bad_payload"
    sources = _view_sources(report)
    return {
        "status": status,
        "reason": reason,
        "account_label": _label_from_mapping(report),
        "used": _view_used(sources),
        "limit": _first_view_number(sources, _VIEW_LIMIT_KEYS),
    }


__all__ = [
    "ACCOUNT_PROMISES",
    "ACCOUNT_STATUS_KEYS",
    "BRIDGE_UNAVAILABLE_REASONS",
    "TREE_UNAVAILABLE_CODES",
    "AccountKey",
    "AccountSettings",
    "AccountStatus",
    "CallUsage",
    "Unavailable",
    "Usage",
    "UsageRollup",
    "account_status_view",
    "is_secret_name",
    "is_secret_value",
]
