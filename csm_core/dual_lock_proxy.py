"""cmSessions Dual-Lock Proxy & Circuit Breaker.

Operationalizes the Four Inviolable Duties from 'The Same Rules for AI':
- RULE-H1: No silent upgrades from free/promotional tiers to paid credit lines.
- RULE-H2: Strict protocol isolation (Vertex Enterprise AQ.* vs AI Studio AIza.*).
- RULE-H3: Zero credential exfiltration into chat logs or disk traces.
- RULE-H5: Strict spend ceiling ($5.00 hard cap per session).

Mechanics:
1. Cognitive Handshake: The model emits a signed Pre-Flight Assertion JSON.
2. Deterministic Proxy: The host proxy intercepts all outbound API requests.
   If any covenant is breached, the wire is dropped and the session is sealed
   with an immutable 'governance.*' scar.
"""

from __future__ import annotations
import re
import json
import time
from typing import Dict, Any, Tuple, Optional


class PreFlightAssertionException(Exception):
    """Raised when an agent attempts execution without valid governance assertions."""
    pass


class CircuitBreakerTrippedException(Exception):
    """Raised when a hard governance boundary (spend/upgrade/exfiltration) is breached."""
    pass


class DualLockProxy:
    """Deterministic machine gate protecting cloud wallets and host credentials."""

    SENSITIVE_PATTERNS = [
        re.compile(r"AIza[0-9A-Za-z-_]{35}"),               # Google AI Studio API Key
        re.compile(r"sk-[a-zA-Z0-9]{32,}"),                 # OpenAI / General API Key
        re.compile(r"AQ\.[a-zA-Z0-9_-]{20,}"),              # Vertex Service Key
        re.compile(r"cpanel\s+[a-zA-Z0-9_-]+:[a-zA-Z0-9]{20,}"), # cPanel UAPI Token
    ]

    def __init__(self, hard_spend_limit_usd: float = 5.0):
        self.hard_spend_limit_usd = hard_spend_limit_usd
        self.cumulative_spend_usd = 0.0
        self.assertion_signed = False
        self.signed_model_id: Optional[str] = None
        self.active_rail: Optional[str] = None

    def verify_preflight_assertion(self, assertion_payload: Dict[str, Any]) -> bool:
        """Step 1: Cognitive Handshake.
        
        Model must sign the pre-flight negative covenants before keys are unlocked.
        """
        required_covenants = ["RULE-H1", "RULE-H2", "RULE-H3", "RULE-H5"]
        signed_rules = assertion_payload.get("acknowledged_rules", [])

        for rule in required_covenants:
            if rule not in signed_rules:
                raise PreFlightAssertionException(
                    f"Agent failed to acknowledge mandatory covenant {rule} in pre-flight handshake."
                )

        if assertion_payload.get("spend_cap_usd", 0.0) > self.hard_spend_limit_usd:
            raise PreFlightAssertionException(
                f"Agent claimed spend cap {assertion_payload.get('spend_cap_usd')} exceeds host cap {self.hard_spend_limit_usd}."
            )

        self.assertion_signed = True
        self.signed_model_id = assertion_payload.get("model_id")
        self.active_rail = assertion_payload.get("rail")
        return True

    def intercept_outbound_call(self, endpoint_url: str, headers: Dict[str, str], payload_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """Step 2: Deterministic Proxy. Intercepts outgoing requests on the wire."""
        if not self.assertion_signed:
            raise PreFlightAssertionException("Wire blocked: Pre-flight governance assertion was never signed.")

        # RULE-H2: Protocol Isolation Check
        # Vertex rail must NEVER call AI Studio endpoints
        if self.active_rail == "vertex" and "generativelanguage.googleapis.com" in endpoint_url:
            self.drop_wire("governance.rule_h2_isolation", "Vertex rail attempted connection to AI Studio endpoint.")

        # Check credentials in headers for cross-contamination
        auth = headers.get("Authorization", "")
        if self.active_rail == "vertex" and "AIza" in auth:
            self.drop_wire("governance.rule_h2_isolation", "AI Studio API key detected on Vertex rail transport.")

        # RULE-H3: Check payload for credential leakage
        try:
            payload_str = payload_bytes.decode("utf-8", errors="ignore")
        except Exception:
            payload_str = ""

        for pattern in self.SENSITIVE_PATTERNS:
            if pattern.search(payload_str):
                self.drop_wire("governance.rule_h3_exfiltration", "Credential string detected in outbound prompt/payload.")

        return True, None

    def record_turn_cost(self, usd_cost: float) -> None:
        """Enforces RULE-H5 Spend Ceiling."""
        self.cumulative_spend_usd += usd_cost
        if self.cumulative_spend_usd >= self.hard_spend_limit_usd:
            self.drop_wire(
                "governance.rule_h5_spend_ceiling",
                f"Cumulative spend ${self.cumulative_spend_usd:.4f} breached hard cap ${self.hard_spend_limit_usd:.2f}."
            )

    def drop_wire(self, scar_code: str, reason: str) -> None:
        """Cuts the circuit breaker immediately and seals the session."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        audit_record = {
            "timestamp": timestamp,
            "scar_code": scar_code,
            "reason": reason,
            "model_id": self.signed_model_id,
            "rail": self.active_rail,
            "spend_usd": self.cumulative_spend_usd,
            "action": "CIRCUIT_BREAKER_WIRE_DROPPED_TASK_TERMINATED"
        }
        # In a real daemon, write this immediately to the LMDB journal
        raise CircuitBreakerTrippedException(f"[{scar_code}] {reason} Audit: {json.dumps(audit_record)}")

    @staticmethod
    def redact_sensitive_strings(text: str) -> str:
        """RULE-H3: Scans and replaces keys with hashed redacting tokens."""
        redacted = text
        for pattern in DualLockProxy.SENSITIVE_PATTERNS:
            redacted = pattern.sub("[REDACTED_BY_GOVERNANCE_PROXY]", redacted)
        return redacted
