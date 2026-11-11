"""cmSessions Discrete Replay & Decoupled Rollback Engine.

Implements Pillar 3 of cmSessions Architecture:
- Discrete turn boundary state machine (K -> K+1).
- VCR Mock Runner (CachedToolRunner) replaying historical tools with 0 token spend.
- Decoupled Rollback Handler:
  * restore_code_only(turn_n) using checkpoints and reverse diffs.
  * restore_context_only(turn_n) rewinding conversational window.
  * restore_both_and_fork(turn_n) atomic rollback and speculative branching.
"""

from __future__ import annotations
import os
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict


class ReplayError(Exception):
    """Base exception for replay and rollback operations."""
    pass


@dataclass
class ToolExecutionRecord:
    turn_seq: int
    tool_name: str
    args: Dict[str, Any]
    arg_hash: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float


@dataclass
class TurnCheckpoint:
    turn_seq: int
    checkpoint_id: str
    parent_id: Optional[str]
    prompt: str
    response: str
    thinking_trace: str
    tool_records: List[ToolExecutionRecord] = field(default_factory=list)
    file_snapshots: Dict[str, str] = field(default_factory=dict)  # rel_path -> blob_hash
    timestamp: float = field(default_factory=time.time)
    tokens_in: int = 0
    tokens_out: int = 0
    usd_cost: float = 0.0


class CachedToolRunner:
    """VCR Mock Runner executing zero-side-effect, zero-token replay."""

    def __init__(self):
        # Tape lookup: (turn_seq, tool_name, arg_hash) -> ToolExecutionRecord
        self._tape: Dict[Tuple[int, str, str], ToolExecutionRecord] = {}

    @staticmethod
    def compute_arg_hash(args: Dict[str, Any]) -> str:
        """Computes deterministic 16-character Blake2b hash of tool arguments."""
        canonical_json = json.dumps(args, sort_keys=True).encode("utf-8")
        return hashlib.blake2b(canonical_json, digest_size=8).hexdigest()

    def record_tool_call(
        self,
        turn_seq: int,
        tool_name: str,
        args: Dict[str, Any],
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_ms: float = 1.0
    ) -> ToolExecutionRecord:
        """Records a live tool execution to the VCR tape."""
        arg_hash = self.compute_arg_hash(args)
        rec = ToolExecutionRecord(
            turn_seq=turn_seq,
            tool_name=tool_name,
            args=args,
            arg_hash=arg_hash,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms
        )
        self._tape[(turn_seq, tool_name, arg_hash)] = rec
        return rec

    def replay_tool_call(
        self,
        turn_seq: int,
        tool_name: str,
        args: Dict[str, Any]
    ) -> Optional[ToolExecutionRecord]:
        """Plays back recorded tool output without re-executing external commands."""
        arg_hash = self.compute_arg_hash(args)
        return self._tape.get((turn_seq, tool_name, arg_hash))

    @property
    def total_recorded_calls(self) -> int:
        return len(self._tape)


class ReplayEngine:
    """Discrete Turn-by-Turn Replay & Rollback State Machine."""

    def __init__(self, session_id: str, workspace_root: Optional[str] = None):
        self.session_id = session_id
        self.workspace_root = Path(workspace_root) if workspace_root else Path(".")
        self.vcr_runner = CachedToolRunner()
        
        # Turn sequence: turn_seq -> TurnCheckpoint
        self.turns: Dict[int, TurnCheckpoint] = {}
        # DAG parent tracking: checkpoint_id -> TurnCheckpoint
        self.checkpoints: Dict[str, TurnCheckpoint] = {}
        
        # File blob store: blob_hash -> file_content (bytes or str)
        self.blob_store: Dict[str, str] = {}
        
        # Current playback position
        self.current_turn: int = 0
        self.active_branch: str = "main"
        self.branches: Dict[str, str] = {}  # branch_name -> checkpoint_id

    def add_turn(
        self,
        turn_seq: int,
        prompt: str,
        response: str,
        thinking_trace: str = "",
        file_mutations: Optional[Dict[str, str]] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        usd_cost: float = 0.0
    ) -> TurnCheckpoint:
        """Appends a discrete turn to the session DAG."""
        parent_id = self.turns[turn_seq - 1].checkpoint_id if turn_seq > 1 and (turn_seq - 1) in self.turns else None
        
        # Compute content-addressed turn ID
        canonical = f"{self.session_id}:{turn_seq}:{prompt}:{response}"
        cid = f"cp_{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"

        snapshots: Dict[str, str] = {}
        if file_mutations:
            for path, content in file_mutations.items():
                bhash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
                self.blob_store[bhash] = content
                snapshots[path] = bhash

        turn = TurnCheckpoint(
            turn_seq=turn_seq,
            checkpoint_id=cid,
            parent_id=parent_id,
            prompt=prompt,
            response=response,
            thinking_trace=thinking_trace,
            file_snapshots=snapshots,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            usd_cost=usd_cost
        )
        self.turns[turn_seq] = turn
        self.checkpoints[cid] = turn
        self.current_turn = turn_seq
        self.branches[self.active_branch] = cid
        return turn

    # -------------------------------------------------------------------------
    # Discrete Stepping Controls
    # -------------------------------------------------------------------------

    def step_forward(self) -> Optional[TurnCheckpoint]:
        """Steps forward K -> K+1."""
        target = self.current_turn + 1
        if target in self.turns:
            self.current_turn = target
            return self.turns[target]
        return None

    def step_backward(self) -> Optional[TurnCheckpoint]:
        """Steps backward K -> K-1."""
        target = self.current_turn - 1
        if target >= 1 and target in self.turns:
            self.current_turn = target
            return self.turns[target]
        return None

    def jump_to_turn(self, turn_seq: int) -> Optional[TurnCheckpoint]:
        """Jumps directly to designated turn sequence."""
        if turn_seq in self.turns:
            self.current_turn = turn_seq
            return self.turns[turn_seq]
        return None

    # -------------------------------------------------------------------------
    # Decoupled Rollback Matrix
    # -------------------------------------------------------------------------

    def restore_code_only(self, target_turn: int) -> Dict[str, str]:
        """Restores file contents to target turn state WITHOUT changing chat context.
        
        Returns dictionary of restored files: rel_path -> content.
        """
        if target_turn not in self.turns:
            raise ReplayError(f"Target turn {target_turn} does not exist.")

        restored_files: Dict[str, str] = {}
        # Reconstruct file state up to target_turn
        for seq in range(1, target_turn + 1):
            if seq in self.turns:
                for path, bhash in self.turns[seq].file_snapshots.items():
                    restored_files[path] = self.blob_store[bhash]

        # Note: self.current_turn remains unchanged! Chat is NOT rolled back.
        return restored_files

    def restore_context_only(self, target_turn: int) -> int:
        """Rewinds conversational pointer to target turn WITHOUT reverting disk files.
        
        Returns new current turn pointer.
        """
        if target_turn not in self.turns:
            raise ReplayError(f"Target turn {target_turn} does not exist.")

        self.current_turn = target_turn
        return self.current_turn

    def restore_both_and_fork(
        self,
        target_turn: int,
        new_branch_name: str,
        modified_prompt: Optional[str] = None
    ) -> Tuple[str, Dict[str, str]]:
        """Atomic rollback: reverts code, rewinds context, and forks a new branch.
        
        Returns (new_branch_name, restored_files).
        """
        if target_turn not in self.turns:
            raise ReplayError(f"Target turn {target_turn} does not exist.")

        # 1. Restore code state
        restored_files = self.restore_code_only(target_turn)

        # 2. Rewind context
        self.current_turn = target_turn

        # 3. Fork new branch
        target_cid = self.turns[target_turn].checkpoint_id
        self.active_branch = new_branch_name
        self.branches[new_branch_name] = target_cid

        if modified_prompt:
            # Fork turn with altered prompt
            fork_seq = target_turn + 1
            self.add_turn(
                turn_seq=fork_seq,
                prompt=modified_prompt,
                response="[Fork Initialized from Turn " + str(target_turn) + "]"
            )

        return new_branch_name, restored_files
