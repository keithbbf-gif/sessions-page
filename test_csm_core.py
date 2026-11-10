#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermetic tests for cmSessions csm_core module:
- LMDB Zero-Copy State Journal and Data Structs
- Deterministic Failover Kernel
- Dual-Lock Proxy and Circuit Breaker
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import csm_core


def case_lmdb_event_roundtrip() -> None:
    event = csm_core.SessionEvent(
        epoch=1,
        step=42,
        timestamp=1700000000.0,
        event_type="GATE_CHECK",
        phase="VERIFY",
        actor="argon_orchestrator",
        payload_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        tokens_in=1200,
        tokens_out=450,
        cost_usd=0.0035,
        scars_recorded=["test.scar_1"],
        metadata={"rail": "vertex-argon"},
    )
    encoded = csm_core.encode_event(event)
    decoded = csm_core.decode_event(encoded)

    if decoded.epoch != 1 or decoded.step != 42:
        raise AssertionError(f"Epoch/Step mismatch: {decoded.epoch}, {decoded.step}")
    if decoded.event_type != "GATE_CHECK" or decoded.phase != "VERIFY":
        raise AssertionError(f"Event type/phase mismatch: {decoded.event_type}, {decoded.phase}")
    if decoded.tokens_in != 1200 or decoded.cost_usd != 0.0035:
        raise AssertionError(f"Tokens/Cost mismatch: {decoded.tokens_in}, {decoded.cost_usd}")
    if decoded.scars_recorded != ["test.scar_1"]:
        raise AssertionError(f"Scars mismatch: {decoded.scars_recorded}")


def case_lmdb_journal_storage(tmp_path: Path) -> None:
    db_dir = tmp_path / "csm_journal"
    journal = csm_core.CmsLMDBJournal(str(db_dir))
    try:
        e1 = csm_core.SessionEvent(
            epoch=1, step=1, timestamp=100.0, event_type="INIT", phase="RECON", actor="agent", payload_hash="h1"
        )
        e2 = csm_core.SessionEvent(
            epoch=1, step=2, timestamp=101.0, event_type="PATCH", phase="PATCH", actor="agent", payload_hash="h2"
        )
        e_other = csm_core.SessionEvent(
            epoch=1, step=1, timestamp=100.0, event_type="INIT", phase="RECON", actor="agent2", payload_hash="h3"
        )

        journal.append_event("sess-alpha", e1)
        journal.append_event("sess-alpha", e2)
        journal.append_event("sess-beta", e_other)

        alpha_events = journal.get_events("sess-alpha")
        if len(alpha_events) != 2:
            raise AssertionError(f"Expected 2 events for sess-alpha, got {len(alpha_events)}")
        if alpha_events[0].event_type != "INIT" or alpha_events[1].event_type != "PATCH":
            raise AssertionError(f"Unexpected event order: {[e.event_type for e in alpha_events]}")

        beta_events = journal.get_events("sess-beta")
        if len(beta_events) != 1 or beta_events[0].actor != "agent2":
            raise AssertionError(f"Unexpected beta events: {beta_events}")
    finally:
        journal.close()


def case_failover_kernel_missing_dir(tmp_path: Path) -> None:
    kernel = csm_core.DeterministicFailoverKernel()
    fake_db = str(tmp_path / "nonexistent.sqlite")
    fake_mbox = str(tmp_path / "nonexistent_mbox")
    res = kernel.query_thunderbird_emails(fake_db, fake_mbox, "urgent")
    if res.get("status") != "NOT_FOUND" or res.get("hits_count") != 0:
        raise AssertionError(f"Expected NOT_FOUND for missing mbox: {res}")


def case_failover_kernel_intercepts_tokenizer_error(tmp_path: Path) -> None:
    kernel = csm_core.DeterministicFailoverKernel()
    db_file = tmp_path / "corrupt_moz.sqlite"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    # Create table without mozporter tokenizer
    cur.execute("CREATE TABLE messagesText_content (c1subject TEXT, c0body TEXT)")
    cur.execute("INSERT INTO messagesText_content VALUES ('Budget report', 'Q4 figures')")
    conn.commit()
    conn.close()

    # Query with match pattern
    res = kernel.query_thunderbird_emails(str(db_file), str(tmp_path / "mbox"), "Budget")
    if res.get("status") != "SUCCESS" or res.get("hits_count") != 1:
        raise AssertionError(f"Expected SUCCESS from fallback or query: {res}")


def case_dual_lock_preflight_valid() -> None:
    proxy = csm_core.DualLockProxy(hard_spend_limit_usd=5.0)
    valid_assertion = {
        "model_id": "gemini-4-argon",
        "rail": "vertex",
        "spend_cap_usd": 2.50,
        "acknowledged_rules": ["RULE-H1", "RULE-H2", "RULE-H3", "RULE-H5"],
    }
    if not proxy.verify_preflight_assertion(valid_assertion):
        raise AssertionError("Valid assertion failed verification")
    if not proxy.assertion_signed or proxy.signed_model_id != "gemini-4-argon":
        raise AssertionError("Proxy state not updated after assertion")


def case_dual_lock_preflight_missing_rule() -> None:
    proxy = csm_core.DualLockProxy(hard_spend_limit_usd=5.0)
    invalid_assertion = {
        "model_id": "gemini-4-argon",
        "rail": "vertex",
        "spend_cap_usd": 2.50,
        "acknowledged_rules": ["RULE-H1", "RULE-H2"],  # Missing H3 & H5
    }
    try:
        proxy.verify_preflight_assertion(invalid_assertion)
        raise AssertionError("Should have failed on missing covenants")
    except csm_core.PreFlightAssertionException:
        pass


def case_dual_lock_preflight_excessive_spend_cap() -> None:
    proxy = csm_core.DualLockProxy(hard_spend_limit_usd=5.0)
    greedy_assertion = {
        "model_id": "gemini-4-argon",
        "rail": "vertex",
        "spend_cap_usd": 15.00,  # Exceeds 5.0
        "acknowledged_rules": ["RULE-H1", "RULE-H2", "RULE-H3", "RULE-H5"],
    }
    try:
        proxy.verify_preflight_assertion(greedy_assertion)
        raise AssertionError("Should have failed on excessive spend cap")
    except csm_core.PreFlightAssertionException:
        pass


def case_dual_lock_rule_h2_isolation() -> None:
    proxy = csm_core.DualLockProxy(hard_spend_limit_usd=5.0)
    proxy.verify_preflight_assertion({
        "model_id": "gemini-4-argon",
        "rail": "vertex",
        "spend_cap_usd": 5.0,
        "acknowledged_rules": ["RULE-H1", "RULE-H2", "RULE-H3", "RULE-H5"],
    })
    # Attempting to call consumer AI studio endpoint on vertex rail
    try:
        proxy.intercept_outbound_call(
            endpoint_url="https://generativelanguage.googleapis.com/v1beta/models",
            headers={"Authorization": "Bearer token"},
            payload_bytes=b'{"prompt": "hello"}',
        )
        raise AssertionError("RULE-H2 breach was not caught by proxy")
    except csm_core.CircuitBreakerTrippedException as exc:
        if "rule_h2_isolation" not in str(exc):
            raise AssertionError(f"Expected rule_h2_isolation scar: {exc}")


def case_dual_lock_rule_h3_exfiltration() -> None:
    proxy = csm_core.DualLockProxy(hard_spend_limit_usd=5.0)
    proxy.verify_preflight_assertion({
        "model_id": "gemini-4-argon",
        "rail": "vertex",
        "spend_cap_usd": 5.0,
        "acknowledged_rules": ["RULE-H1", "RULE-H2", "RULE-H3", "RULE-H5"],
    })
    # Leaking OpenAI secret key in outbound prompt
    leaky_payload = b'{"prompt": "Here is the key sk-abcdef12345678901234567890123456"}'
    try:
        proxy.intercept_outbound_call(
            endpoint_url="https://aiplatform.googleapis.com/v1/projects",
            headers={"Authorization": "Bearer AQ.service_key"},
            payload_bytes=leaky_payload,
        )
        raise AssertionError("RULE-H3 credential leak was not blocked")
    except csm_core.CircuitBreakerTrippedException as exc:
        if "rule_h3_exfiltration" not in str(exc):
            raise AssertionError(f"Expected rule_h3_exfiltration scar: {exc}")


def case_dual_lock_rule_h5_spend_ceiling() -> None:
    proxy = csm_core.DualLockProxy(hard_spend_limit_usd=2.0)
    proxy.verify_preflight_assertion({
        "model_id": "gemini-4-argon",
        "rail": "vertex",
        "spend_cap_usd": 2.0,
        "acknowledged_rules": ["RULE-H1", "RULE-H2", "RULE-H3", "RULE-H5"],
    })
    proxy.record_turn_cost(0.75)
    proxy.record_turn_cost(0.75)  # Total 1.50, still under 2.0
    try:
        proxy.record_turn_cost(0.60)  # Total 2.10, breaches 2.0
        raise AssertionError("RULE-H5 spend ceiling was not enforced")
    except csm_core.CircuitBreakerTrippedException as exc:
        if "rule_h5_spend_ceiling" not in str(exc):
            raise AssertionError(f"Expected rule_h5_spend_ceiling scar: {exc}")


def case_dual_lock_redaction() -> None:
    raw = "My key is AIzaSyD9ExampleKey35CharsLong012345ABCD and OpenAI is sk-12345678901234567890123456789012"
    redacted = csm_core.DualLockProxy.redact_sensitive_strings(raw)
    if "AIza" in redacted or "sk-" in redacted:
        raise AssertionError(f"Redaction failed: {redacted}")
    if "[REDACTED_BY_GOVERNANCE_PROXY]" not in redacted:
        raise AssertionError("Missing redaction placeholder")


def main() -> int:
    cases = [
        ("lmdb event roundtrip", case_lmdb_event_roundtrip),
        ("lmdb journal storage", case_lmdb_journal_storage),
        ("failover kernel missing dir", case_failover_kernel_missing_dir),
        ("failover kernel intercepts tokenizer error", case_failover_kernel_intercepts_tokenizer_error),
        ("dual lock preflight valid", case_dual_lock_preflight_valid),
        ("dual lock preflight missing rule", case_dual_lock_preflight_missing_rule),
        ("dual lock preflight excessive spend cap", case_dual_lock_preflight_excessive_spend_cap),
        ("dual lock rule h2 isolation", case_dual_lock_rule_h2_isolation),
        ("dual lock rule h3 exfiltration", case_dual_lock_rule_h3_exfiltration),
        ("dual lock rule h5 spend ceiling", case_dual_lock_rule_h5_spend_ceiling),
        ("dual lock redaction", case_dual_lock_redaction),
    ]

    tmp = Path(tempfile.mkdtemp(prefix="csm_test_"))
    passed = 0
    try:
        for name, fn in cases:
            if "tmp_path" in fn.__code__.co_varnames:
                fn(tmp)
            else:
                fn()
            print(f"ok   {name}")
            passed += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"{passed}/{len(cases)}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
