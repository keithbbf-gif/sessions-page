# cmSessions — agent brief

Status: design brief for an implementing agent. Source is a design session on 7 Nov 2026. Do not treat chat tone, rankings, or repo snapshots as requirements unless they are restated here.

Product id: `cmSessions`. User-facing name: CM Sessions.

## What you are building

cmSessions is the universal history and handoff tool for AI coding sessions.

It is **both**:

1. A **standalone installable app.** It runs on its own. It does not require Cosmos, cDeck, or any other Solaro module to index sessions, search them, open them, resume them, or hand them off to an installed harness.
2. A **plugin.** When cDeck / Cosmos is present, the same product mounts as a module inside that face. One codebase, two shells. Do not fork the session engine per shell.

The plugin shell and the standalone shell share indexing, search, filters, the transcript view, handoff, the planning view, and the Token Center client. The shell owns windowing, install, and how the module is hosted. The engine does not care which shell called it.

Do not make the standalone app a thin launcher for Cosmos. A person who never installs Cosmos must still get the full session product. Do not make the plugin a second, lesser copy. If Cosmos is installed, cmSessions uses it. If it is not, cmSessions still works.

## Stack decision (2026-11-07)

The product ships in this order. One engine. Do not fork it.

1. Standalone app first. Native window. `CM Sessions.exe`. No browser and no port.
2. The same engine is an integral part of COSMOS, called in-process through `cosmos_session_tools_kit.py`.
3. The same engine is a plugin for Cosmos Code, through `cosmos_code_hook.py`.

cDeck is a Tauri host around HTML. That is the host for the plugin pane later. It is not a reason to make the standalone app a web page.

## What you are not building

- You are not building Cosmos. Cosmos is the body: the resident system, the adversarial multi-model mesh, memory, leases, the ledger, the scheduler, spend. cmSessions plugs into that body. It is not the body.
- You are not building cDeck. cDeck is the visual face Cosmos is shown through. cmSessions is one module on that face, and also ships alone.
- You are not building a coding harness. That is Cosmos Code (a TUI, in progress) and Cosmos Harness (separate, nearly finished). cmSessions launches harnesses. It is not one.
- You are not building an IDE. Do not layout or brand it like an editor. Vendor editors already own that ground.
- You are not building ModelRaters, DailyScar, SpiderCaster, or Token Center. You call them. Contracts are below.

## Why it exists

People run more than one coding agent. Typical set: Claude Code, Codex, Grok Build, Antigravity, Gemini, plus whatever else is on disk. Official vendor extensions read only their own sessions. They do not search across vendors, and they will not hand a transcript to a rival.

The job of cmSessions, in one sentence:

**Pick up a session in a different harness, on a different model, with the context intact.**

Resume-in-place is required. It is the smaller half. The product is the handoff.

Concrete cases the UI must make normal:

- A thread that filled one model's window continues in another model because the window is bigger. Example used in design: a Grok 4.7 thread at ~200K continues in Gemini 4 with a larger context.
- A result from one model family is sent to a different family to check it before it is trusted.
- Context size is a routing choice, not a dead end.

The index is the translation layer between incompatible session formats. If the transcript is not portable, handoff is fake.

## Position in the Solaro / Cosmos stack

Use this hierarchy. Do not invert it.

| Piece | Role | Relation to cmSessions |
|---|---|---|
| Cosmos | Body. Resident system. Adversarial mesh, memory, ledger, leases, scheduler, spend. | Host and optional dependency. Degrade cleanly when absent. |
| cDeck | Face. Visual layer on Cosmos. | Hosts cmSessions as a plugin. |
| cmSessions | This product. Standalone app and plugin. | You are here. |
| Cosmos Harness | Harness, nearly finished at time of writing. | Launch target. |
| Cosmos Code | New coding TUI. Aimed at the same job as Py, Cline, and Claude Code. | Launch target. Not this repo's UI. |
| Token Center | Token supply and billing. | Account and meter for AI features. Coding handoffs spend here too. |
| ModelRaters (`mdata.modelraters.com`) | Ground-truth model rankings by task axis. Public JSON and SQLite, no key. | Advisory input to the handoff menu. Do not reimplement rankings. |
| DailyScar | Failure ledger. Each scar has a name, a law, and an instead. | Advisory input. Do not reimplement the ledger. |
| SpiderCaster | Separate free tool that spends Token Center tokens. | Out of scope. Do not couple the UI. |

Cosmos behaviors cmSessions may surface, but must not reimplement:

- Auto-resession. Crashed work is recoverable. The UI shows the wrecks and offers resume.
- Cache tapping.
- Memory crystals and memory shards. Cross-session memory lives in Cosmos. cmSessions displays and carries what the host provides. It does not invent a second memory store.
- Agent-to-agent motif: scratchpad plus prompt injection, so agents read each other's work without a human pasting it.
- Adversarial, dynamic interaction between models from different families. This is the Cosmos thesis. cmSessions performs the single-step version a person can invoke (send this transcript to another family). The unattended mesh stays in Cosmos.
- Shared surfaces for the mesh: Google Drive, OneDrive, GitHub, local folders, cloud repos, hosted databases, Cloudflare R2. Those mounts belong to Cosmos. cmSessions needs read access to **session stores**. Do not merge those two mounts casually.
- Token-economy optimization: cheap and free channels first, including free browser access over the DOM rail (Stagehand and Chrome-extension tools), then up the ladder to paid models. Paid is allowed. Free-only is wrong. Model choice uses ModelRaters plus data contributed by other installs.

There was an unfinished name in the source conversation after "memory shards." Do not invent a feature for it.

## Distribution rules

Standalone install:

- Indexes local session files for every detected vendor.
- Search, filter, sort, transcript, export, planning view, and handoff all work offline for the local/free path.
- Handoff launches whatever harnesses are installed on the machine (Claude Code, Codex, Grok, Antigravity, Gemini, Cosmos Code, Cosmos Harness, others). Missing harnesses are hidden, not shown as dead buttons.
- Token Center is optional until the user invokes a token feature. Do not gate first run on an account.
- Cosmos-only affordances (crystals, shards, mesh status, auto-resession internals) are absent or marked unavailable. Do not stub them with fake data.

Plugin install, cDeck present:

- Same engine, hosted as a cDeck module.
- May call Cosmos for auto-resession, memory carry, spend gate, and shared identity with Token Center.
- Must not require the rest of cDeck's modules to be open.
- Must not become the shell that owns every other module. It is a peer plugin.

Implementation constraint: session parsing, the index, filter state, handoff planning, and Token Center calls live in a shared core. Shells are adapters. If you are about to write a parser twice, stop.

## v1 scope

Ship the spine first. In order:

1. Detect and index sessions from every supported vendor, locally.
2. Search and the filter/sort model below.
3. Transcript view.
4. Split action: resume in the same harness and model, or hand off to another installed harness and model, with a visible context budget.
5. Status counts, including tokens burned today.

Not in the spine. Build after the spine works:

- Planning view. Free grid and local keywords first. Token-backed summaries after.
- Natural-language command bar. Local parser first. Model fallthrough second.
- Conflict UI when two vendors hold disagreeing context for the same file.

Do not widen v1 into "the home that launches every Solaro app." Launching the harness for a resume or a handoff is in v1 because handoff is impossible without it. Launching unrelated modules is not.

## Vendors

Index at least: Claude Code, Codex, Grok Build, Antigravity, Gemini. Plus a catch-all for other session stores you can detect.

Read them from disk. Do not depend on a vendor's extension being installed. Do not depend on a vendor API for history.

Session formats are proprietary and undocumented. Parsing is reverse engineering. Isolate one parser per vendor behind a single session record. A parser failure skips that file and records why. It does not fail the index.

## Session record

Normalize every vendor into one record. Minimum fields:

- Stable id.
- Vendor.
- Model, if known.
- Harness, if it differs from vendor.
- Project, from the repo path when one exists.
- Title, else first user prompt.
- Start time, last activity, duration if known.
- Status: active, idle, crashed, finished. Map vendor states into these. Do not leak vendor vocabulary into the UI.
- Token spend, if known.
- Parent / thread id, so a resumed or handed-off session can sit under its parent.
- Paths touched.
- Raw transcript location. Do not duplicate entire transcripts into the index row.
- Tags, favorite flag.

Topic and keyword are derived fields. They are not something the user must type before a session appears.

## Layout

Five regions. Each does one job. Standalone uses all five in one window. The plugin uses the same regions inside its cDeck pane. Do not invent a sixth region to explain the product.

### 1. Left rail

Filters. It does not navigate to other products. About 160px open, about 40px collapsed.

Top to bottom:

- Global search. Instant. Covers prompts, responses, tool calls, and paths.
- Vendor chips, **multi-select**. Claude, Codex, Grok, Antigravity, Gemini, Other. Checking two vendors shows both, interleaved by the current sort. Do not use radio buttons. The common query is "this repo, whoever ran it," not "only Claude."
- Primary axes: **project, topic, keyword.** Vendor is a cross-cut on whichever axis is active. It is not the primary axis.
  - Project groups come from repo paths, collapse, and show a count.
  - Topic and keyword are secondary filters layered on the current axis. Do not present four peer sort modes that fight for the same control.
- Status: active, idle, crashed. Crashed is visually marked and is the resume queue. Default crashed to the top of that status group.
- Favorites and tags.
- Recents: last five touched sessions. This is the fast path when one thought is split across two vendors.
- Saved views: named filter sets. Settings at the bottom of the rail.

The rail filters the list. It does not have its own independent scroll story.

### 2. Main list

One row per session:

- Vendor color and badge. Color-by-vendor is required.
- Title, or first prompt.
- Time.
- Token spend.

Toolbar:

- Sort by project, topic, or keyword, with vendor as the cross-cut.
- Secondary sorts: recency, spend, duration.
- Grouped vs flat. Grouped stacks a resumed or handed-off session under its parent thread. Flat is the escape hatch. Grouped is what makes cross-vendor history readable. Do not ship only one of these.

Click a row. Open the detail pane. Do not navigate to a new page.

### 3. Detail pane

- Header: vendor, model, start, duration, tokens.
- **Split action. Not one Resume button.**
  - Primary: continue in the same harness and model.
  - Menu: every installed harness, and the models available there. Missing harnesses do not appear.
  - This menu is also how a check is started: send this transcript to another family.
- Context meter. A single horizontal bar, green to yellow to red, as the current model's window fills. Put a mark where a handoff would truncate. This is the signal to move to a larger window before something is dropped.
- Transcript. Tool calls collapsed by default: name, inputs, truncated output, expand in place. File paths are links that open in the editor or the file manager.
- Actions: copy transcript, export Markdown, export JSON, tag, favorite.

If ModelRaters data is reachable, the handoff menu may annotate a model with the axis that matches the next step (coding, agentic, long context). Annotation is advisory. The user picks. If ModelRaters is unreachable, the menu still lists installed harnesses and models with no scores. Do not block handoff on the network.

DailyScar, if reachable, may warn on a model that has a relevant open scar. A warning is not a block.

Parked. Do not design this until a clean handoff works:

When two vendors have touched the same file and the carried context disagrees, the detail view must show the conflict. It must not silently pick a winner.

### 4. Status bar

Always visible:

- Sessions indexed.
- Active now.
- Tokens burned today, across keys.

The third figure stays. People look at it constantly.

### 5. Command bar

A single prompt at the bottom edge of the window. The user types a request such as "Antigravity sessions that touched the UPS pipeline last week" and it becomes filter state. It does not become a chatbot thread.

Execution:

- Common patterns (vendor names, date ranges, project keywords) are parsed locally in Python. No model, no latency, no token cost.
- Only genuinely ambiguous queries fall through to a small local model or a capped Token Center call. Keep that fallthrough under about 5 percent. Tokens spent parsing are not available for the coding the user actually meant to do.
- If the Token Center balance is empty or the user has no account, fall back to keyword matching. Do this silently. Do not modal-block. The free path is a speed bump, not a wall.

## Planning view

A second view. Not the default. Not the landing screen.

Do not use a month grid of raw sessions as the primary planning UI. Real work arrives in bursts, and a month grid becomes a blob.

Ranges: last day, last week, last month, last few months.

The view answers:

- What got done in the range.
- Sessions summarized, and summarized by topic.
- Keywords for the range.
- Loose ends: where the work actually stands today.
- A short projected plan for the next few days.
- A short list of suggested priorities.

Color by vendor applies here too.

A spend-by-day overlay is optional and secondary. The point of the view is the accomplishment and the unfinished work, not nostalgia and not a billing chart.

## Free path vs Token Center

Rule: if it can be done locally, it is free, in both the standalone app and the plugin. The paid boundary is inference. It is not search, and it is not install.

Signup path, when a token feature is invoked: Token Center. New accounts get free tokens on Inkling and the other free models. When that is not enough, they buy tokens. The same account pays for coding spend caused by handoff and resume. Do not invent a separate cmSessions subscription.

### Free

- Index, search, filters, sorts, status, recents, favorites, tags, saved views.
- Transcript, copy, Markdown export, JSON export.
- Keyword extraction. Use a local algorithm (TF-IDF or RAKE). No model.
- Planning grid and raw counts.
- Command-bar phrases the local parser handles.
- A crude priority list with no model: crashed first, then oldest unfinished. It will feel mechanical. That is acceptable. It shows the shape of the answer.
- Resume and handoff **launch**. The destination model spends whatever that vendor charges. That spend is not a cmSessions fee. Do not put a paywall on the act of launching.

### Costs tokens

- Ambiguous natural-language commands that miss the local parser.
- Topic summaries over a day, week, or month.
- Loose-end detection that has to read the corpus.
- The projected plan. Heaviest call. It reads across the range and says what is next.
- Suggested priorities that include a reason. Three items and a why. Ranking unfinished work is judgment. Do not pretend the crude heuristic is this feature.

Retention matters more than a subscription. A user who resumes and hands off from cmSessions is already spending tokens on the work. Planning features should run on the free path most of the time and call a model only when the free result is not enough, or when the user asks for the narrative.

## Handoff behavior

A handoff:

1. Takes the canonical transcript from the index, not a fresh scrape that might disagree with what the user just read.
2. Shows the context meter for the destination model before launch, including the truncation mark.
3. Starts the destination harness in the session's project directory when a path exists.
4. Passes the carried context in the form that harness accepts. Per-harness adapters live next to per-vendor parsers. Do not build one giant prompt that every CLI is hoped to understand.
5. Records the new session as a child of the parent thread, so grouped view stays coherent.
6. Does not delete or close the source session unless the user did that.

Resume-in-place is the same path with the destination fixed to the source harness and model.

Cross-check is a handoff whose instruction is to review the source transcript, not to continue it blindly. Keep that as a distinct item in the menu so it is not confused with continue.

Routing advice, when ModelRaters is up, is a sort hint on the menu. It is not an automatic launch. The user confirms the destination. Unattended adversarial runs are Cosmos's job, not this menu's.

## Integration contracts

**Session files.** Source of truth for history. Watch or rescan. Do not require the vendor app to be running.

**Token Center.** Optional client. Identify the user, read the balance, spend on the features listed above, and report today's burn to the status bar. If it is down, local features keep working.

**ModelRaters.** Read-only. Prefer the public documents already published (`models.json`, `leaderboard.json`, ratings, the SQLite `mdata.sqlite`). Cache them. No key. No private scrape of the HTML.

**DailyScar.** Read-only, optional warning source. Cache. Failure to load is not an error the user must dismiss.

**Cosmos, only when installed.** Auto-resession state, memory crystals and shards, spend gate, identity. Probe once. Cache the "absent" result so the standalone app does not pay a timeout on every launch.

**cDeck.** Host adapter for the plugin shell. The engine must not import UI from cDeck.

**Out of scope mounts.** Drive, OneDrive, GitHub, R2, and the other shared surfaces are Cosmos mesh mounts. Do not implement them inside cmSessions to make handoff "more collaborative."

## Non-functional

- Local-first. The index and transcripts stay on the machine. No telemetry as a requirement. Do not add telemetry.
- A parser crash, a missing Token Center, a missing ModelRaters, or a missing Cosmos must not take down search.
- First useful screen is the session list, populated, not an account form and not a planning narrative.
- Do not block the UI on a model call. Token features are explicit actions with a visible cost, except the command-bar fallthrough, which must stay rare and must degrade to keywords.

## Acceptance for the spine

The spine is done when all of these are true:

- Sessions from at least two real vendors appear in one list, without those vendors' own extensions.
- Multi-select vendor filter interleaves them.
- Sort by project, and a vendor cross-cut on that sort, both work.
- Opening a row shows the transcript and the context meter.
- Resume launches the original harness in the project directory.
- Handoff launches a different installed harness with the carried transcript, and the new session shows under the parent when grouped.
- With no Token Center account, search, list, transcript, local keywords, and launch still work.
- With no Cosmos installed, the standalone app still does all of the above.
- With cDeck present, the same actions work inside the plugin pane.
- Tokens burned today renders in the status bar when spend data exists, and renders an honest empty state when it does not.

## Build order

1. Shared session record, one parser per vendor, local index.
2. List, rail, detail, context meter. Standalone shell first so the plugin host cannot hide engine bugs.
3. Resume adapter per harness, then handoff adapter per harness. Grouped parent/child records.
4. Plugin shell on cDeck, same engine.
5. Status bar spend, once a Token Center or local usage source is actually available.
6. Planning view, free layer.
7. Command-bar local parser, then model fallthrough with silent keyword fallback.
8. Token-backed planning: topic summary, loose ends, projected plan, priorities with reasons.
9. Conflict UI for disagreeing file context. Not before step 3 is solid.

## Do not decide on your own

- The GUI stack, until you have read the existing cDeck / app tooling. That read is done. See Stack decision above.
- A cmSessions-specific subscription, price, or token tariff. Token Center owns that.
- Automatic launch of a "best" model with no confirmation.
- A second memory store parallel to crystals and shards.
- Implementing the adversarial mesh, DOM rail, or shared cloud surfaces inside this app.
- Filling the unknown feature name that was cut off after memory shards.
- Whether SpiderCaster appears anywhere in this UI. Current decision: it does not.
