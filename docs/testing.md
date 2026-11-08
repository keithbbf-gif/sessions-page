# Tests

Run these from `V:\a\ai\COSMOS\builds\sessions-page`. Each command is `py -3.14` and the file name.

```
py -3.14 test_cli_formats.py
py -3.14 test_cosmos_code_hook.py
py -3.14 test_desk.py
py -3.14 test_formats.py
py -3.14 test_frozen_root.py
py -3.14 test_local_names.py
py -3.14 test_plugin_api.py
py -3.14 test_sessions_page.py
py -3.14 test_store_fixes.py
```

These are the `test_*.py` files in the sessions-page folder. They are hermetic. They use temporary files, or they read the source in this folder. They do not walk the live session stores on this PC. `test_sessions_page.py` does start a temporary loopback page of its own. That page is part of the test. It is not a census of the stores on this machine.

On 2026-11-05, `test_formats.py` printed `ok 34`, `test_store_fixes.py` printed `9/9`, and `test_sessions_page.py` printed `68/68`. `test_desk.py` printed `21/21` and `test_local_names.py` printed `4/4` in the same pass.

A live census is not one of these scripts. The counts in [consumer/load-and-resume.md](consumer/load-and-resume.md) came from a census. They did not come from these tests.

What each file is for:

- `test_cli_formats.py` runs the `formats` command and checks the printed index. It does not open the desk and does not bind a port.
- `test_cosmos_code_hook.py` checks that the hook has no port, that `writes_live` is false, and that the verbs are find, load, resume, and formats. Opening the plug does not bind a socket.
- `test_desk.py` checks resume plans and the load plan. Importing the desk does not open a window and does not bind a socket.
- `test_formats.py` checks the format-index keys, the harness prefixes, and the extra rows that are not walked. It does not walk a live home.
- `test_frozen_root.py` checks that a frozen `product_root` and `var` sit beside the exe, and that an unfrozen root stays beside the source.
- `test_local_names.py` checks local titles, including `aiTitle`, on temporary files. It does not read a live profile.
- `test_plugin_api.py` checks the in-process plug: `port` null, `window` desk, and the format catalog. It does not start a server.
- `test_sessions_page.py` checks find, load, import, export, recover, and resume on a temporary fixture, plus the old page on a temporary server. It does not walk a live profile.
- `test_store_fixes.py` checks a large-database session cap, Hermes with and without a messages table, a Codex rollout that is still on disk, a missing rollout, a `.jsonl.zst` sibling, OpenWork part text, and Antigravity summary and conversation-db rows. It does not walk a live profile.
