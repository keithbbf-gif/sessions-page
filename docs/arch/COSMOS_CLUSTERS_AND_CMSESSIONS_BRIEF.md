# COSMOS Clusters and CM Sessions

Design brief from the 8 November 2026 working session.

This memo captures the concepts, terminology, structures, and plans discussed in that chat. It is a record of decisions and distinctions, not a new design. Where a point was left open, it is marked as open.

Participants: Keith Chambers (Solaro Labs) and Ara.

Scope of the talk: why the sessions UI stalled, how to choose a harness for visual work, then a deep pass on **CM Sessions** and **COSMOS Clusters** — topology, durability, audit, coordination, cost, what is already built, the MDATA flywheel, and how the work gets in front of people.

---

## 1. Why the session happened

`sessions-page` (GitHub: `keithbbf-gif/sessions-page`) was paused because the UI would not render reliably under **Grok Build** (`Grok.exe`). Grok Build is a coding harness. It is strong at multi-file refactors and tests. It is a poor loop for chasing pane layout, because it does not give a fast see-and-fix cycle against a running page.

The UI work was handed to **Muse 1.3 contributor** inside the **Hermes** harness, with an uploaded image of the target main layout and an instruction to keep rendering. Hermes is already on the sessions-page default index (`~/.hermes/state.db`).

The intended production split:

| Phase | Surface | Why |
|---|---|---|
| Design and layout | Browser UI, hot reload | Refresh beats rebuild when chasing layout bugs. A reference mockup lets the agent diff each render against a picture instead of guessing. |
| Ship | Packaged executable (PyInstaller or equivalent) | Once the UI is right, compile what already works. Dev in the browser, ship the exe. |

Nobody on this project diffs code by hand anymore. The agent's diff review plus eyes on the rendered page is the loop. Manual diff UIs survive mostly from habit, trust, and team compliance (a human must sign the patch). For solo work that overhead is dead weight. A person scrolling a diff comprehends on the order of tens of lines a second. The agent already knows the blast radius.

---

## 2. Product map (Solaro Labs)

Public home: [ai.solarolabs.com](https://ai.solarolabs.com).

Positioning stated on the site: free AI tools forever; low-cost tokens only when a model is actually required. Live spend tracking and user-set caps. Every tool does the job without a model when it can.

Site quote (Keith): built every tool to fix a problem hit while running models on his own machine.

| Name | Status as discussed | Role |
|---|---|---|
| **TokenCenter** | Live | One-key access to any OpenAI-compatible endpoint. The paid path when a free tool needs a stronger model. |
| **COSMOS** | In development | The system outside every vendor harness. Sole authority for fencing, spend gates, one-writer leases, close/open, and durable memory. |
| **COSMOS CODE** | In development | The coding harness Clusters is meant to reuse. One codebase, one permission model, one way to inject a spawn manifest. |
| **CM Sessions** | In development | Find any AI coding session and pick it back up. Chronological browser over the session tree. Will need its own harness for summaries. |
| **COSMOS Clusters** | In development — **the work this session focused on** | Run several coding agents and still know who did what. Nested clusters, not a flat swarm. |
| **SpiderCaster** | In development, set for a major graphics upgrade | Site builder inside COSMOS. See §16. |
| **sessions-page** | Exists; UI paused | Standalone indexer/recovery/resume tool. COSMOS already routes its session-tools API at this engine. |
| **MDATA** | Live at `mdata.modelraters.com` | Empirical model evaluations, scars, notes, orthogonality. The measurement side of the flywheel. See §17. |
| **ModelRaters** | Live | Public rankings, JSON and SQLite downloads, no key required for the public surface. |
| **BTS Mesh** | Exists in the COSMOS lineage | Verdict / orchestration mesh. Source of the PIN / one-writer idea. |
| **Swarm Deck / cDECK** | UI experiments | Draggable multi-agent panels. Not the Clusters architecture. |
| **Crucible and other MOTIF triage tools** | Exist as motifs | Adversarial multi-agent review. The enterprise wedge (lawyers, doctors) and a feed into MDATA. |

Canon docs that are **not** on the public site live on the local COSMOS tree (discussed as `V:\A\Ai\COSMOS`, with ROLD at `V:\A\Ai\ROLD`). They were recovered in this session from `keithbbf-gif/cosmos` history, especially the 20 September 2026 close record:

- **TidyUP** and **TidyUP2** — root-level procedures; not always present on the current git tree, but specified in the canon.
- **ROLD** — repository of living documents.
- **BootUP** — start-of-session gate.

Related local package: `V:\A\Ai\spidercaster` (includes an Antigravity SDK subdirectory). SpiderCaster's relationship to COSMOS Core was flagged in its own docs as still needing definition before full integration.

---

## 3. Terminology

Use these words as defined here. Several of them collide with vendor marketing.

### Sessions and resume

- **Session file** — the harness-native transcript or state DB (Claude, Codex, Grok, Hermes `state.db`, and the rest of the ~20 parsers in sessions-page).
- **Parent session** — the orchestrating agent's transcript.
- **Child session / sub-agent session** — a session spawned under a parent. Sometimes nested inside the parent stream, sometimes a separate file, sometimes only stdout that vanishes.
- **Headless session** — a run with no UI. Often logs to stdout or a temp file and disappears on exit.
- **Resume** — print or launch the native command (`grok --resume`, `claude --resume`, and so on). sessions-page can `--launch`.
- **Recovery** — do not rewrite a corrupt file in place. Stage it under `var/stage` and overlay a verified `.bak` sibling.
- **Delta scan** — rescan only from "now" back to the newest timestamp already in the cache. Everything older is known.
- **Lazy backfill** — anything older than the hot window (planned: one week) loads in the background.

### Close, open, and proof

- **TidyUP** — close session. Validates every control file, fail-closed. Writes a signed **SEED**. Inherited facts, active leases, open watchers, handoff recipient.
- **TidyUP2** — adversarial re-measure immediately after close. Porosity counted, occupancy checked, ledger head verified. Proves the close did not lie.
- **BootUP** — start session. Re-reads the SEED under its declared length and HMAC before anything is injected. Refuses to open if the previous close did not seal (`BootUP` gate).
- **SEED** — the signed handoff blob. Not a chat summary pasted into a prompt. Structural carry-over. On the September 2026 close it was on the order of 11 KB.
- **SEED HMAC** — hash-based message authentication code over the SEED. BootUP already checks it. Proposed as the proof that a caller is inside a real COSMOS session (see MDATA access).
- **Ledger** — append-only, hash-chained, signed events. Tampering breaks the chain and TidyUP2 fails closed.
- **ROLD** — repository of living documents. Glossary, rules, scars, and the dated command list that pairs TidyUP with BootUP. Local root discussed as `V:\A\Ai\ROLD`.
- **Carry-over** — structural, not chat memory. A respawned agent loads the seed. It does not reconstruct a life from a transcript dump.

### Memory that appears during a run

- **Memory shard** — durable fragment written to disk during the session.
- **Memory crystal** — denser, composed durable state. A respawned sub-agent loads the crystal instead of re-deriving history.
- **Artifact** — anything the session spontaneously writes into a durable format while it is running (not only at close).
- **Handoff object** — the structured alternative to "last N messages." Goal, decisions made, files touched, open questions, and a pointer at the durable artifact. The SEED is the sealed form of this.

### Clusters

- **Cluster** — a lead plus its direct workers. Not fifty peers. Not a swarm.
- **Lead** — the one agent in charge of that cluster. Holds the contract, the summaries, and the escalation path.
- **Orchestrator** — a lead whose workers are themselves cluster leads. A cluster of clusters.
- **Six plus one** — the default fan-out agreed in this session. Six workers and one lead. Seven plus one is the ceiling (Miller's Law) and only works if every child stays quiet.
- **Nesting** — locality, a failure domain, and a bounded blast radius. Flat fifty-agent rings do not have these.
- **Contract / spawn manifest** — short instructions injected into the native harness at spawn. COSMOS root, SEED path, and the verb to call session-close before exit. The child does not need to understand the ledger.
- **Native harness** — Claude Code, Codex, Cursor, Hermes, Grok Build, Antigravity, and the rest. Clusters does not replace them. It spawns inside them and sits outside them as the authority.

### Coordination

- **Write file** — each agent's own publish surface. That agent may read and write it. Others may only read it. No mailbox collision.
- **Append-only write file** — refinement proposed: sequence numbers, so a reader sees issued / extended / released, not just the latest line.
- **PIN** — the single-writer token from BTS Mesh / COSMOS. Names who currently holds write access to the **live tree** (the master record). Everyone else queues or works in a sandbox.
- **One writer to the live tree** — the actual Clusters rule. Parallelism is in proposals, not in concurrent mutation of the master.
- **Proposal** — a child's candidate change, written only inside its own sandbox. The PIN holder merges into the master on a chosen cadence.
- **Lease / claim** — exclusion when two children would otherwise edit the same project path. Awareness (mailboxes) is not exclusion.
- **Worktree** — per-child checkout so two agents do not write the same file at the same time. Merge only at close. Discussed as still required for shared project files even when write-files are strictly per-agent.
- **Sandbox directory** — per child, under the cluster root: own write file, own worktree if it needs code, own proposal queue. Parent sees all. Siblings see published output only.
- **Collapse** — TidyUP packs that directory into the signed SEED (write file, proposals, lease state). A tree becomes one sealed artifact. BootUP expands it back.
- **Retention** — keep the raw sandbox folder while the cluster is live or under review. The SEED points at packed state; the raw tree is what replay rehydrates at original fidelity. Prune later with a retention policy. Do not garbage-collect during review.

### Audit, wounds, and measurement

- **Audit record** — TidyUP + ledger event + TidyUP2. Not the same thing as the handoff, and not optional for a multi-agent system.
- **Handoff without audit** — amnesia with a paper trail.
- **Audit without handoff** — forensics on a corpse.
- **SCARS** — canonical failure classes. Everyone else scores the final answer. This scores the wound.
- **Notes** — the lesson attached to a scar. A scar without a note is just a wound. The note is what the next agent can load.
- **Porosity** — counted at TidyUP2. Holes in the close.
- **Occupancy** — checked at TidyUP2. What the close claimed to hold versus what is there.
- **Orthogonality** — how much two models disagree. Used to pair adversaries so they catch each other's holes.
- **Rescue probability** — which model to trust when a pair disagrees.
- **Measurement framework** — the axes, the pairing math, the scars taxonomy, the recovery protocols. Raw session logs are cheap. This is the asset.
- **MDATA** — the database those measurements live in (`mdata.modelraters.com`).

### Product and distribution words used carefully

- **Swarm** — rejected as the product name. Oversells decentralization. Implies nobody is in charge.
- **Orchestrator** — generic. Clusters uses an orchestrator, but the product is the cluster.
- **Peer-to-peer multi-agent** — rejected. Agents duplicate work, contradict each other, no source of truth. (This matches the public argument, attributed via swyx to Walden Yan: do not build peer multi-agents; do build sub-agents with a parent-defined contract.)
- **Sub-agent model** — the model Clusters actually is. Hierarchical. One authority per level. Contracts you can update.
- **Table stakes** — parallel spawn, and increasingly git worktrees. Vendors are absorbing this. Do not compete on spawn count.
- **Moat** — durable, signed, re-verified, nested, cross-harness session records, plus the scars database that fills as a side effect of use.

---

## 4. sessions-page, as the foundation Clusters stands on

What it already is:

- Python toolset for finding, importing, exporting, indexing, recovering, and resuming local AI coding sessions.
- On the order of twenty harnesses: Grok, Claude Code, Codex, Cursor, Gemini, Hermes, Cline, Kilo, Roo, Pi, Copilot CLI, Continue, Aider, Goose, Qwen, Amp, OpenHands, Crush, DeepSeek, and others.
- Python 3.14 CLI, or a packaged exe. Loopback-only web UI at `127.0.0.1:8786`, opening on a drive overview and default session locations.
- COSMOS routes its session-tools API through the cosmos session-tools kit. No edits required to `cosmos-service`, `app.js`, or `header.js` for that routing.
- Tests live in the sessions-page test module. A plugin folder exists for a later UI plug.

Known limits called out at the start of the chat:

- SQLite and zstd store imports are unmeasured.
- Migrate and rebind are hard-blocked (do-not-reingest). Correct for legal sessions. Painful if those sessions ever need to move.

Clusters should not reimplement harness parsing. It should call this index.

---

## 5. Harness and agent choice for UI work

The filter is not the brand. It is whether the agent can **see the output and score it against the reference image**.

| Pair | Fit for this UI work |
|---|---|
| Muse 1.3 contributor in Hermes | Already in use. Fast visual back-and-forth. Keep rendering against the uploaded layout. |
| Claude Code + browser MCP | Can screenshot each render and compare to the mockup. |
| Cursor preview pane | Tightest edit-see-fix loop inside an editor. |
| Windsurf Cascade | Browser preview built in. |
| Gemini CLI | Worth it when the comparison itself is multimodal. |
| Antigravity app (`antigravity.exe`), not the `agy` CLI | Full agent surface, browser tooling, artifact review. Preferred over the terminal wrapper. `agy` is the CLI (about 1.5.x) and can run as an ACP server; it was explicitly rejected for this work. The app is the Windows installer from Google, 64-bit Windows 10 or later. Around early November 2026 it was at 2.29 with Gemini Live voice and remote agents. Free tier includes Gemini 3 Pro with rate limits. Stronger models want a paid plan. Google is removing the IDE Agent Manager and pushing supervision to the App or CLI. |
| Aider | No eyes. Fast only after the design direction is already nailed. |
| Grok Build | Wrong loop for layout. Right loop for refactors and tests, and for the later compile-and-verify pass. |

Diff-centric IDE workflows were set aside for this project. The user does not need to review patches by eye.

---

## 6. CM Sessions

### What it is

The browser for sessions across harnesses. Left sidebar is the quick start. The thing a person opens to see the last week of work and resume it.

It is also where child sessions become visible. The parent transcript is not enough.

### Child sessions

Behavior differs by harness:

- **Claude Code** nests sub-agent tool calls in the parent stream. You can read them.
- **Codex** and some others surface only the child's final text. The calls live in the child's own session file.
- **Headless** runs often never become a file you can index.

So CM Sessions must:

1. Parse the parent for child references.
2. Open each child file.
3. Extract tool calls and timestamps.
4. Hang that child under the parent in the sidebar.

Trusting the parent to contain everything will silently drop most of the tree.

### Population order and cost of scanning

Relevance is reverse chronological. Most recent files first.

Initial fill: **the last seven days**, from the OS directory listing sorted by modification time. Do not open file bodies to build that list. That stays near-instant even with hundreds of sessions. Cache the sorted index to disk so reopen does not rescan the world.

Refresh is not a full rescan. It is a **delta scan**: everything newer than the newest cached timestamp. In practice, "rescan today" is enough to stay current. Merge those entries in.

**Older than a week** scans in the background. Foreground stays snappy. Full history fills without a wait.

### Summaries

CM Sessions needs a harness, because a useful summary is a read-and-compress over a whole session, not a template. Same pattern as Clusters: thin UI, harness does the heavy work.

Caution, left open but explicit: a summary harness can fail. If it is model-backed, give it the same SEED and ledger treatment or you will be debugging the debugger. If it is deterministic (regex, keyword compression), it does not need the audit loop, but it will miss quiet semantic changes such as a dependency version bump. That trade (depth versus reliability) was named, not resolved.

### Replay, from the CM Sessions side

Replay is missing today. The plan is a split:

- **CM Sessions** is where you browse the tree and trigger replay. You are already looking at it.
- **Clusters** owns the replay engine, because only Clusters knows how to rehydrate a SEED, relaunch a harness, and step tool calls with real timing.
- CM Sessions hands over an event range and a SEED pointer. Clusters does the work and streams frames back.

Replay is also a training artifact: a good run can be replayed to show a new lead how a veteran cluster behaved.

---

## 7. Competitive landscape (early November 2026)

Three camps. Clusters does not try to win camp one or out-spawn camp two.

### Camp A — first party, absorbing basic parallel spawn

Claude Code desktop (multi-session sidebar, cloud Routines), Codex (parallel cloud sandboxes), Cursor (Agents Window), Antigravity (Agent Manager, being retired as a supervision surface), Grok Build (on the order of eight worktree-isolated subagents). This is becoming table stakes and it is getting faster.

### Camp B — open or commercial orchestrators

Figures below are as cited in the session, not a fresh audit.

| Product | Shape | Notes from the session |
|---|---|---|
| **Orca** (Stably AI) | Broad desktop orchestrator | ~118k stars. 27+ CLI agents. Git worktrees. Windows, Mac, Linux, phone apps. MIT. Orchestrator V3: nested workers, managed remote hosts. Best cluster-management UI found: split terminals, inline diffs you can send back, built-in browser with Design Mode, SSH worktrees, iOS/Android, push when an agent finishes. Two founders (Jinjing Liang, ex-Google Chrome; Neil Parker, ex-Uber; YC W22). Neil on the order of 5,000 commits. ~23 people touched triage in a year; three people close most of it. Claude itself authored hundreds of commits. Repo from 17 March, MIT from day one, nearly a thousand releases by November — daily shipping. Trending spike mid-October 2026. A dev.to deep dive framed it as "not an agent, it orchestrates the agents you already use." |
| **Traycer** | MIT orchestrator | ~22 agents. Shared specs and tickets. Free for individuals. One founder (Tanveer Gill), ~13 people, unfunded since 2024. Product Hunt 13 October 2025 (about #4 that day), then VS Code Marketplace and Open VSX to ~171k installs. ~11k desktop users, ~40k tasks. Founder's own X account did the distribution. |
| **Paradev** (formerly Superset) | Mac-first agent development environment | Three ex-YC CTOs (Kiet Ho, Satya Patel, Avi Peltz). $11.5M from Union Square Ventures. Claims 100+ parallel agents. Nicest phone review loop and scheduled automations. No Windows. Origin: Vibecon November 2025, launch January, first users were friends at YC companies running it 8–12 hours a day. #1 Product Hunt February. YC Spring batch March. 10k stars by April. A Show HN tripled users overnight. By October: claim of ~145k developers, ~180 countries, 1 in 8 Fortune 500, Japan #2 market. MIT-to-Elastic move and a free-forever desktop tier were deliberate. |
| **Kepler** (GitKraken) | ACP-based | 9+ agents including Grok Build, Pi, Antigravity via ACP. Jira, Linear, GitHub. GitKraken is the incumbent (large existing developer base). |
| **Emdash** | Apache-2.0 | Wide CLI auto-detection. |
| **T3 Code V2** | Lightweight web + mobile | Cross-harness delegation. Theo's project. He cannot support Google as a frontier lab in it, and he has confirmed an Anthropic Agents SDK bug that drains the 5-hour limit much faster than Claude Code directly. |
| **Orkas** | Local-first | Commander plus ~16 specialists, plus Claude Code, Codex, OpenCode, OpenClaw, Hermes. |
| **Nimbalyst** | Multi-provider | ~12 providers, optional worktrees. |
| **Claude Squad, dmux** | Terminal, tmux + worktrees | AGPL and MIT respectively. Sessions evaporate when the pane closes. One or two people each. |
| **crystl** | Indie, closed, Mac | Fanout and peer-quest patterns. One agency owner, a year of plain Claude Code, Indie Hackers post June. About $170/year. No marketing machine. |
| **Warp Oz** | Cloud control plane | Multi-harness cloud agents (Claude Code, Codex, Warp Agent). Zach Lloyd, ex-Google Sheets; Warp has raised on the order of $73M. Opaque server-side logs. |
| **amux** | Self-hosted kanban + iOS | Free or paid cloud. |
| **Kosmos, solos-swarm, CloudCLI** | Narrow | Claude-only boards, sandboxed fleets, persistent cloud containers. Not the same problem. |
| **MAO** | Canvas | Wire agents like a flowchart. |
| **Omnigent** (Databricks) | Meta-harness | Layer over other runtimes. |

Also named while looking for contract persistence (not full orchestrators): `ai-agent-handoff` (TASK.md / SESSION.md, admits no locking), `agent-harness` (contract.json, events.jsonl, capsule.md, fail-closed resume, but a skill on one runtime), `ariadoss/handoff` (markdown with the resume command baked in), OpenMOSS `claude-codex-handoff` (append-only JSONL and atomic leases between Claude and Codex — mailbox pattern for two harnesses), Agent Archive (export a thread to jump harnesses), Overseer (late October 2026 Claude Code plugin: live panes, mid-turn steering, Codex-as-subagent, resume by name — Claude-only).

### Camp C — what nobody in A or B does

They track which agent is running and which worktree it is in. When a sub-agent finishes, the transcript is swallowed into the parent or left as an orphan file. Worktrees sit until a human deletes them. Transcripts live wherever the harness felt like writing them. No packing, no signing, no parent-to-child pointer, no independent re-verify at close, no nested cluster of clusters, no SEED.

Claude Code's own docs, as cited: sub-agents may have a memory directory that survives conversations, but resume does not restore in-process teammates, and after a restart the lead may message agents that no longer exist. Codex is spawn, close, gone. A July arXiv paper was cited for the same point: the session is the durability boundary, and the fix is to put the durable part in files.

Anthropic's own numbers, cited in the session: multi-agent burns about **15×** the tokens of a normal chat. A September study: harness choice moved cost by up to **5×** at similar success rates. Cost tracking is part of orchestration, not a report you bolt on later.

### The word "clusters"

Almost unused as a product name in coding-agent tools. The field says swarm, parallel agents, orchestrator, or agent development environment.

Exceptions that do use the word, and are not this product:

- AWS Kiro blog: self-organizing multi-agent clusters, flat rings up to ~184 agents, one cited ring of 16. Flat topology. The pattern this design rejects.
- Cosmos Cloud: containers, unrelated.
- NVIDIA `cosmos-rl`: GPU replica groups, unrelated.

The name is free in this niche. It was kept because it is accurate: a lead with workers, coordinated, stateful, recoverable. Not a free-for-all.

### Who is actually building the alternatives

Mostly tiny teams. A few funded startups. One incumbent platform (GitKraken). No large engineering org owns cross-harness session lifecycle. Session management is the unsexy plumbing: orchestrator authors assume resume is solved, harness authors assume you will use their CLI. Nobody in the middle owns the lifecycle across twenty-plus tools. That is the opening, and it is unshipped.

---

## 8. How Clusters competes, and the architecture that follows

### Do not compete on

- Who can spawn more agents.
- Who has the prettier split terminal (Orca currently leads that UI).
- Who wraps the most CLIs.
- A demo that forgets the run when the process exits.

### Compete on

1. **Cross-vendor compatibility.** The differentiator vendors cannot ship, because each of them only speaks their own harness. ACP is the interop layer where it exists (on the order of forty agents in the registry with session list, fork, and resume). Where a vendor does not speak ACP — Anthropic's MCP stance was the example — fall back to the sessions-page parsers.
2. **Reconstructable runs.** Parent, children, tool calls, token spend, merge decision. Queryable after the fact.
3. **Structural handoff.** A respawned sub-agent receives a signed SEED, not a transcript dump. Claude parent, Codex child, neither has to know the other existed, as long as both can emit and consume the handoff file.
4. **Independent audit.** TidyUP seals. The ledger is the receipt. TidyUP2 is the witness that neither was forged. No surveyed orchestrator re-verifies the handoff artifact at close.
5. **Hierarchy with a real fan-out cap**, so polling and context stay bounded.
6. **One writer to the live tree**, with parallel proposals. COSMOS already runs this loop. Clusters inherits it.
7. **Rules that apply inside someone else's harness.** COSMOS is outside the child. The same fencing token, spend gate, and one-writer lease apply whether the child is Grok, Claude, or Hermes.
8. **Cost ledgers per child.** When the spawn race ends, this is what is still defensible. Fifteen-times burn makes "who spent what" a product feature.

### Three layers (the back-end cut)

**Spawn layer.** Talk ACP where the harness supports session list, fork, and resume. Otherwise use sessions-page parsers. Inject the spawn manifest. Enforce token and wall-clock quotas **before** the child starts, not after it is burning. Enforce CPU, memory, and disk caps at the OS before the process is allowed to run. A runaway child must not starve the lead.

**Record layer.** Write every child session durably **at spawn**, not after success. A crash mid-run still leaves a trace. Append-only hash-chained signed ledger. Sandbox directory per child. TidyUP collapses it to a SEED. TidyUP2 checks the collapse.

**Review layer.** This is CM Sessions. Chronological sidebar, delta scans, background backfill, the parent/child tree. Replay is triggered here and executed in Clusters.

### What the main agent in the native harness must be told

The orchestrator does not puppet the child's internals. It passes a short manifest:

- Here is your COSMOS root.
- Here is the SEED path.
- Here is how to call session-close before you exit.
- Here is your sandbox, your write file, and the rule that you do not write the live tree.

The agent needs the verb and the path. It does not need to understand HMAC, porosity, or the ledger format.

### Critical components still to implement (back end first)

Agreed list, in the order the session piled them up:

1. Spend attribution per child. Which harness burned what.
2. Merge handling when two proposals touch the same path. Everyone else punts to git and hopes. Clusters has a PIN holder who merges.
3. Liveness. A dead child is detected and respawned **with its SEED intact**, not dropped.
4. The spawn manifest / rule-injection layer.
5. Worktree or equivalent isolation per child for project files.
6. The ledger itself: append-only, hash-chained, signed.
7. OS-level resource caps and pre-spawn quotas.
8. Per-agent sandbox directory, collapse-on-close, retain-while-reviewing.
9. Replay engine (after the above is boring and reliable).
10. Front end for all of this. Explicitly deferred. Mechanics first.

### Front ends worth learning from, not copying

Orca is the UI to study for "many agents at once": split terminals, send a comment back into the agent, a browser with Design Mode, phone companions.

Paradev is the UI to study for phone review and scheduled automations. No Windows, so it is not a substitute.

Traycer is the UI to study for a shared plan across agents.

T3 Code is the UI to study for a light web-and-mobile control surface.

None of them show an audit-tied handoff tree. That view does not exist to copy.

---

## 9. Durability primitives (the part that is already COSMOS)

These are not ideas Clusters still has to invent. They are the close/open system, and they are also the audit system. One close event produces both.

### TidyUP

Close. Fail closed if control files do not validate. Emits the signed SEED: inherited facts, active leases, open watchers, handoff recipient.

### TidyUP2

Immediately re-measures. Porosity, occupancy, ledger head. If the close lied, the gate does not pass.

### BootUP

Open. Length and HMAC of the SEED must match before injection. No seal, no boot.

### ROLD

Living documents the session is allowed to read: glossary, rules, scars, command list. Token cost here is ordinary document-read cost. Stable prefixes hit prompt cache after the first call.

### What a child receives instead of a transcript

Not the last N parent messages. That burns tokens and loses the thread.

A structured handoff, sealed as the SEED:

- goal
- decisions already made
- files touched
- open questions
- pointer to the durable artifact on disk
- leases still held
- scars / recovery notes that apply (this was the later MDATA hook)

### Token cost of the audit

TidyUP, TidyUP2, HMAC, packing, and ledger appends are local. No model call.

The SEED at ~11 KB is roughly three thousand tokens if injected whole at BootUP. At Claude rates that was estimated around a cent and a half. Trim with a summary layer, or let the agent read only the sections it needs.

It scales with sub-agent count. A whole cluster run was shrugged off as on the order of a dollar. Against a 15× multi-agent burn, that is rounding error. It is also the cheap insurance against losing an unrepeatable dataset again (the September 2026 synchrotron loss is the concrete case: raw data mostly recovered, analysis pipeline and processed spectra not).

Ledger writes are disk I/O, not tokens.

### Enforcement consequence

Because children run inside their own vendor harness, they inherit that harness's permissions, sandbox, and prompt cache. Nothing in Orca, Traycer, or Kepler enforces a cross-harness rule set. COSMOS can, only if the manifest and the close verb are actually invoked. The audit is what proves they were.

---

## 10. Topology

### The failure of flat fan-out

A lead cannot manage fifty sub-agents.

- **Polling.** Fifty status polls is chatter. Five cluster leads reporting up is five signals, each already summarized.
- **Context.** One agent holding fifty transcripts is bloated by construction. Each lead holds its own cluster's summary. The top orchestrator holds summaries of leads, not transcripts of leaves. Context is bounded at every level.

### Fan-out

There is no published optimum. Practical ceiling cited: **three to seven direct children**. Below three you are not parallel. Above seven the lead fills with status.

Kiro's flat ring of sixteen was cited as the thing not to copy.

Keith's candidates were seven-plus-one or six-plus-one.

**Decision: six plus one.** Seven is the Miller ceiling and assumes well-behaved children. Six leaves headroom for one noisy or stuck agent without saturating the lead.

### Recursion

A cluster's worker may itself be a lead of a cluster. You manage clusters, not a bag of fifty agents. The same six-plus-one cap applies at every level.

### Failure domains (what the SEED makes recoverable)

| What dies | What happens |
|---|---|
| Child dies mid-task | Liveness notices. Respawn from the sealed SEED. Do not start over from an empty prompt. |
| Child finishes and writes garbage | TidyUP2 fails the close. The parent does not trust the output. |
| Lead dies | That cluster's SEED is already on disk. A replacement lead boots from it instead of reconstructing every child's history. |
| Top orchestrator dies | Every cluster record is durable on its own. Rebuild the tree by reading SEEDs. Do not replay the world to recover the index. |

Replay is a separate, optional, high-fidelity path for understanding a decision. It is not the recovery path.

---

## 11. Coordination and the PIN

### The problem

If several agents talk to each other and all write the same files, you get lost updates. If you pass a single global PIN around the whole tree, parallelism collapses into a relay race and the run takes all day.

### The rule that already exists in COSMOS

**Only one writer to the live tree.**

Everyone else writes proposals in their own sandbox. They do not block on each other. The PIN holder merges into the master record at whatever cadence makes sense.

Clusters does not invent this. It inherits a loop COSMOS already runs. The PIN solves both mutual exclusion and "who is allowed to touch the master." It does **not** have to be passed for every small message.

### Per-agent write files

Each agent has its own write file.

- It can read and write **its** file.
- It can read, not write, the other agents' write files.

That removes mailbox collisions entirely. It does **not** remove conflicts on shared project source. Two agents can both read `foo.py`, both decide to edit it, and both propose a write. So:

- Write files give awareness and a collision-free publish surface.
- The PIN plus sandbox proposals give exclusion on the live tree.
- Worktrees (or equivalent) keep in-progress code off the master until merge.
- A claim/lease is still required when two proposals name the same path. The lease system already in COSMOS is the enforcement, not a polite convention.

Scoped PINs (one per file or directory) were discussed as the alternative if a single tree-level PIN thrashes. The resolution in the session was stronger than per-file PINs: **do not let children write the master at all.** Scope is "the master record," and only the PIN holder touches it. Children never contend on it.

### Suggested write-file shape

Append-only, with sequence numbers, so a reader can reconstruct issued → extended → released instead of seeing only the latest line.

### Messaging

Direct peer chat was rejected as the coordination mechanism. It burns context on both sides and races. Publish state, decisions, and claims into the write file. Let others observe.

---

## 12. Persistence shape

```
cluster root/
  lead/
    sandbox/          # write file, proposals, worktree, lease state
    SEED               # sealed collapse of the above
  child-1/
    sandbox/
    SEED
  child-2/
    ...
  ledger               # append-only, hash-chained, signed
```

Lifecycle:

1. **Spawn.** Create the child folder immediately. Start the durable session record immediately. Do not wait for success.
2. **Run.** Child writes only inside its sandbox and its write file. It may read siblings' published write files and the project tree. It may not write the live tree.
3. **Close.** TidyUP packs the sandbox into a signed SEED. TidyUP2 re-measures. Ledger event appended.
4. **Retain.** Keep the raw folder while the cluster is live or under review, because replay wants original fidelity, not only the packed blob.
5. **Prune.** Later, by retention policy. Not during review. Not as the default at close.
6. **Boot.** BootUP checks length and HMAC, then expands the SEED back into a working sandbox for the replacement agent.

Other products, by comparison, keep a trash folder of worktrees and call it a log. That was called amnesia with a trash folder. The teams shipping those tools optimized for the demo. The reconstruction problem shows up only after a lost run — which is the failure mode this system is being built from.

---

## 13. Replay and the summary harness

Replay scrolls a cluster run event by event: every spawn, every tool call, every SEED seal. It is how you see where a merge went wrong or where a child vanished.

Placement:

- Trigger and display: CM Sessions.
- Engine: Clusters.
- Input: event range + SEED pointer.
- Output: frames streamed back to CM Sessions.

The summary harness inside CM Sessions is a meta-tool. Meta-tools recurse. Either:

- it is model-backed, and then it gets a SEED and a ledger line of its own, or
- it is deterministic, and then it stays AI-independent and unaudited, and it will miss some real changes.

Not resolved. Named so it does not get forgotten.

---

## 14. What is already built, and what Clusters still is

The session corrected an early "Clusters is a year of greenfield" reading. The foundation is most of the system. Clusters is wiring plus a spawn layer on top of it.

Already in the COSMOS lineage, as named in the chat:

- **sessions-page** — index and resume across twenty-plus harnesses, exe, loopback UI, COSMOS session-tools routing. On the order of a couple of months of part-time work.
- **COSMOS CODE** — the harness Clusters should reuse. In progress since around spring 2026; another several months of work on top of the indexer.
- **CM Sessions** — the browser. Child tree and replay not finished.
- **TidyUP / TidyUP2 / BootUP / SEED / HMAC** — close, adversarial re-measure, open.
- **ROLD** — living documents.
- **PIN and leases** — one writer, from BTS Mesh.
- **Memory shards, memory crystals, spontaneous artifacts** — durable state written during the run, not only at the end.
- **TokenCenter** — payments and spend caps.
- **Swarm Deck and cDECK** — multi-agent UI experiments. Useful as surface research, not as the cluster model.
- **BTS Mesh** — verdict orchestration.
- **SpiderCaster** — site builder motif. Major upgrade planned.
- **Crucible and the other adversarial motifs** — triage, second opinions, scars.
- **MDATA / ModelRaters** — measurement database and public rankings.
- **Daily Score** — named as existing; not opened in this chat.
- **ElitElixirs agent stack** — daily background agents. Evidence the orchestration loop already runs unattended. Not a Clusters feature.

### Rough effort, revised

An honest greenfield estimate given in the session was six to twelve months solo, sequenced spawn+record, then PIN and sandbox, then nesting and liveness, replay last, and with the trap called out: do not build the front end before the back end is boring.

That estimate assumed the primitives above did not exist. They do. What remains is mostly:

- spawn manifest injected into foreign harnesses
- child folder + immediate durable record
- collapse and retain
- liveness and respawn-from-SEED
- spend attribution
- PIN-holder merge of proposals
- the CM Sessions tree, delta index, and replay trigger
- much later, the management UI

No calendar commitment was made after the correction. The point of the correction was that this is not a third of a new product. It is the product's missing orchestration shell.

### Build order implied by the session

1. Record layer on top of sessions-page (child pointers, delta index, seven-day hot set).
2. Spawn manifest + sandbox directory + write file, still one harness end-to-end.
3. PIN-only writes to the master; proposals in the sandbox. This is wiring, not invention.
4. TidyUP collapse and TidyUP2 as the definition of "a child is done."
5. Liveness and respawn.
6. Second harness, to prove the manifest is actually cross-vendor.
7. Nesting: a lead whose worker is a lead. Six plus one at each level.
8. Spend ledger per child.
9. Replay.
10. UI only once the above fails closed without a human watching.

---

## 15. SpiderCaster and the free-tool rule

SpiderCaster today: a COSMOS motif (`cosmos_spidercaster.py`). You start from a problem prompt. Nine MOTIF stages become left-tab skins. IMPLEMENT writes a staged site, a sandbox, a publish-online option that waits for an explicit click, or a push to Gitur. Status discussed as "cooking." Extra pane for Profiles in cDeck. An Antigravity SDK tree exists beside the package. Graphics engine is due for a major upgrade toward a Wix or Shopify class of visual builder. Muse-in-Hermes is a plausible fit for that rendering loop for the same reason it fits the sessions UI: instant visual feedback.

The upgrade is a **freemium that is actually free**:

- Runs without a paid model.
- Choose a template, a palette or a set of palettes, and pre-packaged graphic elements.
- On the order of **200 pre-built templates** for the most common small-business types. That density was endorsed: enough to cover the real catalog, not a teaser grid of six.
- If you want elaboration beyond what free local models and the template system can do, you buy tokens through TokenCenter.

The rule, stated harder than typical freemium:

- Free should be as much as possible.
- Do everything possible to keep the free user free.
- "We don't want their money" as the default posture.
- Tokens are the exception path when intelligence beyond the template is actually required.
- This inverts the usual incentive. Free is the product, not the bait. You are not trying to frustrate people into paying.

Risk named, and rejected: a truly generous free tier might never produce token revenue, and small-business sites would be funded out of pocket. The reply was that this will not happen, because the people who burn serious tokens would have paid anyway, and because the business is not that meter.

### Why free is not charity

Three mechanisms, stacked:

1. **The flywheel.** Free runs still emit SEEDs, artifacts, failure patterns, and scars. The product improves whether or not anyone pays. A rival who clones the UI does not clone months of measured sessions.
2. **MOTIF / Crucible.** The same adversarial multi-agent pattern that reviews code also reviews higher-stakes work. A malpractice-averse lawyer or a doctor running a second and third opinion is not a "free user" in the growth-hack sense. They are the trust wedge. If that audit trail is trusted there, other verticals follow.
3. **The enterprise wedge** sits on top of the free tools, not instead of them. Free use by those people is also data for MDATA, which is what makes the tools harder to catch.

Google Maps was the analogy: the product improves because people use it with the phone in their pocket, not because they filled out a survey.

---

## 16. MDATA

Live at **`mdata.modelraters.com`** (spelled MDATA, not "m-data" as a host label). The hyphenated host returned 503 during this session. `modelraters.com` itself is the public rankings site: JSON and SQLite downloads, no key.

What the live MDATA surface contained, as read in this session:

- 138 empirical model evaluations.
- Six harness axes: form contract, coder task, judge form, availability, bakeoff, consistency.
- A constructors-style championship across 59 engine families and 39 makers.
- Pairwise disagreement: orthogonality and rescue probabilities.
- Forward projections: which models have the most headroom.
- A scars taxonomy: **14 canonical failure classes**, **11 recovery protocols**.
- Seated HERO models verified across eight layers from role down to mission.
- Version-one JSON endpoints and a downloadable SQLite database.

Not shown on the page: the ingestion path. How a free COSMOS session becomes a new row. That pipeline was treated as real and not yet public.

### Three ways COSMOS apps should read it

No new infrastructure. REST against the version-one endpoints.

1. **Model selection at spawn.** A coding child is chosen on the coder-task axis, not on a single blended rank.
2. **Adversarial pairing.** Crucible seats models with high orthogonality. Rescue probabilities pick a winner when they disagree.
3. **BootUP context.** The SEED can carry the relevant recovery protocols so a respawned agent knows the canonical failure classes before it starts.

### How to let COSMOS read it and not hand the same feed to everyone

A static API token compiled into the exe was rejected as the real control. Anyone who decompiles the binary has it. Rotation limits the damage. It does not remove it.

Cleaner gate, and the one to remember:

**Require a valid SEED HMAC.** BootUP already verifies it. There is no extra secret to steal. The proof of access is proof you are already inside a COSMOS close/open loop. A third-party scraper does not have a seal to present.

(The phrase in the chat drifted to "SEED HMXE" and was corrected to **HMAC**.)

### Should the methodology be public?

Yes, the methodology. No, the raw session payloads.

- Publish the schema and a sample ingestion log so the loop is visible and the moat is explainable.
- Keep raw session bodies private. That is where defensibility lives.
- A public **scars browser** on ModelRaters: searchable by failure class, model, harness, and recovery protocol. Five minutes to poke. Every search is a reason to return.
- That browser will not create traffic by itself. `modelraters.com` and `ai.solarolabs.com` do not have meaningful search traffic yet. SEO on an empty domain was dismissed as a thousand-year plan. Figroots and the furniture sites are the wrong home for this.

### Open submission?

If anyone may submit, MDATA becomes a common database. Public databases get forked. Someone seeds a clone with their own harness logs and ModelRaters is just a node.

Counterweight, if submission is opened anyway:

- Raw data is cheap and will be copied.
- The measurement framework is not: six axes, orthogonality math, rescue probabilities, the 14-class scars taxonomy, consistent scoring across model versions, cross-references.
- A competitor who reads the docs has a checklist. The database that took months to fill, and that fills every day, is the kitchen. The recipe is not the kitchen.

Poisoning is the other cost of open submission. Not resolved. Named.

### Who else scores models, and what they do not score

| System | What it actually measures |
|---|---|
| Artificial Analysis | Own evals, fixed settings, intelligence index plus cost and speed. Closest in spirit to a multi-axis board. |
| LMSYS / Chatbot Arena | Blind human preference, Elo. Not faithfulness, not traceability. |
| Epoch AI | SWE-bench, FrontierMath, confidence intervals. |
| Scale SEAL | Private expert-authored sets that do not leak. |
| HELM (Stanford) | Rigorous protocol. A methodology, not a live operational database. |
| Arena.ai causal tracing | Decomposes orchestrator, sub-agents, and tools into separate signals. Nearest public cousin of a porosity-style breakdown. |

None of them score the **lifecycle**: crashes, reseals, recoveries, the wound and the note. That is SCARS plus notes. The surprise in the session was that this is still unoccupied. Failure data sits in logs. Teams publish the highlight reel. Publishing the scar is both a trust signal (the surgeon who shows the scar) and the training signal (without it, every agent repeats the same mistake from zero).

### How the scars travel before the site has traffic

A small embed, not a destination site.

- An iframe or a script tag.
- Hits a ModelRaters endpoint.
- Returns one scar as styled HTML: failure class, model, what broke, what fixed it, link to the full entry.
- Paste into a blog, a docs page, or a GitHub README.
- It stays current because it reads the live endpoint.
- No dependency on Solaro Labs ranking in Google.

Distribution of the embed is still a human problem. The embed only removes the "come to my empty website" step.

---

## 17. Getting it in front of people

Constraints stated plainly:

- No existing GitHub audience. Discovery there is topics, stars, search, and a README with one sharp picture — not followers.
- Users of these tools do not live on GitHub. They live on X, Reddit, Discord, and Google.
- No time to sit in forums.
- Cold websites will not rank themselves into existence.
- Figroots and Saline River Workshop are the wrong properties. Solaro Labs is the right one and currently has no traffic.

### What actually worked for the tools in §7

Not "pedigree" and not "velocity" as abstractions. Concrete sequences:

- **Paradev:** a hackathon (Vibecon), friends who used it all day, Product Hunt #1, YC batch, a Show HN that tripled users overnight, a free desktop tier that removed reasons not to try, then a license change once it had gravity.
- **Orca:** daily releases as the growth engine, a trending day, one deep-dive post whose framing ("it orchestrates the agents you already use") got repeated by other people, and a phone notification when the agent finishes so the user does not have to stay at the laptop.
- **Traycer:** one Product Hunt day, then the VS Code marketplace, and the founder's own posts about agent loops.
- **crystl:** one founder, one Indie Hackers post, a tool that removed a pain he already had in public.

Pattern: one specific launch moment, then one artifact other people can point at. A moment plus a thing. Not a content calendar.

Keith's own discovery chain was offered as the real shape of spread: looking for an alternative to Cowork, found OpenWork, from there OpenRouter, from there Hermes, from there the rest. sessions-page → COSMOS → Clusters is the same kind of trail if the first link solves a lost-session wall.

### Channels that match the constraints

1. **Search for the pain, not the product name.** Queries like "Claude Code session lost" and "resume Codex session" have weak answers. Ranking Solaro Labs for those is right and slow.
2. **One good answer where the pain is already being discussed** (GitHub issues on the harness repos, Claude Code and OpenCode Discords, r/LocalLLaMA). Faster than SEO. Rejected as a lifestyle: no time to hang out there.
3. **Approve-queue automation** instead of hanging out. A bot watches for exact phrases, drafts a reply, and waits for a one-tap yes. Target: seconds a day, not an hour.

Tools named for that queue:

- **Reduck** — Reddit via a Chrome extension, no Reddit API app, posts only what you approve.
- **Prowlo** — MCP, Reddit plus X, ranked by intent.
- **RedReplier** — a skill for Claude Code or Cursor; watches Reddit, Hacker News, X, Bluesky; scores leads.
- **answerLoops** — self-hosted, draft-and-review with two agents, human approves, one inbox for Discord, GitHub, and Slack.
- **LangBot** — open-source Discord bot runtime if the agent should actually sit in a server.

Every one of those was chosen because it does **not** auto-post. Identical phrasing, new accounts, and links dropped too often get **shadowbanned** rather than banned. Shadowbans give no error and no appeal. A hard ban would teach the evasion. Aged accounts, varied wording, and no link in the first reply survive longer.

Buying warmed accounts and assuming they will die (the ReplyGuy / Bazzly / Engain model) was discussed and set aside as the brittle half. It can prime a first week. It dies on one platform change. The durable layer is the tool itself, found because it worked.

4. **Influencers, but not as a spray.** Mega-accounts post all day to audiences who do not run coding agents. A ten-thousand-follower account whose entire audience is people debugging harnesses is a concentrated hit. The exception: one mega-account in the exact niche (Theo, swyx were the examples; Karpathy less so, because his public stance is "everything should have an AI-native CLI," not "my session died"). Do not pitch them. Solve something they already complained about in public, so their post is a reaction, not an ad.

### Public complaints that match this product

Cited from recent posts, as a hook list, not as a commitment to contact anyone:

- **swyx:** `/compact` means you have already lost. He has called it a footgun and has shared Claude Code bug lists. He has also said this is the year of the sub-agent, that practical multi-agent problems are sub-agent problems, and that you should not build peer multi-agents. His line that sub-agents can have resources and contracts you define, and that you can update those contracts, is the PIN-plus-SEED system in other words. A launch thread framed as an answer to that question is not a pitch.
- **levelsio:** weekly complaints about Claude Code logging him out (broken OAuth). He built a tmux-per-folder script to force one session per site because `/resume` was annoying. Session loss and resume friction are the CM Sessions hook.
- **Theo:** the Agents SDK five-hour-limit bug, and the hole where T3 Code cannot sit on Google's frontier models. He already built a management surface, so he is adjacent, not unaware of the category.
- **Karpathy:** weaker hook. Wishes for AI-native CLIs. Not a lost-session complaint.

### What not to claim as unique

Hierarchy itself is not unique. Orca, Traycer, and Paradev already run lead-and-worker trees. Their contracts live in RAM and die with the process. Same shape, opposite lifespan. The public claim has to be the lifespan: durable, signed, re-verified, cross-harness, nested.

Almost nobody persists the contract. The file-brief pattern (TASK.md, contract.json, handoff markdown, JSONL leases) is converging from below, which is evidence the problem is real and still open. None of those sign the artifact, independently re-verify at close, or nest clusters.

---

## 18. Decisions locked in this chat

| Topic | Decision |
|---|---|
| UI iteration surface | Browser with hot reload, against an uploaded mockup. Muse in Hermes is the current worker. |
| Ship surface | Compile to an executable after the UI is right. |
| Grok Build | Wrong loop for layout. Fine for later hardening. |
| Antigravity | The app, not `agy`. |
| Manual diff review | Not part of this workflow. |
| Current build focus | COSMOS Clusters, with CM Sessions as the review layer. |
| Hot session window | 7 days, reverse chronological, directory mtime, cached. |
| Refresh | Delta scan from the newest cached timestamp. Older history in the background. |
| Child sessions in the sidebar | Must open the child file. Do not trust the parent transcript. |
| Fan-out | **Six plus one.** |
| Shape | Nested clusters. A lead's worker may be a lead. Never a flat fifty. |
| Live tree | One writer, the PIN holder. |
| Everyone else | Proposals in a private sandbox. Own write file. Read-only on peers' write files. |
| Global PIN passing | Rejected. It serializes the cluster. |
| Close | TidyUP seals a SEED. TidyUP2 re-measures. Both are the audit and the handoff. |
| Child folder | Created at spawn, retained for review, collapsed into the SEED, expanded on BootUP. |
| Replay | Trigger in CM Sessions, engine in Clusters. |
| Summary harness | Required for CM Sessions. Audit it if it is a model. Optional if it is deterministic. |
| Cluster harness | Reuse COSMOS CODE. Do not fork a second harness. |
| Front end | After the back end fails closed. |
| Free tier philosophy | As free as possible. Tokens only for elaboration. Do not want the free user's money. |
| MDATA access for first-party apps | SEED HMAC, not a baked-in API token. |
| Public scars | Methodology and a scars browser / embed, yes. Raw session payloads, no. |
| Distribution | Pain-shaped search, one pointable artifact, approve-queued replies, niche builders who already complained. Not forum residency, not bought accounts as the strategy, not mega-accounts by default. |

---

## 19. Open points

- Exact handoff schema fields beyond goal, decisions, files, open questions, artifact pointer, leases, scars.
- Whether write files are append-only with sequence numbers (proposed, not locked).
- Worktree versus "sandbox is enough" for project-file isolation. Both were affirmed at different moments: worktrees as table stakes for code, sandboxes as the COSMOS-native proposal surface. They are complementary, not alternatives, but the implementation choice is not specified.
- Merge algorithm the PIN holder uses when two proposals touch one path.
- Retention window for raw sandbox folders.
- Whether the CM Sessions summarizer is model-backed (and therefore sealed) or deterministic.
- How Daily Score fits. It was named and not inspected.
- SpiderCaster's formal boundary with COSMOS Core.
- Whether MDATA ingestion stays first-party-only or becomes open submission with a poisoning policy.
- Which single harness is the end-to-end proof before a second harness is added.
- The one-line public framing. The strongest candidate from the chat: Clusters is the sub-agent contract swyx described, made durable and auditable across harnesses, with a witness (TidyUP2) that the handoff was not forged.

---

## 20. One-paragraph version

CM Sessions shows the last week of coding sessions across every harness, newest first, with child sessions nested under their parents, refreshed by a delta scan and backfilled in the background. COSMOS Clusters runs those sessions as nested six-plus-one groups inside the vendor harnesses people already use, under COSMOS CODE, with COSMOS itself outside them as the authority. Each child gets a sandbox and a write file at spawn. Only the PIN holder writes the live tree. Everyone else submits proposals. At close, TidyUP seals a signed SEED, TidyUP2 re-measures it, and BootUP will not start the next agent without that seal. The SEED is the handoff, the ledger is the receipt, and TidyUP2 is the witness. Replay lives in Clusters and is triggered from CM Sessions. The same free runs feed MDATA's scars and notes, which first-party tools read by presenting a SEED HMAC. Parallel spawn is table stakes and other people already do it. Signed, re-verified, cross-harness, nested carry-over is the part they do not.
