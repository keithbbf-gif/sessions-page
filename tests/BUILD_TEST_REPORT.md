# BUILD_TEST_REPORT

Exact text from each testing done file. Nothing rewritten.

## testing-Tst-Spine.done

{"kind": "OK", "url": "http://127.0.0.1:53215/"}
ok   find counts every harness and leaves gemini unmeasured
ok   legal claude and cowork are counted, titles blank
ok   ids are stable
ok   cline, pi, gemini, and hermes are counted
ok   cline import reads the json history
ok   hermes sqlite is listed and its transcript import stays unmeasured
ok   documented stores are counted and indexes are not
ok   aider counts the one history file
ok   stores without a documented transcript stay null
ok   json transcripts import and sqlite or zstd stay unmeasured
ok   goose, crush, and dsh import stay unmeasured
ok   documented resume flags are named
ok   import writes canonical jsonl and leaves the md
ok   legal import refuses
ok   export is derived markdown
ok   index has no legal body text
ok   complete jsonl is already ok
ok   truncated jsonl without bak is named and untouched
ok   recover without apply does not copy
ok   apply restores from the sibling bak and stages the original
ok   sqlite restore uses the bak, not an in-place repair
ok   claude resume argv has no headless flag
ok   grok resume names --resume
ok   codex resume names resume
ok   cursor resume names agent --resume
ok   openwork resume does not spawn
ok   legal resume refuses
ok   scan of a catalog quotes n and legal
ok   unknown store is unmeasured, not zero
ok   load codex turn count
ok   anonymize redacts the copy only
ok   diff of a file against itself is identical
ok   seed check verifies len and sha
ok   sit check reads bucm
ok   strip dry writes nothing new
ok   preview quotes a turn and writes nothing
ok   legal preview refuses
ok   a harness filter keeps the other counts
ok   folder name seals a legal claude session
ok   wide transcript is past the preview head
ok   wide preview reads the head and does not invent a total
ok   a root summary title is searchable
ok   a missing summary title uses the first user line
ok   preview skips the system prompt and still counts it
ok   the next find sees a session added after the last one
ok   preview reuses the find list
ok   one bad store does not hide the others
ok   legal recover refuses
ok   foreign keys do not count as damage
ok   an empty jsonl is not already healthy
ok   an empty jsonl restores from the sibling bak
ok   an older good bak is used when the newest bak is bad
ok   sqlite restore parks the wal sidecar
ok   a blocked replace leaves the original in place
ok   a locked database is not replaced
ok   fresh must be a boolean
ok   project cwd counts and a blank legal cwd does not
ok   rebind stays closed
ok   doi does not claim existence
ok   home status does not pretend a count
ok   ui files exist
ok   standalone page serves a session list
ok   verbs route lists find and resume
ok   page refusal is a JSON error, not a disconnect
ok   a negative content length is refused
ok   places lists drives and default locations before a count
ok   find can stay on one drive
ok   plugin mounts one id and does not call Core
68/68
exit: 0

## testing-Tst-Desk.done

test_frozen_root.py exit 0
ok   claude resume argv starts with claude and --resume
ok   claude hit on grok is NEED_LOAD without the claude uuid
ok   a grok id on the hit uses grok --resume, not the claude uuid
ok   an empty app defaults to the hit harness
ok   openwork resume is OPENWORK_FOCUS
ok   cowork resume is OPENWORK_FOCUS and does not spawn
ok   a claude id is not focused as OpenWork
ok   cursor resume matches agent --resume
ok   cline --id is only for a messages file
ok   an unknown app is UNMEASURED
ok   load names the action and id and does not modify the source
ok   load plan has no write flag
ok   importing desk binds nothing
ok   desk has no ThreadingHTTPServer reference
ok   tkinter is not imported at module level
ok   plan json for a foreign app does not stuff the uuid into --resume
ok   plan_foreign_launch of a claude hit onto grok is HANDOFF
ok   plan_foreign_launch of a claude hit onto claude is not HANDOFF
ok   plan_foreign_launch of openwork is OPENWORK_FOCUS
ok   instance_name is Local\cmSessionsDesk
ok   claim_instance is not called by import
21/21
exit code: 0

## testing-Tst-Formats.done

py -3.14 test_formats.py
exit: 0
ok 34

py -3.14 test_store_fixes.py
exit: 0
ok  handoff record carries parent target pid export
ok  openwork find ow-id and load n_turns 2
ok  openwork 2001 messages TRUNCATED n_turns 2000
ok  hermes sessions-only load raises UNMEASURED
ok  hermes messages load kind OK n_turns 1
ok  codex real rollout n_turns 1 and missing file
ok  antigravity-cli find and load n_turns 1
ok  openwork part text is the turn
ok  codex jsonl.zst loads
ok  antigravity-ide lists a conversation db
ok  antigravity step_payload sentence without preview
ok  maybe_name stays off without env
12/12

py -3.14 test_record.py
exit: 0
ok   schema is the shared record
ok   vendor map folds harnesses and leaves the rest other
ok   find on the temp homes returns claude and grok
ok   those hits become claude and grok records
ok   a record has the shared fields and no transcript
ok   vendor multi-select interleaves claude and grok by activity
ok   a hit missing a title still makes a record
ok   a non-dict hit is skipped and transcript text is not copied
ok   status, tokens, and parent stay inside the record
ok   crashed rows stay and unknown times sort last
10/10


## testing-Tst-Core.done

ok   lmdb event roundtrip
ok   lmdb journal storage
ok   failover kernel missing dir
ok   failover kernel intercepts tokenizer error
ok   dual lock preflight valid
ok   dual lock preflight missing rule
ok   dual lock preflight excessive spend cap
ok   dual lock rule h2 isolation
ok   dual lock rule h3 exfiltration
ok   dual lock rule h5 spend ceiling
ok   dual lock redaction
11/11
EXIT:0

## testing-Tst-Skip.done

Tst-Skip done 2026-11-12.

Created only:
- tests/test_sibling_modules.py

Each test imports one of csm_core.errors, csm_core.persist, csm_core.tokenctr_bridge, csm_core.cosmos_pointer. A failed import skips that test. A successful import asserts errors.CODES when present, otherwise the module's public functions.

Command: py -3.14 -m pytest tests/test_sibling_modules.py -q --tb=line
Result: 4 skipped in 0.08s (exit 0). None of the four modules import on this branch.
No product code edited.
