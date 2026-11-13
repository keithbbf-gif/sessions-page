# cmSessions — Developer & Troubleshooting Onboarding Guide for Jack

Welcome to **cmSessions**, Jack! This document gets you up and running immediately on your PC so you can troubleshoot, polish the UI, and push updates using Antigravity.

---

## 1. What cmSessions Is

`cmSessions` is the local, multi-vendor AI coding session manager for the Solaro Labs / COSMOS ecosystem.
It discovers, indexes, reads, and resumes coding sessions from **26+ local AI harnesses** on your machine (Grok, Claude Code, Cursor, OpenAI Codex, Google Gemini CLI, Hermes, Antigravity, Cline, Aider, Copilot, Goose, etc.).

**Core Law of Local Silicon:**
Local CPU/RAM is free, model tokens are expensive. Zero tokens are spent on mechanical file discovery or driver errors.

---

## 2. Getting Started on Your PC

### Step A: Clone the Repository
Open PowerShell or your terminal on your PC:
```powershell
git clone https://github.com/keithbbf-gif/sessions-page.git
cd sessions-page
```

### Step B: How launch actually works
Make sure Python 3.14 (or Python 3.12/3.13) is installed. Read this from `sessions_page.py`. The Tk desk is not the only window.

The frozen exe with no arguments (`CM Sessions.exe` / `sessions_page.exe`, `console=False`) calls `_launch_gui()`. It does not call `desk.main()`. It binds `127.0.0.1`, serves `ui/index.html` (title "CM Sessions — Full Screen UI") with `ui/app.js` and `ui/app.css`, and opens that page. It tries ports 8786 through 8795. If `/api/verbs` on one of those ports already lists `find` and `resume`, it only focuses that page. On Windows it prefers `msedge.exe --app=http://127.0.0.1:<port>/` when Edge is installed; otherwise it uses the default browser. `POST /api/shutdown` stops the server. A frozen exe serves UI from the packed `_MEIPASS` copy, so editing the source `ui` folder does not change a running exe.

```powershell
# 1. UI work against the source tree. This is the same page the exe serves.
#    Default port 8786. Omit --no-browser and it opens the page.
#    F5 reloads ui/index.html, ui/app.css, and ui/app.js from disk.
py -3.14 sessions_page.py serve --port 8786

# Same page, no browser window from this process:
py -3.14 sessions_page.py serve --port 8786 --no-browser

# 2. Tkinter ledger only. This does not bind a port.
#    It is not what a double-clicked exe does.
py -3.14 sessions_page.py desk
```

`py -3.14 sessions_page.py` with no subcommand does not open either window. Argparse requires a command and exits with an error.

### Step C: Run the unit tests
Run these when you need to. This guide does not claim they pass, and it does not record a count.
```powershell
py -3.14 test_desk.py
py -3.14 test_sessions_page.py
py -3.14 test_store_fixes.py
py -3.14 test_record.py
py -3.14 test_formats.py
py -3.14 test_csm_core.py
```

---

## 3. UI Development & Hot-Reload Workflow

When working on UI styling, layouts, and animations:
1. Run:
   ```powershell
   py -3.14 sessions_page.py serve --port 8786
   ```
2. Open `http://127.0.0.1:8786` in Edge or Chrome.
3. Edit the UI assets directly:
   * **`ui/index.html`**: Main HTML structure, telemetry dashboard, Replay player, and TnT graph.
   * **`ui/app.css`**: Styling, colors, high-density layouts, animations.
   * **`ui/app.js`**: Frontend logic, column dragging, calendar rendering, Replay event playback.
4. Simply hit **F5 / Ctrl+R** in your browser to immediately see changes—**no compilation needed while developing**.

---

## 4. Key UI Features & What to Troubleshoot

Here are the primary areas ready for your inspection and polish:

1. **Draggable Column Headers:**
   * Test resizing the table columns (`Session ID`, `Title / Goal`, `Maker`, `Model`, `Harness`, `Turns`, `Spend`, `Status`).
   * Verify minimum column widths and smooth mouse release.
2. **Month $\to$ Week Calendar Zoom:**
   * Month view shows high-level 2-3 word topic summaries and hour badges.
   * Double-clicking any day box zooms into the 7-day Week View with model attribution bullets.
   * Check layout responsiveness on different window aspect ratios.
3. **Replay Mode:**
   * Step through session turns with the variable speed scrubber ($0.5\times$ to $5\times$).
   * Inspect diff highlighting and turn telemetry.
4. **Tracking & Tracing (TnT):**
   * Review subagent swarm DAG cascades and alert triggers.
5. **Cross-Harness Handoff:**
   * Selecting a session and clicking a launcher (e.g. Grok, Claude, Cursor) plans an export to `var/exports/` and logs lineage to `var/handoffs.jsonl`.

---

## 5. Building a New Executable

Build only after you have run the checks you mean to rely on. Do not treat an old handoff count as a pass.
```powershell
py -3.14 -m PyInstaller --noconfirm --distpath dist_desk sessions_page.spec
```
The binary is `dist_desk\sessions_page.exe`. With no arguments it opens the Full Screen page (`ui/index.html`) as described above. It does not open the Tk desk. Close a running exe before you copy over it. If the old process is still up, the copy fails.

---

## 6. Antigravity & Multi-Agent Architecture

When using Antigravity on your PC:
* Use the **G4Argon Orchestrator** pattern documented in `w:\db\NA+kees.md`.
* Antigravity coordinates high-level tasks and delegates parallel coding/testing to subagents (`EnableSubagentTools: true`, `EnableWriteTools: true`).
* Commit and push your changes back to `keithbbf-gif/sessions-page`:
  ```powershell
  git add .
  git commit -m "feat(ui): <describe your UI updates>"
  git push origin main
  ```

Have fun building, Jack!
