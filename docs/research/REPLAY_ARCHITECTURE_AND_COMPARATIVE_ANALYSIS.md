# REPLAY: Session Replay, Time-Travel Debugging, and State Scrubbing in Multi-Model AI Agent Systems
**Comprehensive Architecture Specification & Comparative Product Analysis**  
*Target Platforms: COSMOS Engine, cmSessions, cmCode, cmClusters, and the COSMOS Deterministic Harness*

---

## Executive Summary

As AI agent systems evolve from single-prompt completions to long-running, multi-turn, multi-tool autonomous workflows, **replayability** has become the primary bottleneck for reliability, debugging, benchmark evaluation, and user trust. 

When an autonomous agent makes a catastrophic coding error at Turn 7 of an 8-turn budget, burns \$2.50 in tokens, or hallucinates an incorrect shell command, developers cannot afford to "start over from scratch" or blindly re-prompt the model hoping for non-deterministic luck. They need **Time-Travel Debugging**: the ability to scrub backward to Turn 6, inspect the exact context window and workspace diff, modify either the user directive or the tool response, and branch into a new execution line while optionally reusing deterministic cached results for Turns 1–5.

This document delivers:
1. **Comparative Product Analysis**: Reverse engineering and architectural comparison across observability platforms (LangSmith, Langfuse, Arize Phoenix, Braintrust, Helicone), AI IDEs / agents (Cursor, Windsurf, Claude Code), and deterministic UI state-machines (Redux DevTools, rrweb).
2. **Deep-Dive Mechanics**: Analysis of Deterministic (VCR/mocked) vs Non-Deterministic replay, Branching State DAGs vs Linear histories, and Multi-layer State Capture (Context, Workspace File Diffs, Process Side Effects, Token/Spend Meters).
3. **Feature Assessment**: A ruthless evaluation of signal vs bloat—identifying what real developers actually use versus flashy gimmicks that derail agent harnesses.
4. **Ecosystem & Architectural Blueprint**: Concrete integration across `cmSessions`, `cmCode`, `COSMOS` Core, the `Harness`, and `cmClusters`, complete with production-ready JSON/dataclass schemas, state machines, and UX interaction workflows.

---

## 1. Comparative Product Analysis

### 1.1 State-of-the-Art Comparative Matrix

| Platform / Tool | Primary Replay Paradigm | Tool Output Handling | Workspace / Code State Tracking | Branching / Scrubbing Model | Cost & Token Telemetry |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LangSmith** | Run Tree Playback & Playground Fork | Live re-execution or Mocked via playground run config | None (assumes cloud APIs, no workspace state) | Non-destructive fork into Playground; original run tree is immutable | Granular per-step token, latency, and cost ledger |
| **Langfuse** | Session Traces & Turn Observation Tree | Read-only inspect; "Send to Playground" for re-evaluation | None (pure API/prompt trace) | Re-run turn in playground; session itself is immutable append-only | Detailed token and USD spend tracking per span/turn |
| **Arize Phoenix** | OpenTelemetry Span Graph & Eval Replay | Read-only span inspection; re-execute evaluations against recorded inputs | None | Read-only timeline; fork spans into playground | Token counts per span; focus on evaluation metrics (accuracy/toxicity) |
| **Cursor** | Checkpoint Timeline & Shadow Worktrees | Re-executed on resume; tool calls not mock-replayed | Git-based internal snapshots & reverse patch application | Linear rollback with restore; can diverge into new checkpoint chain | Local chat token tracking; no tool mock caching |
| **Windsurf (Codeium)** | Cascade Flow & Turn Undo | Live tool execution; undo discards step outputs | In-memory & disk rollback via Cascade engine | Linear rollback; preserves conversation if requested | Session-level token counter |
| **Claude Code** | `/rewind` Checkpoint Menu & JSONL Transcript | Live shell/tool calls; cannot undo bash side effects | Built-in file tool snapshots (up to 100 turns in `.jsonl` state) | Granular: restore code, conversation, or both; summarize from/to turn | Per-turn input/output tokens, cache hits, and spend estimate |
| **Braintrust / Helicone** | Proxy-level Replay & Prompt Playground | Proxy caching (`Helicone-Cache-Enabled: true`); VCR cassette replay | None (stateless proxy layer) | Playground fork from recorded payload | Exact request/response tokens, dollar cost, cache hit flags |
| **Redux DevTools / rrweb** | Deterministic State-Action Stream Replay | Pure reducer action replays; rrweb replays DOM mutation events | Complete serialized state tree delta per action | Tree/Linear scrubbing: `JUMP_TO_STATE`, `REORDER`, `COMMIT`, `SWEEP` | N/A (Frontend memory / DOM nodes) |

---

### 1.2 Deep-Dive into Platforms & Patterns

#### 1. LangSmith (LangChain Ecosystem)
- **Mechanics**: Every agent interaction is captured as a hierarchical Run Tree (`Run` $\rightarrow$ child `Runs` / `ToolCalls`). Replay operates via two modes:
  1. *Run Replay*: Re-invoking the agent chain from a specific intermediate run node using stored inputs.
  2. *Open in Playground*: Extracts the exact prompt payload, tools definitions, and model parameters into an interactive web playground.
- **Tool Handling**: In playground, developers can toggle between mock tool responses (using the captured string) or live tool execution.
- **Limitations**: Completely disconnected from local filesystem states. If a tool was `write_file("src/main.py")`, LangSmith knows the string passed to the tool, but has zero concept of the file before, during, or after the run.

#### 2. Langfuse (Open Source Observability)
- **Mechanics**: Captures hierarchical *Traces* structured into *Generations*, *Spans*, and *Events*. Sessions group traces chronologically.
- **Scrubbing & Playback**: Provides an observation waterfall. Clicking a turn exposes the prompt template, rendered system prompt, and completion. Users can "Fork to Playground" where input variables are extracted.
- **Evaluation Replay**: A key strength of Langfuse is re-running automated evaluators (LLM-as-a-judge) over historical traces without re-running the underlying agent model.

#### 3. Arize Phoenix (OTel Native)
- **Mechanics**: Built natively on OpenTelemetry semantic conventions for GenAI. Replay is focused on observability and offline evaluation.
- **RAG & Retrieval Playback**: Phoenix records the exact embedding vectors, chunk IDs, and similarity scores returned by vector DBs at Turn $N$, enabling developers to isolate whether a failure was caused by the retrieval step or the synthesis step.

#### 4. Cursor (Shadow Workspace & Composer Checkpoints)
- **Mechanics**: Cursor creates automatic checkpoints before and after agent tool actions (especially `edit_file`, `create_file`). Checkpoints are stored in internal git-like storage structures.
- **Timeline Scrubbing**: In the Composer UI, users see a chronological feed of turns. Clicking "Restore Checkpoint" reverts the workspace to the exact file contents before that turn executed.
- **Shadow Worktrees**: Behind the scenes, Cursor leverages background worker threads and isolated git worktrees to test edits, run diagnostics, and calculate diffs before applying them to the active editor.
- **Limitation**: Non-deterministic agent loops. If you rewind 3 turns and re-run, Cursor re-prompts the model from scratch with the current files; it cannot do deterministic offline playback of tool outputs.

#### 5. Claude Code (`/rewind` and Transcripts)
- **Mechanics**: Claude Code generates an append-only JSONL transcript containing every user input, assistant reasoning block, tool invocation, and tool response.
- **The `/rewind` Menu (Esc x2)**: Offers 5 surgical rewind primitives:
  1. *Restore code and conversation*: Hard reset of both files and context.
  2. *Restore conversation only*: Resets chat context to turn $N$, but leaves current file edits intact (useful when you like the code but want to redirect the agent's explanation or next step).
  3. *Restore code only*: Reverts code back to turn $N$ while keeping the chat history (useful when code broke but you want the agent to learn from the failure without forgetting what it tried).
  4. *Summarize from here* / *Summarize up to here*: Context compaction anchored at turn $N$.
- **Critical Vulnerability**: Claude Code explicitly cannot roll back side effects executed via `Bash` (`rm`, `npm install`, `docker run`). Only built-in file editor tools are snapshot.

#### 6. Braintrust & Helicone (Proxy Caching & Tape Replay)
- **Mechanics**: These tools sit between the agent and the model provider as an HTTP proxy. 
- **Deterministic VCR Caching**: Helicone allows setting `Helicone-Cache-Enabled: true` with a custom cache key (e.g., hash of system prompt + messages + model + temperature). When replaying, identical requests return instantly with zero cost and identical outputs.
- **Playground Branching**: Allows taking a production failure, altering one system parameter, and running a comparative A/B test across 50 historical inputs.

#### 7. Redux DevTools & rrweb: The UI State-Scrubbing Gold Standard
- **The Redux Elm Architecture**:
  $$\text{State}_{t+1} = \text{Reducer}(\text{State}_t, \text{Action}_t)$$
  Replay is simply: start at initial state $S_0$, and re-apply actions $A_0 \dots A_N$.
  Key actions:
  - `JUMP_TO_STATE`: Move the active pointer to index $N$ without destroying $N+1 \dots M$.
  - `BRANCH`: Commit an action at index $N$ that diverges from $A_{N+1}$, creating a tree.
  - `REORDER`: Swap order of non-dependent actions to test commutativity.
- **rrweb (DOM Mutation Recording)**:
  - Takes a **Full Snapshot** at $t_0$ (serialized DOM tree).
  - Records **Incremental Mutations** ($t_1 \dots t_n$): DOM additions, removals, attribute mutations, text changes, mouse coordinates, and scroll positions.
  - Replay loads the snapshot into an isolated sandbox/iframe and feeds mutation events through a virtual timer.
- **Translation to AI Agents**:
  - Full Snapshot $\equiv$ Workspace file tree + Git commit hash + Environment variables + System Prompt.
  - Incremental Mutation $\equiv$ User message, Assistant reasoning/tool-call delta, Tool execution output delta, File patch diff, Token usage delta.

---

### 1.3 Analysis of the Three Foundational Replay Pillars

```
+----------------------------------------------------------------------------------------------------+
|                                      THE THREE PILLARS OF REPLAY                                   |
+------------------------------------+----------------------------------+----------------------------+
| PILLAR A: DETERMINISM              | PILLAR B: SCRUBBING & BRANCHING  | PILLAR C: STATE CAPTURE    |
| - Deterministic VCR Mode           | - Linear Rollback (Destructive)  | - Context Window Snapshot  |
| - Live Re-execution Mode           | - DAG Branching (Non-destructive)| - Workspace File Patches   |
| - Hybrid Cached-Execution Mode     | - Time-Travel Jump Pointer       | - Shell & Sandbox State    |
| - Seed & Temperature Invariance    | - Re-prompt & Divergence Fork    | - Spend & Token Accounting |
+------------------------------------+----------------------------------+----------------------------+
```

#### Pillar A: Non-Deterministic vs Deterministic Replay
In classical software, replay is 100% deterministic given identical binary inputs and seeds. In LLM agent systems, two distinct types of replay exist:
1. **Deterministic "VCR" Playback (Inspection & Regression Testing)**:
   - *Goal*: Exact reproduction of an observed run for auditing, post-mortem analysis, or UI review.
   - *Implementation*: The model provider completions and external tool responses (API queries, bash outputs, web searches) are **not** re-executed. The system reads directly from the recorded tape/journal.
   - *Latency & Cost*: Zero API cost, sub-millisecond execution.
2. **Non-Deterministic Live Replay (Exploration & Prompt Tuning)**:
   - *Goal*: "What happens if I change the instructions at Turn 3?"
   - *Implementation*: Historical turns $1 \dots 2$ use recorded state; Turn 3 injects the modified prompt; Turns $3 \dots N$ invoke the live model and live tools.
   - *Caveat*: Because LLM temperature $> 0$ (or even at temperature $= 0$ due to GPU floating-point non-determinism across inference clusters), the downstream path will immediately diverge.
3. **Hybrid "Cached-Tool" Fast-Forward (The Holy Grail)**:
   - When branching at Turn 3, if the agent issues tool calls that are pure read operations (`read_file("src/foo.py")` or `grep_search("UserSession")`), the harness intercepts the call and serves the cached result from the earlier run *if* the underlying workspace files have not changed.
   - Only destructive actions (`write_file`, shell commands) or novel tool requests are executed live.

#### Pillar B: Scrubbing, Rewinding, and Branching Models
When scrubbing backward to Turn $N$, how does the session store manage the timeline?
- **Pattern 1: Destructive Truncation (Linear Overwrite)**
  - Dropping everything from Turn $N+1$ to the end. The user edits the prompt, and the new turn becomes the new $N+1$.
  - *Pros*: Simple data structure (1D array).
  - *Cons*: Total loss of data. If the user's edit at Turn $N$ turns out to be worse than the original branch, they cannot recover the original Turns $N+1 \dots M$.
- **Pattern 2: Append-Only Directed Acyclic Graph (DAG) with Branch Pointers**
  - Turns are content-addressed nodes. Each turn references its `parent_turn_id`.
  - Rewinding to Turn $N$ and executing a new prompt simply creates a new child node with `parent_turn_id = turn_N.id`.
  - The UI maintains a pointer to `active_leaf_id`. The user can switch between branches seamlessly.
  - *Pros*: Zero data loss; supports multi-turn A/B comparisons.
  - *Cons*: Higher UI complexity; requires tree visualization and pruning policies.

#### Pillar C: State Capture (Beyond Just Chat History)
A coding agent is **not** a stateless chatbot. It has physical state in the workspace and environment. Replay must capture:
1. **Context Window State**: The exact serialized token sequence or message list derived from the journal.
2. **Workspace Files**: Full file blobs at $t_0$, plus reverse/forward unified diffs per turn.
3. **Environment & Sandbox State**: Working directory, active environment variables, path jail configurations, process exit codes.
4. **Tool Metadata**: Tool execution duration, status codes, standard output, and standard error.
5. **Cost & Spend Ledger**: Model token usage (prompt, completion, cache read tokens, cache creation tokens), billed dollars, and elapsed wall-clock latency.

---

## 2. Feature Assessment: Signal vs. Noise

When designing replay for a professional multi-harness developer tool (like COSMOS / cmSessions / cmCode), distinguishing high-utility features from over-engineered bloat is critical.

### 2.1 The Most Useful Features (Signal)

1. **Granular Decoupled Rollback (Code vs Conversation)**
   - *Why*: Developers frequently encounter two distinct failure modes:
     - Case A: The agent's code modification is correct, but its subsequent explanation or next action goes off the rails. Developer wants to keep the code, but rewind the conversation to re-prompt.
     - Case B: The conversation strategy is solid, but the file patch had a subtle syntax bug. Developer wants to revert the file to clean state, keep the conversation, and instruct the agent: "That patch broke the compiler; fix syntax error at line 42".
   - *Verdict*: **Mandatory Tier 1 Requirement.**

2. **Surgical "Fork & Diverge" at Turn N**
   - *Why*: Finding the root cause of an agent failure almost always isolates to a single prompt ambiguity or bad tool response at turn $K$. Being able to jump directly to turn $K$, edit the prompt (or edit the tool output!), and launch a child session saves enormous time and token cost.
   - *Verdict*: **Mandatory Tier 1 Requirement.**

3. **Step-by-Step VCR Playback with Side-by-Side Diff Scrubbing**
   - *Why*: Watching the code changes evolve turn-by-turn alongside the agent's internal reasoning and tool invocations is the fastest way for human engineers to verify that the agent did not introduce subtle regressions, delete comments, or edit unintended files.
   - *Verdict*: **Mandatory Tier 1 Requirement.**

4. **Offline Deterministic Audit & Scar Inspection**
   - *Why*: When an automated benchmark or harness run halts with a scar (e.g., `CONTEXT_OVERFLOW`, `RESERVED_PATH`, `RETRY_SAME`), developers need an instant deterministic playback that re-derives every request wire hash and verifies the exact point of refusal.
   - *Verdict*: **Mandatory Tier 1 Requirement.**

5. **Tool Output Mocking / Cached Fast-Forward**
   - *Why*: Replaying long runs where expensive web queries, database inspections, or slow compilation runs occurred should not require re-executing those tools if their inputs are identical.
   - *Verdict*: **High Value Tier 2 Requirement.**

---

### 2.2 Gimmicks & Over-Engineered Bloat (Noise to Avoid)

| Gimmick / Anti-Pattern | Why it seems appealing | Why it fails in practice | Recommendation |
| :--- | :--- | :--- | :--- |
| **Continuous "Video-Style" Animation (60fps Typewriter Scrubber)** | Feels like watching a real-time screen recording of the agent "typing". | Complete waste of developer time. Developers do not want to watch an agent type at 40 words/minute; they want instant discrete turn-level state transitions and diffs. | **REJECT**. Use discrete turn-stepper ($K \rightarrow K+1$). |
| **Full OS / VM Memory Snapshots (CRIU / RAM dumps)** | Promises 100% bit-exact restoration of running bash subshells, RAM, and OS sockets. | Enormous disk bloat (gigabytes per turn), extreme latency (pausing VM for RAM serialization), platform-dependent (fails across Windows/macOS/Linux). | **REJECT**. Rely on Git worktrees + working directory file diffs + process exit traps. |
| **Microsecond-Level Event Stepping** | Records every single chunk delta of streaming tokens as an individual timeline checkpoint. | Floods timeline UI with 4,000 micro-nodes per turn. Drowns developer in noise. | **REJECT**. Collapse streaming tokens into a single turn completion event; scrub by turn boundaries. |
| **Automatic Hallucination Auto-Rewind** | Harness tries to guess when an agent made a bad edit and automatically rewinds without human confirmation. | False-positive disaster. The harness often rewinds valid exploratory code or intermediate refactorings, infuriating the developer. | **REJECT**. The harness flags the scar and pauses; human or explicit oracle gate controls the rollback. |
| **Infinite Unpruned DAG Graphs** | Never pruning orphan exploration branches, leading to 3D graph visualizations of 500 dead branches. | Visual spaghetti. Developers cannot navigate tree graphs with $>10$ branches. | **REJECT**. Support simple parent-child linear branch forks; archive or collapse abandoned branches. |

---

### 2.3 Strict Adoption Matrix for a Multi-Harness Tool

For a multi-harness platform handling external harnesses (Claude Code, Cursor, Grok, Goose, OpenHands) and the native COSMOS harness, the following three replay modes are strictly worth adopting:

```
[MODE 1: INSPECTION REPLAY]   --> Read-only playback of any imported session across 20+ harnesses.
[MODE 2: RESUME & BRANCH]     --> Rewind to Turn N, alter prompt, branch into live execution.
[MODE 3: HARNESS AUDIT]       --> Re-derive requests, verify wire hashes, validate L1-L8 harness laws.
```

---

## 3. Architecture & Ecosystem Fit across COSMOS

The COSMOS architecture separates concerns into a clean 5-layer hierarchy:
1. **cmSessions**: The User Experience & Session Ingest / Export / Navigation layer.
2. **cmCode**: The Workspace File System, Editor, and Patch/Worktree manager.
3. **COSMOS Core**: The Canonical Session Schema, DAG SessionTree, and Content-Addressed Journal.
4. **The Harness**: The Execution Sandbox, Tool Interceptors, VCR Runner, Scars, and 4C Gates.
5. **cmClusters**: Distributed Agent Execution, signed envelopes, logical ordering, and multi-node replay.

```
+----------------------------------------------------------------------------------------------------+
|                                    COSMOS REPLAY ARCHITECTURE                                      |
+----------------------------------------------------------------------------------------------------+
|  cmSessions (UI & Control Layer)                                                                   |
|  - Timeline Scrubber Bar [|<] [<] [Turn 3 / 8] [>] [>|]                                           |
|  - Split-Pane View: Session Transcript vs Unified File Diff                                        |
|  - Granular Rollback Modal: [Code Only] | [Transcript Only] | [Both & Fork]                        |
+----------------------------------------------------------------------------------------------------+
                                      | Controls & Events
                                      v
+----------------------------------------------------------------------------------------------------+
|  COSMOS Core (Protocol & Journal Layer)                                                            |
|  - Canonical SessionTree (DAG of TurnCheckpoint nodes)                                             |
|  - Content-Addressed Hash Chains (BLAKE2b digests)                                                 |
|  - Journal append-only ledger: derive == wire auditability                                         |
+----------------------------------------------------------------------------------------------------+
             |                                                |
             v                                                v
+---------------------------------------+  +---------------------------------------------------------+
|  cmCode (Workspace Layer)             |  |  The Harness (Execution & Policy Layer)                 |
|  - Git Worktree / Patch Shadowing     |  |  - VCR Interceptor & Cached Tool Response Runner        |
|  - Workspace Snapshot at Turn N       |  |  - Sandbox Jail (jail.Jail.resolve, Reserved Paths)     |
|  - Reverse-patch application          |  |  - SopLedger (Anti-Silent-Retry, Single Confirming Call)|
|  - File state independent of chat     |  |  - 4C Verification & Oracle Reproducer Gate             |
+---------------------------------------+  +---------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------------------------------+
|  cmClusters (Distributed Mesh Layer)                                                               |
|  - Mesh Cross-Agent Replay: Signed cosmos-msg/2 Envelopes                                          |
|  - Logical Lamport/Vector Clock Sequencing across Roster Nodes                                     |
|  - Distributed Timeline Synthesis across Pilot, Orc, and Workers                                   |
+----------------------------------------------------------------------------------------------------+
```

---

### 3.1 Layer 1: cmSessions (UI Scrubber, Timeline Player, Side-by-Side Diff)
- **Role**: Serves as the primary user interface for time travel (web interface at `127.0.0.1:8786` or desktop TUI).
- **Multi-Harness Ingest**: Reads transcripts from all 20+ supported tools (Claude Code, Cursor, Gemini, Grok, Goose, OpenHands, Cline, etc.) and translates them into the **Canonical COSMOS SessionTree**.
- **Scrubber UI Component**:
  - Horizontal timeline bar showing turns $1 \dots N$.
  - Color-coded turn indicators: 
    - Green: Completed turn with passing tests/checks.
    - Yellow: Soft warning or SOP shape correction.
    - Red: Scar / refusal / gate failure.
    - Blue: Active scrub position.
  - Controls: Step Backward (`[<]`), Step Forward (`[>]`), Jump to Turn (`N`), Fork Session (`[Fork]`), Rollback Code (`[Undo Code]`).
- **Side-by-Side Dual Diff Viewer**:
  - Left pane: Message stream, model reasoning block, and tool invocations for the scrubbed turn.
  - Right pane: Unified multi-file workspace diff showing exactly what changed on disk during that turn.

---

### 3.2 Layer 2: cmCode (File Snapshots, Patch Rollback, Git Tree Integration)
- **Role**: Manages the physical workspace state on disk so that moving the scrubber updates files without corrupting developer work.
- **Git Worktree Shadowing**:
  - For active sessions, `cmCode` maintains an ephemeral git shadow branch or temporary worktree:
    $$\text{refs/cosmos/checkpoints/}\langle\text{session\_id}\rangle/\langle\text{turn\_seq}\rangle$$
  - Every turn completion commits the workspace delta with metadata:
    ```
    commit_hash = git commit -m "cosmos(turn=3, scar=NONE, tools=[edit_file])"
    ```
- **Decoupled Revert Engine**:
  - `restore_workspace(turn_seq)`: Checks out the shadow tree or applies reverse diffs to working directory.
  - Does not pollute user's primary git log; changes stay in `refs/cosmos/*` until explicit user "Land" / "Commit".
- **Safety Jails**: If external edits or dirty unstaged files exist prior to rewind, `cmCode` stages them safely into `.history/` or `_delme/` rather than destructive overwriting.

---

### 3.3 Layer 3: COSMOS Core (Canonical Session Schema & SessionTree DAG)
- **Role**: The single source of truth. Authority is the content-addressed ledger.
- **SessionTree Architecture**:
  - Every session is represented as an append-only DAG of `TurnCheckpoint` records.
  - Hash Integrity: Every checkpoint computes a BLAKE2b digest of:
    $$\text{Digest}_k = \text{BLAKE2b}(\text{Digest}_{k-1} \parallel \text{RequestHash} \parallel \text{ResponseHash} \parallel \text{FileDiffHash})$$
  - If a session is scrubbed backward and branched, the new turn records `parent_turn_id = Turn_{k-1}`. The old branch remains intact in the DAG.
- **Derive == Wire Law**:
  - The context window is never stored as an arbitrary mutated blob; it is strictly re-derived from the journal via `derive_messages(journal, up_to_turn=K)`.

---

### 3.4 Layer 4: The Harness (Interceptors, VCR Runner, Sandbox Execution)
- **Role**: Enforces execution policies, intercepts tool calls, and provides deterministic test runners.
- **VCR Tape Runner (`CachedToolRunner`)**:
  - When replaying an existing session in deterministic mode:
    ```python
    def execute_tool(self, tool_name: str, args: dict) -> ToolResult:
        if self.replay_mode == ReplayMode.DETERMINISTIC_TAPE:
            return self.vcr_tape.get_cached_result(self.current_turn, tool_name, args)
        elif self.replay_mode == ReplayMode.LIVE:
            return self.sandbox.execute(tool_name, args)
    ```
- **SopLedger & Anti-Placation Laws**:
  - During re-runs, the harness enforces COSMOS Laws:
    - *Anti-Silent-Retry*: Identical body digest returns `RETRY_SAME` refusal.
    - *Reasoning Isolation*: Model reasoning blocks are journaled for developer inspection but stripped from the wire context.
    - *4C Gate Verification*: To claim `DONE`, the harness re-runs the oracle reproducer; replay confirms the PASS summary hash matches the journal.

---

### 3.5 Layer 5: cmClusters (Distributed Multi-Agent Replay)
- **Role**: Replaying coordinated runs across multi-agent clusters (Pilot, Orchestrator, Worker agents on different machines).
- **Envelope Ordering with Logical Clocks**:
  - All inter-agent messages use signed `cosmos-msg/2` envelopes.
  - Envelopes carry a Lamport sequence vector: `(cluster_epoch, agent_id, seq_id)`.
- **Global Mesh Timeline Synthesis**:
  - Replaying a cluster run merges each agent's individual hash-chained inbox into a unified global timeline.
  - The UI scrubber can display a multi-lane timeline (Lane 1: Orchestrator, Lane 2: Worker A, Lane 3: Worker B) and step forward in causal order.

---

## 4. Concrete Schemas, Data Structures & Implementation Blueprints

### 4.1 Canonical Turn Checkpoint Schema (`checkpoints.py`)

Below is the concrete Python dataclass definition for a canonical turn checkpoint, compliant with COSMOS stdlib-only kernel requirements:

```python
"""
COSMOS Core: Canonical Turn Checkpoint & Replay Schema
Standard library only: hashlib, json, dataclasses, typing, pathlib, time
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from enum import Enum
import hashlib
import json

class ReplayMode(str, Enum):
    DETERMINISTIC_TAPE = "tape"      # Mocked cached responses, zero API calls
    CACHED_TOOLS_LIVE_MODEL = "hybrid" # Live model, cached deterministic tool reads
    LIVE_EXECUTION = "live"          # Live model and live tool execution
    AUDIT_VERIFY = "audit"           # Re-derive wire hashes and verify L1-L8 laws

class HaltReason(str, Enum):
    NONE = "NONE"
    DONE = "DONE"
    VERDICT = "VERDICT"
    HALT_MAX_TURNS = "HALT_MAX_TURNS"
    HALT_SIZE = "HALT_SIZE"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    DOOR_REFUSAL = "DOOR_REFUSAL"
    SCAR_THRESHOLD = "SCAR_THRESHOLD"

@dataclass(frozen=True)
class ToolCallRecord:
    call_id: str
    tool_name: str
    args: Dict[str, Any]
    result_content: str
    exit_code: int
    duration_ms: int
    is_cached: bool = False
    args_hash: str = field(init=False)

    def __post_init__(self):
        serialized = json.dumps({"tool": self.tool_name, "args": self.args}, sort_keys=True)
        digest = hashlib.blake2b(serialized.encode("utf-8"), digest_size=16).hexdigest()
        object.__setattr__(self, "args_hash", digest)

@dataclass(frozen=True)
class FilePatchDelta:
    path: str
    action: str              # "create" | "modify" | "delete"
    unified_diff: str        # Standard unified diff format
    pre_sha256: Optional[str]
    post_sha256: Optional[str]

@dataclass(frozen=True)
class SpendAccounting:
    prompt_tokens: int
    completion_tokens: int
    cache_read_tokens: int
    cache_created_tokens: int
    cost_usd_micros: int     # Stored as integer micro-dollars ($1 = 1,000,000)
    latency_ms: int

@dataclass
class TurnCheckpoint:
    turn_seq: int                        # 1-based sequential index in branch
    checkpoint_id: str                   # BLAKE2b content-addressed ID
    parent_checkpoint_id: Optional[str]  # ID of parent node in DAG
    session_id: str
    branch_id: str
    timestamp_iso: str
    
    # Model & Turn Core
    model_pin: str                       # e.g., "claude-3-7-sonnet-20250219"
    user_prompt: str
    assistant_reasoning: Optional[str]   # Isolated reasoning evidence
    assistant_reply: str
    tool_calls: List[ToolCallRecord]
    
    # State Diffs & Ledger
    workspace_patches: List[FilePatchDelta]
    git_shadow_commit: Optional[str]
    spend: SpendAccounting
    
    # Verification & Health
    scar_name: Optional[str]             # e.g., "RETRY_SAME", "PATH_ESCAPE", or None
    checks_4c_pass: bool                 # Compilation, Clean, Correctness, Contract
    halt_reason: HaltReason = HaltReason.NONE
    
    # Content Hash Chain
    chain_digest: str = ""

    def compute_chain_digest(self, parent_digest: str = "") -> str:
        """Derive the cryptographically verified hash chain digest."""
        payload = {
            "turn_seq": self.turn_seq,
            "parent_digest": parent_digest,
            "session_id": self.session_id,
            "model_pin": self.model_pin,
            "user_prompt": self.user_prompt,
            "assistant_reply": self.assistant_reply,
            "tool_hashes": [tc.args_hash for tc in self.tool_calls],
            "patch_paths": [p.path for p in self.workspace_patches],
            "cost_micros": self.spend.cost_usd_micros,
            "scar": self.scar_name or ""
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.blake2b(raw, digest_size=20).hexdigest()
```

---

### 4.2 Directed Acyclic Graph SessionTree (`session_tree.py`)

```python
"""
COSMOS Core: Append-Only Directed Acyclic Graph (DAG) Session Tree
Supports multi-branch time-travel scrubbing without data loss.
"""
from typing import Dict, List, Optional
from .checkpoints import TurnCheckpoint

class SessionTree:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.nodes: Dict[str, TurnCheckpoint] = {}       # checkpoint_id -> Checkpoint
        self.children: Dict[str, List[str]] = {}         # parent_id -> list of child_ids
        self.root_id: Optional[str] = None
        self.active_leaf_id: Optional[str] = None
        self.branch_heads: Dict[str, str] = {}           # branch_name -> checkpoint_id

    def add_checkpoint(self, checkpoint: TurnCheckpoint) -> str:
        cid = checkpoint.checkpoint_id
        parent_id = checkpoint.parent_checkpoint_id
        
        # Link in graph
        self.nodes[cid] = checkpoint
        if parent_id is None:
            self.root_id = cid
        else:
            self.children.setdefault(parent_id, []).append(cid)
            
        self.active_leaf_id = cid
        self.branch_heads[checkpoint.branch_id] = cid
        return cid

    def get_lineage(self, leaf_id: Optional[str] = None) -> List[TurnCheckpoint]:
        """Returns the chronological list of checkpoints from root to the given leaf."""
        target_id = leaf_id or self.active_leaf_id
        if not target_id or target_id not in self.nodes:
            return []
            
        path = []
        curr: Optional[TurnCheckpoint] = self.nodes[target_id]
        while curr:
            path.append(curr)
            curr = self.nodes.get(curr.parent_checkpoint_id) if curr.parent_checkpoint_id else None
            
        path.reverse()
        return path

    def fork_at_turn(self, target_checkpoint_id: str, new_branch_name: str) -> TurnCheckpoint:
        """Branches the session tree at an arbitrary past checkpoint."""
        if target_checkpoint_id not in self.nodes:
            raise KeyError(f"Checkpoint {target_checkpoint_id} not found in SessionTree")
            
        base_checkpoint = self.nodes[target_checkpoint_id]
        self.branch_heads[new_branch_name] = target_checkpoint_id
        self.active_leaf_id = target_checkpoint_id
        return base_checkpoint
```

---

### 4.3 VCR Replay Interceptor State Machine (`replay_interceptor.py`)

```python
"""
COSMOS Harness: Replay Interceptor & VCR Tape Runner
Handles deterministic tool mocking and hybrid live branching.
"""
from typing import Dict, Any, Tuple
from .checkpoints import ToolCallRecord, ReplayMode

class VCRReplayInterceptor:
    def __init__(self, recorded_tape: Dict[Tuple[int, str, str], ToolCallRecord]):
        """
        Tape key: (turn_seq, tool_name, args_hash) -> ToolCallRecord
        """
        self.tape = recorded_tape
        self.mode = ReplayMode.DETERMINISTIC_TAPE

    def intercept_tool(self, turn_seq: int, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str, int]:
        """
        Returns: (handled_by_cache, result_content, exit_code)
        """
        if self.mode == ReplayMode.LIVE_EXECUTION:
            return False, "", 0

        # Compute deterministic args hash
        import hashlib, json
        serialized = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        args_hash = hashlib.blake2b(serialized.encode("utf-8"), digest_size=16).hexdigest()

        key = (turn_seq, tool_name, args_hash)
        if key in self.tape:
            record = self.tape[key]
            return True, record.result_content, record.exit_code

        if self.mode == ReplayMode.DETERMINISTIC_TAPE:
            # If in strict tape mode, unexpected tool call is a refusal scar
            raise RuntimeError(f"TAPE_MISSING: No recorded output for {tool_name} at turn {turn_seq}")
            
        # In hybrid mode, fallback to live execution
        return False, "", 0
```

---

### 4.4 UI Interaction Flow & Keybindings in `cmSessions`

```
+----------------------------------------------------------------------------------------------------+
|  cmSessions REPLAY INTERACTION WORKFLOW                                                           |
+----------------------------------------------------------------------------------------------------+

1. NAVIGATION (Timeline Bar)
   - [Left Arrow] / [h]       : Step back 1 turn (re-renders transcript & workspace diff)
   - [Right Arrow] / [l]      : Step forward 1 turn
   - [Home] / [g g]           : Jump to Turn 1 (Initial Prompt)
   - [End] / [G]              : Jump to Final Active Turn
   - [Click on Timeline Node] : Instant jump to selected Turn N

2. ACTIONS AT TURN N
   - Press [r] (Rollback Code Only):
     * Checks out git shadow commit for Turn N into workspace.
     * Leaves chat transcript pointing to latest turn.
     * Injects system notice: "Workspace files rolled back to Turn N state by developer."
     
   - Press [u] (Rollback Conversation Only):
     * Context window rewinds to Turn N prompt.
     * Leaves physical workspace files untouched.
     * Developer can immediately re-prompt the agent with existing disk edits intact.

   - Press [b] (Branch / Fork Session):
     * Opens prompt dialog: "Enter modified instruction for Turn N:"
     * Generates new branch ID in SessionTree (`branch-20261109-01`).
     * Prompts for Replay Mode:
       (1) Hybrid (Use cached tool outputs where valid)
       (2) Full Live (Re-execute all tools live)
     * Spawns turn runner on new branch.

   - Press [d] (Toggle Diff Mode):
     * Switches right pane between:
       - Single-Turn Patch (What changed in Turn N)
       - Cumulative Diff (What changed between Turn 1 and Turn N)
```

---

## 5. Strategic Architectural Recommendations for COSMOS

### Recommendation 1: Adopt the Content-Addressed `SessionTree` as Canon
Do not store sessions as flat JSON lists or ad-hoc SQLite tables. Standardize on the content-addressed `SessionTree` DAG. This allows developers to fork at any turn without destroying earlier attempts, providing an audit-grade provenance chain (`derive == wire`).

### Recommendation 2: Decouple Code Rollback from Conversation Rollback
Follow the pattern proven by Claude Code's `/rewind` architecture. Real developer friction is overwhelmingly caused by agents either writing bad code while having the right plan, or writing great code and then drifting off-topic. Decoupling the rollback actions gives developers surgical precision without wasting tokens.

### Recommendation 3: Enforce the VCR Interceptor in the Harness
When running automated evaluation suites or diagnosing test failures, the Harness must support strict VCR tape playback. This enables 1,000 regression runs of an 8-turn session in seconds at \$0.00 cost, verifying that changes to harness guards or scar classifiers do not break historical runs.

### Recommendation 4: Leverage Ephemeral Git Worktrees (`refs/cosmos/*`) in `cmCode`
Never invent a custom binary diff storage engine when Git is available. Store per-turn workspace snapshots as lightweight git trees under private namespace `refs/cosmos/checkpoints/<session_id>/<turn_seq>`. This guarantees maximum performance, zero risk of data corruption, and immediate compatibility with standard developer tooling.

### Recommendation 5: Reject Video-Typewriter Scrubbers; Embrace Discrete Turn Stepping
Focus UI engineering exclusively on instant turn-to-turn transitions, responsive side-by-side diffing, and fast branching modals. Avoid animated typewriter effects and heavy memory snapshotting engines that add maintenance burden without developer utility.

---
*Report compiled for the COSMOS Core Architecture & Harness Engineering Group.*
