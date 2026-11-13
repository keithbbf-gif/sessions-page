# cmSessions & Barndoor AI: Fenced Inference Architecture & Local Silicon Doctrine

**Document ID:** `CMS-SPEC-2026-V5-01`  
**Classification:** Core System Architecture Specification  
**Location:** `V:\Streams\cmsessions\docs\arch\CMSESSIONS_BARNDOOR_FENCED_INFERENCE_SPEC.md`  
**Target Subsystems:** `cmSessions`, `COSMOS Code`, `COSMOS Harness`, `cmClusters`  

---

## 1. Executive Summary & Core Law

The defining insight of **cmSessions** and the **COSMOS Harness** is:
> **Local silicon is free; model tokens are expensive.**  
> *Anything that CAN be computed by local CPU, OS, and RAM MUST be computed there. The model must never perform raw data parsing, string searching, or mechanical formatting that a deterministic script can execute in sub-milliseconds.*

In historical legacy runs (e.g., `SESSION_LOG_Harness-failure-Ai-Governance_20261014-25.md`), legacy harnesses violated this law:
- **Turns 12–45:** When the agent hit a SQLite full-text tokenizer error (`unknown tokenizer: mozporter`), the harness passively let the model burn 33 conversational turns trying to guess Python regex hacks to open the database.
- **Turn 157:** The harness blindly allowed 8 concurrent, unbuffered web fetches to overwhelm the context window, resulting in a silent 5-day thread freeze.

To prevent these defects, `cmSessions` adapts the best architectural mechanisms of **Barndoor Automations (Barndoor.ai / Frags Runtime Engine)**—specifically **Fenced Inference**, **Compile-Time Schema Verification**, and **Bi-Directional MCP Compilation**—and grounds them in a **Pure-Rust / Python `uvloop` Local Execution Kernel**.

---

## 2. Comparative Matrix: Barndoor AI vs. cmSessions / COSMOS

| Feature Dimension | Barndoor Automations (Frags / FML) | Solaro Labs (cmSessions / COSMOS) | Advantage & Implementation |
| :--- | :--- | :--- | :--- |
| **Primary Domain** | Enterprise SaaS workflows (Salesforce, Jira, BigQuery) | Deep software engineering, AST refactoring, benchmark evaluations | Specialized for high-velocity coding and test-driven validation. |
| **Workflow Definition** | FML (Frags Modeling Language) blueprints | Declarative `cosmos.toml` + 5-Phase FSM (`RECON -> LOCK -> PATCH -> VERIFY -> COMMIT`) | Version-controlled, human-readable, PR-diffable blueprints. |
| **Inference Boundary** | Fenced `session(..., after=...)` blocks | Stratified 3-Slot KV Cache + $O(1)$ Ephemeral Repair Window | Model sees only scoped task inputs; history is frozen in Slot 2. |
| **State Persistence** | Cloud-managed SaaS database (30-day retention) | Zero-copy memory-mapped LMDB (`writemap=True`) + append-only journal | Microsecond state recovery, survives crashes, zero cloud lock-in. |
| **Linter & Verification** | Static JSON schema matching | Strict 12C Validator Ladder + AST MinHash delta gating | Evaluates regressions against unedited baseline, not dirty noise. |
| **Tool Calling / Compilation**| APICP (OpenAPI to MCP dynamic compiler) | `CosmosPluginHost` / Native Local MCP Server | Exposes harness routines as standard MCP tools for Claude Code/Cursor. |
| **Safety & Liability** | Soft monthly budget alerts in SaaS gateway | Deterministic Dual-Lock Machine Gate (`RULE-H1` to `RULE-H5`) | Hard kernel circuit breaker drops socket on unauthorized spend. |

---

## 3. Four Core Pillars Borrowed from Barndoor

### Pillar 1: Fenced Inference & Typed Phase Contracts
Barndoor eliminates open-ended agent drift by compiling workflows into a Directed Acyclic Graph (DAG) of isolated `session()` blocks.
- **In cmSessions:** An agent never loops indefinitely in an open conversation. Every phase transition (`RECON` to `LOCK`, `LOCK` to `PATCH`, `PATCH` to `VERIFY`) is an immutable transaction boundary.
- **Schema Gating:** An agent transitioning from `PATCH` must emit a typed unified-diff schema. The moment it outputs text that fails structural parsing, the engine rejects the payload immediately at the host layer without invoking downstream linters or tests.

### Pillar 2: Native Model Context Protocol (MCP) Server Compilation
Barndoor’s Frags runtime dynamically compiles workflow blueprints into native MCP servers.
- **In cmSessions:** `cmSessions` exposes an embedded, lightweight MCP server. Third-party developer IDEs (like Claude Code, Cursor, or VS Code) can discover and invoke seated COSMOS routines:
  * `tools.cmsessions_replay(session_id, epoch)`
  * `tools.cmsessions_tnt_trace(session_id, filter)`
  * `tools.cosmos_run_harness_test(worktree, suite)`
- The external agent receives a deterministic execution receipt without needing to manage subprocess lifecycle or environment variables.

### Pillar 3: Absolute Code-Level Determinism Between Steps
Barndoor strictly bans models from executing mechanical data manipulation.
- **In cmSessions:**
  * **AST Navigation:** `ast_nav.py` uses `tree-sitter` on the local CPU to build a PageRank symbol map before the model is invoked. The model receives a compact, 400-token structural context instead of burning turns calling `ls` or `grep`.
  * **Deterministic Failover:** If an execution tool throws a system exception (e.g. SQLite missing tokenizer), the error trace is hidden from the model. The host CPU intercepts the error, runs a local parsing fallback (e.g., standard library `mailbox.mbox`), and provides clean text data to the turn context.

### Pillar 4: Language Server Protocol (LSP) Diagnostics & Zero-Tear TUI
Barndoor provides real-time validation via an FML Language Server.
- **In cmSessions:** The append-only `session.jsonl` state journal is coupled with an in-memory LSP bridge (`rust-analyzer` / `pyright`).
- **TUI & Web Dashboard:** `cmSessions` drives:
  1. A terminal UI (`ratatui`) locked via hardware `DECSTBM` scrolling regions to prevent screen tearing at 150+ tok/sec.
  2. A local-loopback web dashboard (`ui/index.html`) displaying active draggable columns, session timelines, Replay scrubbing, and Tracking & Tracing (TnT) swarm trees.

---

## 4. The Dual-Lock Machine Gate Architecture

To operationalize the **Four Inviolable Duties** established in *"The Same Rules for AI"*:

```
┌──────────────────────────────────────────────────────────────┐
│                    THE DUAL-LOCK MACHINE GATE                │
│                                                              │
│  [ STEP 1: Cognitive Pre-Flight Assertion Handshake ]        │
│  Model signs structured JSON acknowledging:                  │
│    • RULE-H1: No unconsented tier upgrades                  │
│    • RULE-H2: Strict protocol isolation (Vertex vs Studio)  │
│    • RULE-H3: Zero credential exfiltration in logs          │
│    • RULE-H5: Strict spend ceiling ($5.00 hard cap)         │
│                                                              │
│                            │                                 │
│                            ▼                                 │
│  [ STEP 2: Deterministic Local Kernel Proxy (Rust/Python) ]  │
│  Proxy inspects outbound wire packets:                       │
│    • Intercepts transport headers                            │
│    • Filters socket connections (COSMOS_NO_NET=1)            │
│    • Drops wire instantly if spend or boundary breached      │
│    • Logs immutable audit receipt (Proof of Gross Negligence)│
└──────────────────────────────────────────────────────────────┘
```

If a model signs the pre-flight assertion and later violates a boundary, the immutable log converts what tech companies claim is an "excused stochastic anomaly" into an open-and-shut case of gross negligence under common law and statutory warranty.
