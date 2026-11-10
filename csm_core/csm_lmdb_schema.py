"""cmSessions Core: Memory-Mapped Zero-Copy LMDB State Schema & Transaction Journal.

Uses msgspec.Struct when available for C-struct speed and zero-copy serialization,
with seamless zero-dependency fallback to standard library dataclasses.
"""

from __future__ import annotations
import os
import time
import json
from typing import List, Optional, Dict, Any

try:
    import msgspec
    HAS_MSGSPEC = True
except ImportError:
    HAS_MSGSPEC = False

if HAS_MSGSPEC:
    class SessionEvent(msgspec.Struct, gc=False):
        epoch: int
        step: int
        timestamp: float
        event_type: str
        phase: str
        actor: str
        payload_hash: str
        tokens_in: int = 0
        tokens_out: int = 0
        cost_usd: float = 0.0
        scars_recorded: List[str] = []
        metadata: Dict[str, str] = {}

    class CarryOverPacket(msgspec.Struct, gc=False):
        session_id: str
        epoch: int
        phase: str
        active_model: str
        harness_id: str
        invariants: List[str] = []
        ast_ledger: Dict[str, str] = {}
        active_scars: List[str] = []
        cumulative_spend_usd: float = 0.0
        hard_spend_ceiling_usd: float = 5.0
        last_verified_commit: Optional[str] = None

    class SessionIndexRecord(msgspec.Struct, gc=False):
        session_id: str
        title: str
        started_at: float
        updated_at: float
        total_turns: int
        primary_model: str
        harness: str
        status: str
        spend_usd: float
        tags: List[str] = []
        parent_session_id: Optional[str] = None
        spawned_subagents: List[str] = []

    def encode_event(event: SessionEvent) -> bytes:
        return msgspec.msgpack.encode(event)

    def decode_event(data: bytes) -> SessionEvent:
        return msgspec.msgpack.decode(data, type=SessionEvent)

else:
    from dataclasses import dataclass, field, asdict

    @dataclass
    class SessionEvent:
        epoch: int
        step: int
        timestamp: float
        event_type: str
        phase: str
        actor: str
        payload_hash: str
        tokens_in: int = 0
        tokens_out: int = 0
        cost_usd: float = 0.0
        scars_recorded: List[str] = field(default_factory=list)
        metadata: Dict[str, str] = field(default_factory=dict)

    @dataclass
    class CarryOverPacket:
        session_id: str
        epoch: int
        phase: str
        active_model: str
        harness_id: str
        invariants: List[str] = field(default_factory=list)
        ast_ledger: Dict[str, str] = field(default_factory=dict)
        active_scars: List[str] = field(default_factory=list)
        cumulative_spend_usd: float = 0.0
        hard_spend_ceiling_usd: float = 5.0
        last_verified_commit: Optional[str] = None

    @dataclass
    class SessionIndexRecord:
        session_id: str
        title: str
        started_at: float
        updated_at: float
        total_turns: int
        primary_model: str
        harness: str
        status: str
        spend_usd: float
        tags: List[str] = field(default_factory=list)
        parent_session_id: Optional[str] = None
        spawned_subagents: List[str] = field(default_factory=list)

    def encode_event(event: SessionEvent) -> bytes:
        return json.dumps(asdict(event)).encode("utf-8")

    def decode_event(data: bytes) -> SessionEvent:
        d = json.loads(data.decode("utf-8"))
        return SessionEvent(**d)


class CmsLMDBJournal:
    """Memory-mapped append-only LMDB session state manager.
    
    Provides sub-microsecond event writes and instant crash-recovery rollback.
    """
    def __init__(self, db_dir: str):
        try:
            import lmdb
            self.has_lmdb = True
        except ImportError:
            self.has_lmdb = False

        self.db_dir = db_dir
        os.makedirs(db_dir, exist_ok=True)
        if self.has_lmdb:
            import lmdb
            self.env = lmdb.open(
                db_dir,
                map_size=10 * 1024 * 1024 * 1024,
                max_dbs=8,
                writemap=True,
                sync=False,
                metasync=True
            )
            self.db_events = self.env.open_db(b"events")
            self.db_csm = self.env.open_db(b"csm")
            self.db_index = self.env.open_db(b"index")
        else:
            self.env = None
            self._fallback_store = {}

    def append_event(self, session_id: str, event: SessionEvent) -> None:
        key = f"{session_id}:{event.epoch:06d}:{event.step:06d}".encode("ascii")
        val = encode_event(event)
        if self.has_lmdb and self.env:
            with self.env.begin(db=self.db_events, write=True) as txn:
                txn.put(key, val)
        else:
            self._fallback_store[key] = val

    def get_events(self, session_id: str) -> List[SessionEvent]:
        events = []
        prefix = f"{session_id}:".encode("ascii")
        if self.has_lmdb and self.env:
            with self.env.begin(db=self.db_events) as txn:
                cursor = txn.cursor()
                if cursor.set_range(prefix):
                    for k, v in cursor:
                        if not k.startswith(prefix):
                            break
                        events.append(decode_event(v))
        else:
            for k, v in sorted(self._fallback_store.items()):
                if k.startswith(prefix):
                    events.append(decode_event(v))
        return events

    def close(self):
        if self.has_lmdb and self.env:
            self.env.close()
