#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermetic test suite for cmSessions Phase 2 & Scale Architecture:
- Pillar 1: Scale Indexer (7-day hot window, delta scan, atomic cache, backfill)
- Pillar 2: 6+1 Hierarchical Cluster Topology & Single-Writer PIN Leasing
- Pillar 2: Durability Triumvirate (TidyUP, TidyUP2, BootUP HMAC Gate)
- Pillar 3: Discrete Replay & VCR Mock Runner
- Pillar 3: Decoupled Rollback Matrix (code-only, context-only, fork)
"""

from __future__ import annotations

import os
import sys
import time
import json
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import csm_core


# =============================================================================
# Pillar 1: Scale Indexer Tests
# =============================================================================

def case_scale_indexer_hot_window(tmp_path: Path) -> None:
    """Verifies that the 7-day hot window filters out older historical files."""
    grok_dir = tmp_path / "grok_sessions"
    grok_dir.mkdir(parents=True)
    now = time.time()

    # Create mock session files with controlled mtimes
    # File 1: 2 days old (inside 7-day hot window)
    f_hot = grok_dir / "sess_hot.jsonl"
    f_hot.write_text('{"turn": 1, "text": "hot session"}', encoding="utf-8")
    os.utime(f_hot, (now - 2 * 86400, now - 2 * 86400))

    # File 2: 12 days old (outside 7-day hot window)
    f_cold = grok_dir / "sess_cold.jsonl"
    f_cold.write_text('{"turn": 1, "text": "cold session"}', encoding="utf-8")
    os.utime(f_cold, (now - 12 * 86400, now - 12 * 86400))

    cache_file = tmp_path / "var" / "index.json"
    indexer = csm_core.ScaleIndexer(cache_path=str(cache_file), hot_days=7)

    homes = {"grok": grok_dir}
    hits = indexer.scan_hot_window(homes)

    if len(hits) != 1:
        raise AssertionError(f"Expected exactly 1 hot hit, got {len(hits)}")
    if hits[0]["vendor_id"] != "sess_hot.jsonl":
        raise AssertionError(f"Expected sess_hot.jsonl, got {hits[0]['vendor_id']}")
    if indexer.total_count != 1:
        raise AssertionError(f"Expected catalog count 1, got {indexer.total_count}")


def case_scale_indexer_delta_scan(tmp_path: Path) -> None:
    """Verifies high-water mark delta scanning picks up only newly added/modified files."""
    claude_dir = tmp_path / "claude_sessions"
    claude_dir.mkdir(parents=True)
    now = time.time()

    f1 = claude_dir / "sess_1.jsonl"
    f1.write_text('{"id": 1}', encoding="utf-8")
    os.utime(f1, (now - 100, now - 100))

    cache_file = tmp_path / "var" / "index.json"
    indexer = csm_core.ScaleIndexer(cache_path=str(cache_file), hot_days=7)
    homes = {"claude": claude_dir}

    # Pass 1: Scans f1
    hits1 = indexer.scan_hot_window(homes)
    if len(hits1) != 1:
        raise AssertionError(f"Pass 1 expected 1 hit, got {len(hits1)}")

    # Pass 2: No changes -> 0 new hits
    hits2 = indexer.scan_hot_window(homes)
    if len(hits2) != 0:
        raise AssertionError(f"Pass 2 expected 0 hits, got {len(hits2)}")

    # Add f2 with newer timestamp
    f2 = claude_dir / "sess_2.jsonl"
    f2.write_text('{"id": 2}', encoding="utf-8")
    os.utime(f2, (now + 50, now + 50))

    # Pass 3: Delta scan picks up only f2
    hits3 = indexer.scan_hot_window(homes)
    if len(hits3) != 1 or hits3[0]["vendor_id"] != "sess_2.jsonl":
        raise AssertionError(f"Pass 3 expected only sess_2.jsonl hit, got {hits3}")
    if indexer.total_count != 2:
        raise AssertionError(f"Expected catalog count 2, got {indexer.total_count}")


def case_scale_indexer_atomic_cache(tmp_path: Path) -> None:
    """Verifies atomic cache persistence and instant cold-boot loading."""
    cache_file = tmp_path / "var" / "index.json"
    indexer1 = csm_core.ScaleIndexer(cache_path=str(cache_file))

    # Populate in-memory catalog
    indexer1._catalog["sess-001"] = {
        "id": "sess-001", "vendor_id": "v1", "harness": "grok",
        "path": "C:/fake/path", "updated": 1700000000.0, "nbytes": 4096,
        "title": "Refactoring Auth", "cwd": "V:/repo"
    }
    indexer1._catalog["sess-002"] = {
        "id": "sess-002", "vendor_id": "v2", "harness": "claude",
        "path": "C:/fake/path2", "updated": 1700001000.0, "nbytes": 8192,
        "title": "Database Optimization", "cwd": "V:/repo"
    }
    success = indexer1.save_cache_atomic()
    if not success or not cache_file.is_file():
        raise AssertionError("Failed to save atomic cache")

    # Cold boot indexer2
    indexer2 = csm_core.ScaleIndexer(cache_path=str(cache_file))
    loaded_count = indexer2.load_cache()
    if loaded_count != 2:
        raise AssertionError(f"Expected 2 loaded sessions, got {loaded_count}")

    # Query checks
    results = indexer2.query(search="Refactoring")
    if len(results) != 1 or results[0]["id"] != "sess-001":
        raise AssertionError(f"Query search failed: {results}")

    grok_results = indexer2.query(harness="grok")
    if len(grok_results) != 1 or grok_results[0]["id"] != "sess-001":
        raise AssertionError(f"Query harness filter failed: {grok_results}")


# =============================================================================
# Pillar 2: Hierarchical Clusters & PIN Leasing Tests
# =============================================================================

def case_cluster_6_plus_1_fanout() -> None:
    """Verifies 6+1 Fan-Out rule enforcement and reserve slot headroom."""
    cluster = csm_core.ClusterNode(
        cluster_id="cluster-alpha",
        name="Backend Core",
        lead_agent_id="lead-001",
        project_id="proj-cosmos"
    )

    # Lead is already registered as 1
    if cluster.lead.agent_id != "lead-001":
        raise AssertionError("Cluster lead mismatch")

    # Add 6 workers (allowed under 6+1)
    for i in range(1, 7):
        cluster.add_worker(
            agent_id=f"worker-{i:03d}",
            model="gemini-4-flash",
            door="cosmos",
            role="worker"
        )

    roster = cluster.get_roster()
    if roster["worker_count"] != 6:
        raise AssertionError(f"Expected 6 workers, got {roster['worker_count']}")

    # Adding 7th worker without reserve must fail closed
    try:
        cluster.add_worker(
            agent_id="worker-007",
            model="gemini-4-flash",
            door="cosmos",
            role="worker",
            use_reserve=False
        )
        raise AssertionError("Should have raised FanOutCeilingExceededError for 7th worker")
    except csm_core.FanOutCeilingExceededError:
        pass

    # Adding 7th worker WITH reserve slot enabled succeeds (up to 8 workers + 1 lead)
    cluster.add_worker(
        agent_id="worker-007",
        model="gemini-4-flash",
        door="cosmos",
        role="worker",
        use_reserve=True
    )
    if cluster.get_roster()["worker_count"] != 7:
        raise AssertionError("Expected 7 workers after using reserve slot")

    # Test subcluster nesting (Cluster of Clusters)
    sub = csm_core.ClusterNode("cluster-sub", "Sub-Worker", "lead-sub", "proj-cosmos")
    cluster.add_subcluster(sub)
    if "cluster-sub" not in cluster.subclusters:
        raise AssertionError("Subcluster nesting failed")


def case_single_writer_pin_lease() -> None:
    """Verifies single-writer PIN exclusion and worker proposal submission."""
    pin_mgr = csm_core.SingleWriterPinManager(default_lease_duration_s=10.0)

    # Worker attempting to acquire PIN must fail
    try:
        pin_mgr.acquire_pin(agent_id="worker-01", role="worker")
        raise AssertionError("Worker should not be able to acquire live tree PIN")
    except csm_core.PinLeaseViolationError:
        pass

    # Lead acquires PIN successfully
    acquired = pin_mgr.acquire_pin(agent_id="lead-01", role="lead")
    if not acquired:
        raise AssertionError("Lead failed to acquire PIN")

    # Another lead cannot acquire while active lease held
    acquired_peer = pin_mgr.acquire_pin(agent_id="lead-02", role="lead")
    if acquired_peer:
        raise AssertionError("Peer lead acquired PIN while held by lead-01")

    # Lead can write to live master tree
    pin_mgr.assert_write_privilege(agent_id="lead-01", path="live_master_tree")

    # Worker is refused write to live tree
    try:
        pin_mgr.assert_write_privilege(agent_id="worker-01", path="live_master_tree")
        raise AssertionError("Worker write to live tree should have failed closed")
    except csm_core.PinLeaseViolationError:
        pass

    # Worker submits proposal instead
    prop = pin_mgr.submit_proposal(
        agent_id="worker-01",
        cluster_id="cluster-01",
        summary="Add token budget validator",
        target_paths=["src/budget.py"],
        diff_content="--- a/src/budget.py\n+++ b/src/budget.py\n+def validate(): pass\n"
    )
    if prop.status != "PENDING" or not prop.diff_hash:
        raise AssertionError(f"Proposal submission invalid: {prop}")

    # Lead merges proposal
    merged = pin_mgr.merge_proposal(pin_holder_id="lead-01", proposal_id=prop.proposal_id)
    if not merged or prop.status != "MERGED":
        raise AssertionError("Lead failed to merge proposal")


def case_append_only_write_file() -> None:
    """Verifies append-only write files with monotonic sequence numbers."""
    pin_mgr = csm_core.SingleWriterPinManager()

    seq1 = pin_mgr.append_write_file_event("agent-01", "issued", {"task": "AST Parse"})
    seq2 = pin_mgr.append_write_file_event("agent-01", "extended", {"pct": 50})
    seq3 = pin_mgr.append_write_file_event("agent-01", "released", {"status": "DONE"})

    if (seq1, seq2, seq3) != (1, 2, 3):
        raise AssertionError(f"Expected monotonic sequence (1, 2, 3), got {(seq1, seq2, seq3)}")

    stream = pin_mgr.write_file_streams["agent-01"]
    if len(stream) != 3 or stream[0]["action"] != "issued" or stream[2]["action"] != "released":
        raise AssertionError(f"Stream verification failed: {stream}")


def case_durability_triumvirate() -> None:
    """Verifies TidyUP compaction, TidyUP2 adversarial porosity audit, and BootUP HMAC verification."""
    session_key = b"secret-cosmos-session-key-32bytes!!"

    # 1. TidyUP: Compact active state to SEED
    seed = csm_core.DurabilityTriumvirate.tidy_up(
        cluster_id="c-001",
        lead_agent_id="lead-001",
        goal="Refactor DB Layer",
        decisions=["Use LMDB writemap", "Enforce 6+1 fanout"],
        modified_paths=["src/db.py", "src/schema.py"],
        open_questions=["Retention period?"],
        artifact_pointers={"shard_1": "mem/001.bin"},
        scars_recorded=["rule_h5_spend_ceiling"],
        session_key=session_key
    )

    if not seed.hmac_sha256 or seed.length_bytes <= 0:
        raise AssertionError(f"TidyUP SEED generation failed: {seed}")

    # 2. TidyUP2: Adversarial re-measure
    # Case A: Clean close (no temp files, all claimed paths exist)
    audit_clean = csm_core.DurabilityTriumvirate.tidy_up_2(
        seed=seed,
        actual_files_on_disk={"src/db.py", "src/schema.py", "README.md"},
        untracked_temp_files=set()
    )
    if not audit_clean["verified"] or audit_clean["verdict"] != "VERIFIED":
        raise AssertionError(f"TidyUP2 clean audit failed: {audit_clean}")

    # Case B: Porosity breach (untracked temp files left behind)
    audit_porous = csm_core.DurabilityTriumvirate.tidy_up_2(
        seed=seed,
        actual_files_on_disk={"src/db.py", "src/schema.py"},
        untracked_temp_files={"temp_dump.txt"}
    )
    if audit_porous["verified"] or audit_porous["porosity_score"] != 1:
        raise AssertionError(f"TidyUP2 failed to catch porosity breach: {audit_porous}")

    # 3. BootUP: Validate SEED HMAC
    # Valid boot
    boot_ok = csm_core.DurabilityTriumvirate.boot_up(seed, session_key)
    if not boot_ok:
        raise AssertionError("BootUP valid check failed")

    # Tampered key or tampered length must fail closed
    bad_key = b"wrong-key-000000000000000000000000"
    try:
        csm_core.DurabilityTriumvirate.boot_up(seed, bad_key)
        raise AssertionError("BootUP should have failed with wrong HMAC key")
    except csm_core.VerificationFailureError:
        pass


# =============================================================================
# Pillar 3: Replay & VCR Mock Runner Tests
# =============================================================================

def case_replay_discrete_stepping() -> None:
    """Verifies discrete turn-by-turn stepping state machine."""
    engine = csm_core.ReplayEngine(session_id="ses-replay-001")

    engine.add_turn(1, "Turn 1 Prompt", "Turn 1 Response")
    engine.add_turn(2, "Turn 2 Prompt", "Turn 2 Response")
    engine.add_turn(3, "Turn 3 Prompt", "Turn 3 Response")

    if engine.current_turn != 3:
        raise AssertionError(f"Expected current turn 3, got {engine.current_turn}")

    # Step backward
    t2 = engine.step_backward()
    if engine.current_turn != 2 or t2.prompt != "Turn 2 Prompt":
        raise AssertionError("Step backward failed")

    t1 = engine.step_backward()
    if engine.current_turn != 1:
        raise AssertionError("Step backward to 1 failed")

    # Step backward past 1 returns None
    t0 = engine.step_backward()
    if t0 is not None or engine.current_turn != 1:
        raise AssertionError("Step backward past start should return None")

    # Step forward
    engine.step_forward()
    if engine.current_turn != 2:
        raise AssertionError("Step forward failed")

    # Direct jump
    engine.jump_to_turn(3)
    if engine.current_turn != 3:
        raise AssertionError("Jump to turn failed")


def case_replay_vcr_mock_runner() -> None:
    """Verifies VCR Mock Runner records and replays tool outputs deterministically with 0 tokens."""
    vcr = csm_core.CachedToolRunner()

    args = {"path": "src/main.py", "pattern": "def authenticate"}
    vcr.record_tool_call(
        turn_seq=4,
        tool_name="grep_search",
        args=args,
        stdout="def authenticate(user, password):\n",
        stderr="",
        exit_code=0,
        duration_ms=4.2
    )

    if vcr.total_recorded_calls != 1:
        raise AssertionError("VCR recording count mismatch")

    # Replay matching call
    replayed = vcr.replay_tool_call(turn_seq=4, tool_name="grep_search", args=args)
    if not replayed or "def authenticate" not in replayed.stdout or replayed.exit_code != 0:
        raise AssertionError(f"VCR replay failed: {replayed}")

    # Replay mismatch arguments returns None (cache miss)
    mismatch = vcr.replay_tool_call(turn_seq=4, tool_name="grep_search", args={"path": "other.py"})
    if mismatch is not None:
        raise AssertionError("VCR should have missed on different args")


def case_replay_decoupled_rollback() -> None:
    """Verifies surgical decoupled rollback: code-only, context-only, and fork."""
    engine = csm_core.ReplayEngine(session_id="ses-rollback-001")

    # Turn 1: edits main.py
    engine.add_turn(1, "Create main", "Created", file_mutations={"main.py": "print('hello v1')"})

    # Turn 2: edits main.py and auth.py
    engine.add_turn(2, "Add auth", "Added", file_mutations={"main.py": "print('hello v2')", "auth.py": "def auth(): pass"})

    # Turn 3: edits main.py with syntax error
    engine.add_turn(3, "Break main", "Broken", file_mutations={"main.py": "print(BROKEN SYNTAX)"})

    # Test 1: Restore Code Only to Turn 2 (Plan was sound, revert syntax error, keep context at Turn 3)
    restored_code = engine.restore_code_only(target_turn=2)
    if restored_code["main.py"] != "print('hello v2')":
        raise AssertionError(f"Code-only restore main.py mismatch: {restored_code['main.py']}")
    if "auth.py" not in restored_code:
        raise AssertionError("Code-only restore missing auth.py")
    if engine.current_turn != 3:
        raise AssertionError(f"Chat context should NOT have rolled back: current_turn={engine.current_turn}")

    # Test 2: Restore Context Only to Turn 1 (Code is good, conversational drift rewind)
    new_turn = engine.restore_context_only(target_turn=1)
    if new_turn != 1 or engine.current_turn != 1:
        raise AssertionError(f"Context-only restore failed: {engine.current_turn}")

    # Test 3: Restore Both & Fork
    new_branch, forked_files = engine.restore_both_and_fork(
        target_turn=2,
        new_branch_name="speculative_auth_branch",
        modified_prompt="Let's implement auth with JWT instead"
    )
    if new_branch != "speculative_auth_branch" or engine.active_branch != "speculative_auth_branch":
        raise AssertionError("Fork branch creation failed")
    if forked_files["main.py"] != "print('hello v2')":
        raise AssertionError("Forked file restoration mismatch")
    if engine.current_turn != 3:  # Target turn 2 + fork turn 3
        raise AssertionError(f"Expected fork turn sequence 3, got {engine.current_turn}")
    if engine.turns[3].prompt != "Let's implement auth with JWT instead":
        raise AssertionError("Altered fork prompt not recorded")


# =============================================================================
# Main Test Harness
# =============================================================================

def main() -> int:
    cases = [
        ("scale indexer hot window (7-day filter)", case_scale_indexer_hot_window),
        ("scale indexer delta scan (high-water mark)", case_scale_indexer_delta_scan),
        ("scale indexer atomic disk cache", case_scale_indexer_atomic_cache),
        ("cluster 6+1 fanout & reserve slots", case_cluster_6_plus_1_fanout),
        ("single-writer pin lease & proposal queue", case_single_writer_pin_lease),
        ("append-only write file monotonic sequence", case_append_only_write_file),
        ("durability triumvirate (TidyUP -> TidyUP2 -> BootUP)", case_durability_triumvirate),
        ("replay discrete turn stepping", case_replay_discrete_stepping),
        ("replay vcr mock runner (zero-token replay)", case_replay_vcr_mock_runner),
        ("replay decoupled rollback (code vs context vs fork)", case_replay_decoupled_rollback),
    ]

    tmp = Path(tempfile.mkdtemp(prefix="csm_scale_test_"))
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

    print(f"\nPhase 2 & Scale Architecture Suite: {passed}/{len(cases)} passed hermetically.")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
