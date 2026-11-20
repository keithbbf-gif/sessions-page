# Accounts and settings

The full-screen page links directly to `/accounts.html` and `/settings.html`. Those files are served from `ui/` by `sessions_page._serve`. The title-bar gear, the gear beside User Name, and the User Name control open those pages. They do not only write a status line.

`/accounts.html` mounts the shared 7-tab `<solaro-account>` component (`ui/solaro-account.js`) via `solaro_core`. The tabs are account, usage, logs, billing, settings, keys, and models. In local mode it posts to `/api/run` and sends `X-CM-Token` when the page has `<meta name="cm-token">`. When a credit or balance is unmeasured, `<solaro-account>` shows "—" and the account status fields show "Not reported". It does not invent a balance. Nothing on either page signs you in.

`/settings.html` stores theme, row density, and page size in this browser under the `localStorage` key `cmSessions.settings`. `index.html` reads that key and applies theme, row density, and page size live.

`POST /api/run` accepts `account_status` without calling `engine.dispatch`. If the TokenCTR bridge is not configured, the response is `status: unavailable`.

## What the account buttons do

On the full-screen page, the bottom-left control says "User Name" and shows the initials UN. It links to `/accounts.html`. The title bar also links Accounts to that page. It does not only write a status line, and it does not call the engine by itself.

The status line on the right says "Estimates only · Token Center optional". That text is part of the page. It is not a balance, and it does not change when you scan.

The classic page has no account control. The desk has no account control.

Find, Load, Resume, and Launch do not ask who you are. They read files on this computer. See [safety.md](safety.md).

## What the settings buttons do

The gear in the title bar and the gear beside User Name both open `/settings.html`. Neither one only writes a status line. `index.html` reads `localStorage` `cmSessions.settings` for theme (`dark` or `light`), row density (`compact`, `regular`, or `comfortable`), and page size (`25`, `50`, `100`, or `200`) and applies them live. `/settings.html` writes that same key.

These controls on the full-screen page do change what you see:

- A cycles the summary font. The order is Bahnschrift SemiCond, Inter Tight, then IBM Plex Condensed. It starts on Bahnschrift. It is not saved. The next time you open the page it starts over.
- Sz cycles the summary size. The order is Small, Med, then Old. It starts on Old. It is not saved.
- The square in the title bar asks the browser for full screen, or leaves it. Minimize and Close in that bar do nothing.
- Dragging a table-column edge saves the widths in this browser under the local storage key `cm_sessions_col_widths`. Showing or hiding a column is not saved.
- Maker, harness, sort, and the search box last only until you reload the page. Search is a filter of the rows already listed. It is not a setting, and it is not a new Find. See [find-and-name.md](find-and-name.md).

The classic page has checkboxes for vendor, status, and which columns are visible. Unchecking a column hides it until you reload. Print this view calls the browser print. The last five sessions you open are kept in session storage under `cmsessions.recents` for that tab. They are not an account, and they are not written to `var`. Create summaries does not call a model.

The desk Tools page has one named switch, and it is not a settings screen. Name stays off unless `CMSESSIONS_NAME` is `1` and `XAI_API_KEY` is set. That button sends a header, not the transcript. If naming is unavailable, the desk says "Naming is off." The engine does not read those two variables itself. See [find-and-name.md](find-and-name.md).

`serve` still binds `127.0.0.1`. The port defaults to 8786 ([sessions_page.py](../../sessions_page.py) `sessions_page._serve`, `sessions_page.main`). That is a start flag, not a setting you can change from the page. `--port` and `--no-browser` are the only `serve` flags ([sessions_page.py](../../sessions_page.py) `sessions_page.main`). The desk takes no flags and does not bind a port ([desk.py](../../desk.py) `desk.main`).
