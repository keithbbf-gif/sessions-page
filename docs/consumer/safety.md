# What stays on this computer

Sessions reads files on this machine and writes only the copies you ask for. Find, Load, Resume, Launch, Anonymize, and Recover do not upload a transcript. Naming does not call a model, and it does not spend an API credit. The program does not look up a citation on the network. It does not move a session into another app. Migrate and rebind stay closed.

The desk does not listen on a port. The packaged app opens that window and does not bind one. `serve` is the old page, and only that command binds `127.0.0.1`, on port 8786 unless you pass `--port`. COSMOS does not add a sessions port. Its port is null, and its window is the desk. See [cosmos.md](cosmos.md).

The desk buttons include Check recovery, Restore, Anonymize, Check strip, and Write strip, along with Load, Resume, and Launch. The old `serve` page still has its own buttons if you open it.

## Legal rows

A session is legal when its stream is named legal, or when its path, working folder, or title contains `\legal\`, `p:\legal`, `v:\ai\legal`, or `\abraxas\`. A path that ends in `\legal` is treated the same way.

Legal sessions are counted. Their text is not opened. The list shows a legal session, with a blank title and a blank folder. The index stores that title blank. Load, Import, Export, Anonymize, Recover, and Launch refuse them. Resume can still show a plan from the id already on the row, and it does not open the text to do that. Because the text is not read, it is not shown, copied, or sent.

## Recover

Check recovery does not change the file. Restore replaces the file from a verified sibling backup, and only when you apply it. On the desk, Restore asks "Replace this file with the backup beside it?" and applies only if you say yes.

```
py -3.14 sessions_page.py recover --target <file>
py -3.14 sessions_page.py recover --target <file> --bak <file>
py -3.14 sessions_page.py recover --target <file> --apply
```

`--target` is required. `--bak` is optional. `--apply` is what replaces the file. Without `--apply`, nothing is copied over the original.

The command only does this for a `.jsonl` file or a `.db` or `.sqlite` file. Other types stay unmeasured. On the old page, Check recovery and Restore from backup stay off for a database row. They are for a text session that page can already read. A legal target is refused. A file that is in use is left alone. A file that already checks out is left alone.

The backup has to sit in the same folder. Its name starts with the file's name and contains `.bak`. Shortcuts are ignored. The program uses the newest sibling that still checks out. A jsonl backup must parse. A sqlite backup must pass its own integrity check. A backup that fails is not used. If you pass `--bak`, that file is the only candidate. There is no search of the rest of the disk.

Apply does not rewrite the broken bytes in place. It first copies the original into `var\stage`, then replaces the file with a copy of the good backup. When you are running the packaged app, `var` is beside the exe. From source it is in the program directory. If the replacement does not check out, it puts the staged original back. If there is no good backup beside the file, the file is left as it is.

## Anonymize

Anonymize writes a new copy and leaves the session you selected unchanged. The copy goes under `var\exports` unless a caller gives another folder. The Anonymize button on the desk uses that folder. There is no anonymize command line in this build. The old page has the same button.

The copy replaces keys, tokens, passwords, and long secrets with a redaction mark. It is still a file on this computer. It is not sent away, and it is not a promise that every private detail is gone. A legal session is not anonymized, because its text is not opened.

Check strip, then Write strip, is on the desk and on the old page. It drops tool and system lines and leaves the original unchanged. Write strip does nothing until Check strip has succeeded for that same session. If it has not, the desk says the check has to succeed first. That copy is not uploaded either.

## What is not sent

Session text stays on this computer. The program does not call a model to name a chat. It does not fetch a citation. It does not open a legal transcript, so that text cannot leave with a preview or a copy. The desk does not listen, so the list is not served on a port. Recover reads the broken file and a sibling backup, and it writes only the staged original and the replacement on this disk. Anonymize and strip write their copies on this disk. Launch starts a local app only when you press Launch or pass `--launch`. The session's own app gets its resume command. Another app gets a local Markdown copy and a start with no resume id, and OpenWork is not started at all.
