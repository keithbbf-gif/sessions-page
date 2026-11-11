"""cmSessions Hierarchical Cluster Topology & PIN Lease Engine.

Implements Pillar 2 of cmSessions Architecture:
- 6+1 Fan-Out cluster tree data model (1 Lead + 6 Workers + 2 Reserve slots).
- Single-Writer PIN lease manager on live tree (proposals in sandboxes).
- Append-only write file tracker with monotonic sequence numbers (issued -> extended -> released).
- Durability Triumvirate: TidyUP compaction, TidyUP2 adversarial porosity audit, BootUP SEED HMAC validator.
"""

from __future__ import annotations
import os
import time
import json
import hmac
import hashlib
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict


class ClusterError(Exception):
    """Base exception for cluster topology and lease violations."""
    pass


class FanOutCeilingExceededError(ClusterError):
    """Raised when attempting to add workers exceeding the 6+1 fan-out ceiling."""
    pass


class PinLeaseViolationError(ClusterError):
    """Raised when an unauthenticated agent attempts to write to the live master tree."""
    pass


class VerificationFailureError(ClusterError):
    """Raised when TidyUP, TidyUP2, or BootUP fails verification."""
    pass


@dataclass
class AgentMember:
    agent_id: str
    role: str  # "lead", "worker", "critic", "witness", "orc"
    model: str
    door: str
    sandbox_dir: str
    status: str = "SPAWNED"  # SPAWNED, ACTIVE, COMPACTED, SEALED, FAILED
    write_file_seq: int = 0
    leases_held: List[str] = field(default_factory=list)
    tokens_spent: int = 0
    cost_usd: float = 0.0


@dataclass
class CommitProposal:
    proposal_id: str
    agent_id: str
    cluster_id: str
    summary: str
    target_paths: List[str]
    diff_hash: str
    created_at: float = field(default_factory=time.time)
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, MERGED


@dataclass
class SeedArtifact:
    cluster_id: str
    lead_agent_id: str
    goal: str
    decisions: List[str]
    modified_paths: List[str]
    open_questions: List[str]
    artifact_pointers: Dict[str, str]
    scars_recorded: List[str]
    timestamp: float
    length_bytes: int
    hmac_sha256: str


class ClusterNode:
    """Represents a 6+1 Hierarchical Cluster Node."""

    MAX_WORKERS = 6
    RESERVE_SLOTS = 2  # Total hard capacity: 8 + 1 Lead

    def __init__(self, cluster_id: str, name: str, lead_agent_id: str, project_id: str):
        self.cluster_id = cluster_id
        self.name = name
        self.lead_agent_id = lead_agent_id
        self.project_id = project_id
        
        # Members dictionary: agent_id -> AgentMember
        self.members: Dict[str, AgentMember] = {}
        # Nested subclusters: subcluster_id -> ClusterNode
        self.subclusters: Dict[str, ClusterNode] = {}
        
        # Register the lead immediately
        self.lead = AgentMember(
            agent_id=lead_agent_id,
            role="lead",
            model="default",
            door="cosmos",
            sandbox_dir=f"sandboxes/{cluster_id}/lead"
        )
        self.members[lead_agent_id] = self.lead

    def add_worker(
        self,
        agent_id: str,
        model: str,
        door: str,
        role: str = "worker",
        use_reserve: bool = False
    ) -> AgentMember:
        """Adds a direct worker to the cluster enforcing the 6+1 rule."""
        current_workers = [m for m in self.members.values() if m.role != "lead"]
        max_allowed = self.MAX_WORKERS + (self.RESERVE_SLOTS if use_reserve else 0)

        if len(current_workers) >= max_allowed:
            raise FanOutCeilingExceededError(
                f"Cluster {self.cluster_id} exceeded fan-out ceiling ({len(current_workers)}/{max_allowed}). "
                f"Refusing to violate 6+1 fan-out rule. Spawn a nested subcluster instead."
            )

        worker = AgentMember(
            agent_id=agent_id,
            role=role,
            model=model,
            door=door,
            sandbox_dir=f"sandboxes/{self.cluster_id}/{agent_id}"
        )
        self.members[agent_id] = worker
        return worker

    def add_subcluster(self, child_cluster: ClusterNode) -> None:
        """Nests an existing cluster under this lead (Cluster of Clusters / Orchestrator)."""
        if len(self.subclusters) >= self.MAX_WORKERS:
            raise FanOutCeilingExceededError(
                f"Cluster {self.cluster_id} cannot nest more than {self.MAX_WORKERS} subclusters."
            )
        self.subclusters[child_cluster.cluster_id] = child_cluster

    def get_roster(self) -> Dict[str, Any]:
        """Returns the complete roster of this cluster and all nested children."""
        return {
            "cluster_id": self.cluster_id,
            "name": self.name,
            "lead": asdict(self.lead),
            "worker_count": len([m for m in self.members.values() if m.role != "lead"]),
            "members": {aid: asdict(m) for aid, m in self.members.items()},
            "subclusters": {cid: sc.get_roster() for cid, sc in self.subclusters.items()}
        }


class SingleWriterPinManager:
    """Manages Single-Writer Live Tree Exclusion and Candidate Proposal Queues."""

    def __init__(self, default_lease_duration_s: float = 300.0):
        self.default_lease_duration = default_lease_duration_s
        self.pin_holder_id: Optional[str] = None
        self.lease_expires_at: float = 0.0
        
        # Path leases: path -> (agent_id, expires_at)
        self.path_claims: Dict[str, tuple[str, float]] = {}
        
        # Candidate proposal queue
        self.proposals: Dict[str, CommitProposal] = {}
        
        # Append-only write file logs: agent_id -> list of (seq, event, timestamp)
        self.write_file_streams: Dict[str, List[Dict[str, Any]]] = {}

    def acquire_pin(self, agent_id: str, role: str, duration_s: Optional[float] = None) -> bool:
        """Awards the Live Tree PIN to a designated Lead.
        
        Only Leads or Orchestrators may acquire the master PIN. Workers must submit proposals.
        """
        now = time.time()
        if role not in ("lead", "orc", "manager"):
            raise PinLeaseViolationError(
                f"Agent {agent_id} with role '{role}' cannot hold the Live Tree PIN. "
                "Only cluster Leads may write directly to the live tree. Workers must submit proposals."
            )

        if self.pin_holder_id and now < self.lease_expires_at and self.pin_holder_id != agent_id:
            return False  # Active lease held by another lead

        dur = duration_s or self.default_lease_duration
        self.pin_holder_id = agent_id
        self.lease_expires_at = now + dur
        return True

    def release_pin(self, agent_id: str) -> bool:
        """Releases the Live Tree PIN."""
        if self.pin_holder_id == agent_id:
            self.pin_holder_id = None
            self.lease_expires_at = 0.0
            return True
        return False

    def assert_write_privilege(self, agent_id: str, path: str) -> None:
        """Guards live tree mutations. Fails closed if PIN is missing or path is contested."""
        now = time.time()
        # 1. Master PIN check for live master tree
        if self.pin_holder_id != agent_id or now >= self.lease_expires_at:
            raise PinLeaseViolationError(
                f"Agent {agent_id} denied write to live path '{path}'. Live Tree PIN not held or lease expired."
            )

        # 2. Path exclusion claim check
        if path in self.path_claims:
            claim_holder, expires = self.path_claims[path]
            if claim_holder != agent_id and now < expires:
                raise PinLeaseViolationError(
                    f"Path '{path}' is claimed by agent {claim_holder} until {expires}."
                )

    def append_write_file_event(self, agent_id: str, action: str, details: Dict[str, Any]) -> int:
        """Appends a monotonic sequence event to an agent's published write file."""
        if agent_id not in self.write_file_streams:
            self.write_file_streams[agent_id] = []

        stream = self.write_file_streams[agent_id]
        next_seq = len(stream) + 1

        record = {
            "seq": next_seq,
            "agent_id": agent_id,
            "action": action,  # "issued", "extended", "released", "claim"
            "details": details,
            "timestamp": time.time()
        }
        stream.append(record)
        return next_seq

    def submit_proposal(
        self,
        agent_id: str,
        cluster_id: str,
        summary: str,
        target_paths: List[str],
        diff_content: str
    ) -> CommitProposal:
        """Submits a candidate proposal from a worker's sandbox queue."""
        diff_hash = hashlib.sha256(diff_content.encode("utf-8")).hexdigest()
        proposal_id = f"prop_{hashlib.blake2b(f'{agent_id}{time.time()}'.encode()).hexdigest()[:12]}"

        prop = CommitProposal(
            proposal_id=proposal_id,
            agent_id=agent_id,
            cluster_id=cluster_id,
            summary=summary,
            target_paths=target_paths,
            diff_hash=diff_hash
        )
        self.proposals[proposal_id] = prop
        return prop

    def merge_proposal(self, pin_holder_id: str, proposal_id: str) -> bool:
        """Merges a pending proposal into the live master tree."""
        self.assert_write_privilege(pin_holder_id, "live_master_tree")
        if proposal_id not in self.proposals:
            return False

        prop = self.proposals[proposal_id]
        if prop.status != "PENDING":
            return False

        prop.status = "MERGED"
        return True


class DurabilityTriumvirate:
    """Implements TidyUP, TidyUP2, and BootUP HMAC validation."""

    @staticmethod
    def tidy_up(
        cluster_id: str,
        lead_agent_id: str,
        goal: str,
        decisions: List[str],
        modified_paths: List[str],
        open_questions: List[str],
        artifact_pointers: Dict[str, str],
        scars_recorded: List[str],
        session_key: bytes
    ) -> SeedArtifact:
        """TidyUP: Compresses active session/cluster into a signed SEED artifact."""
        now = time.time()
        core_data = {
            "cluster_id": cluster_id,
            "lead_agent_id": lead_agent_id,
            "goal": goal,
            "decisions": decisions,
            "modified_paths": sorted(modified_paths),
            "open_questions": open_questions,
            "artifact_pointers": artifact_pointers,
            "scars_recorded": sorted(scars_recorded),
            "timestamp": now
        }
        canonical_bytes = json.dumps(core_data, sort_keys=True).encode("utf-8")
        computed_hmac = hmac.new(session_key, canonical_bytes, hashlib.sha256).hexdigest()

        return SeedArtifact(
            cluster_id=cluster_id,
            lead_agent_id=lead_agent_id,
            goal=goal,
            decisions=decisions,
            modified_paths=modified_paths,
            open_questions=open_questions,
            artifact_pointers=artifact_pointers,
            scars_recorded=scars_recorded,
            timestamp=now,
            length_bytes=len(canonical_bytes),
            hmac_sha256=computed_hmac
        )

    @staticmethod
    def tidy_up_2(
        seed: SeedArtifact,
        actual_files_on_disk: Set[str],
        untracked_temp_files: Set[str]
    ) -> Dict[str, Any]:
        """TidyUP2: Adversarially re-measures porosity and occupancy."""
        claimed_paths = set(seed.modified_paths)
        
        # 1. Porosity: unsealed edges or untracked temp files left behind
        porosity_score = len(untracked_temp_files)
        
        # 2. Occupancy: claimed modified files that actually exist
        missing_paths = claimed_paths - actual_files_on_disk
        occupancy_ratio = 1.0 if not claimed_paths else (len(claimed_paths - missing_paths) / len(claimed_paths))

        is_verified = (porosity_score == 0) and (len(missing_paths) == 0) and (occupancy_ratio == 1.0)

        return {
            "verified": is_verified,
            "porosity_score": porosity_score,
            "untracked_temp_files": list(untracked_temp_files),
            "occupancy_ratio": occupancy_ratio,
            "missing_claimed_paths": list(missing_paths),
            "verdict": "VERIFIED" if is_verified else "POROSITY_FAILED"
        }

    @staticmethod
    def boot_up(seed: SeedArtifact, session_key: bytes) -> bool:
        """BootUP: Validates SEED HMAC and byte length before launching new/respawned agent."""
        core_data = {
            "cluster_id": seed.cluster_id,
            "lead_agent_id": seed.lead_agent_id,
            "goal": seed.goal,
            "decisions": seed.decisions,
            "modified_paths": sorted(seed.modified_paths),
            "open_questions": seed.open_questions,
            "artifact_pointers": seed.artifact_pointers,
            "scars_recorded": sorted(seed.scars_recorded),
            "timestamp": seed.timestamp
        }
        canonical_bytes = json.dumps(core_data, sort_keys=True).encode("utf-8")

        # 1. Byte length invariant
        if len(canonical_bytes) != seed.length_bytes:
            raise VerificationFailureError(
                f"BootUP rejected: SEED byte length mismatch (expected {seed.length_bytes}, got {len(canonical_bytes)})."
            )

        # 2. HMAC cryptographic signature check
        expected_hmac = hmac.new(session_key, canonical_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hmac, seed.hmac_sha256):
            raise VerificationFailureError("BootUP rejected: SEED HMAC cryptographic signature verification failed.")

        return True
