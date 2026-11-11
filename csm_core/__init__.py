"""cmSessions Core Engine: High-performance state journal, failover kernel, and governance proxy.

Components:
- csm_lmdb_schema: Memory-mapped zero-copy LMDB transaction journal and event structs.
- deterministic_failover: Zero-token CPU-level exception interceptor enforcing the Law of Local Silicon.
- dual_lock_proxy: Pre-flight assertion handshake + circuit breaker enforcing RULE-H1 through RULE-H5.
"""

from __future__ import annotations

from .csm_lmdb_schema import (
    SessionEvent,
    CarryOverPacket,
    SessionIndexRecord,
    CmsLMDBJournal,
    encode_event,
    decode_event,
    HAS_MSGSPEC,
)
from .deterministic_failover import DeterministicFailoverKernel
from .dual_lock_proxy import (
    DualLockProxy,
    PreFlightAssertionException,
    CircuitBreakerTrippedException,
)
from .scale_indexer import ScaleIndexer
from .cluster_topology import (
    ClusterNode,
    AgentMember,
    CommitProposal,
    SeedArtifact,
    SingleWriterPinManager,
    DurabilityTriumvirate,
    ClusterError,
    FanOutCeilingExceededError,
    PinLeaseViolationError,
    VerificationFailureError,
)
from .replay_engine import (
    ReplayEngine,
    CachedToolRunner,
    ToolExecutionRecord,
    TurnCheckpoint,
    ReplayError,
)

__all__ = [
    "SessionEvent",
    "CarryOverPacket",
    "SessionIndexRecord",
    "CmsLMDBJournal",
    "encode_event",
    "decode_event",
    "HAS_MSGSPEC",
    "DeterministicFailoverKernel",
    "DualLockProxy",
    "PreFlightAssertionException",
    "CircuitBreakerTrippedException",
    "ScaleIndexer",
    "ClusterNode",
    "AgentMember",
    "CommitProposal",
    "SeedArtifact",
    "SingleWriterPinManager",
    "DurabilityTriumvirate",
    "ClusterError",
    "FanOutCeilingExceededError",
    "PinLeaseViolationError",
    "VerificationFailureError",
    "ReplayEngine",
    "CachedToolRunner",
    "ToolExecutionRecord",
    "TurnCheckpoint",
    "ReplayError",
]
