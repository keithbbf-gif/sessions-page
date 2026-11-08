# Places, Find, and names

## Places

The desk lists places on the left. The first line is All sessions. Then each drive, with its letter, label, kind, and whether it is ready. Then each default session folder, marked present or absent, with its path when it is here.

This list does not count sessions. A count stays empty until you select a place or press Refresh. The program reads drive letters and labels. It does not walk every file on the drive to draw the list.

Select All sessions to clear the filter. Select a drive to show sessions on that drive. Select a folder to show that app only. Refresh reads the places again and runs Find again.

A place with no documented folder stays absent. Factory, Windsurf, and Augment are in that group on purpose. Amazon Q is absent unless `AMAZONQ_HISTORY` points at an export you already have. The program does not treat `~/.aws/amazonq` as a transcript store.

Shortcuts are not followed. A linked folder is not used as the store.

The format index also names some folders the program does not walk. Those are listed in [formats.md](formats.md). They do not appear as counted places.

## Find

Find counts sessions from headers. It does not open the text of a legal session. Search matches the title, the id, or the folder. Press Enter in the search box to run it again. The desk and the `find` command show up to 200 sessions, newest first. The old `serve` page shows 40.

```
py -3.14 sessions_page.py find --query "something" --harness claude --limit 200
```

`--harness` is the family name, such as `claude` or `grok`. `--cwd` limits the list to a working folder. There is no `--drive` flag. The drive filter is the drive you selected in the window.

A missing store is not zero. Its count is null, and the place stays absent. One bad store is skipped. That family's count is null, and its status is the error, not a number. The other apps are still counted.

`scan` looks at one store you name, and only that store:

```
py -3.14 sessions_page.py scan --store <path>
```

If that path is not a known kind of store, the count is null.

Legal sessions are still counted. Their title and folder are blank, and the row is labeled as a legal session. The count line says how many were left closed. A session is legal when its stream is named legal, or when its path, working folder, or title contains `\legal\`, `p:\legal`, `v:\ai\legal`, or `\abraxas\`. A path that ends in `\legal` is treated the same way. Find does not read that transcript.

Claude Code listing is one project folder deep. It does not open nested subagent folders. A session file sitting directly in the projects folder is still listed. A project folder whose name contains `claude-probe` is skipped and is not listed.

## How a session gets its name

Local naming is what the program does. A model call is not part of this build. There is no switch that turns an xAI name on, and the program does not spend an API credit to name a session.

The name is chosen on this computer, in this order:

1. A title the app already stored. That is a Grok summary title, a Cowork or database title, a Cursor header title, or another title already on the row. If that title is present, it is kept.
2. For a Claude or Claude Desktop jsonl whose title is still blank, the head of the file. An ai-title line stores its name in `aiTitle`. That local automatic name wins over the first user line, and it wins over a custom title on the same line. A custom-title line can also supply a custom title, title, or summary.
3. If the title is still blank, a short header sniff for a custom title, a generated title, a title, or a summary.
4. If the title is still blank and the file is jsonl, the first user line, cut at 80 characters. The program stops looking after about 256 KB. It does not read the rest of a long file just to name it.
5. Otherwise the title stays blank.

When the title is blank, the list shows the id. The id is not stored as the title. A legal row stays blank even if a name was found, and the id is what you see.

Index on the desk uses this same naming and writes the name into `var\index.jsonl`. When you are running the packaged app, `var` is the folder beside the exe. From source it is `var` in the program directory. A legal title is stored blank. A model call is still not used.

The id you see is the app's own id with a short prefix, such as `grok-`, `cc-` for Claude Code, `cdx-` for Codex, and `cur-` for Cursor. The prefix is not a title. Families that are only in the format index, and not in the walked list, have no prefix.
