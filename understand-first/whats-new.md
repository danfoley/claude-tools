## 0.14.0
- Your ledger, work log and events are backed up before any sync overwrites them, and at every session start (newest 10 of each kept in the backups folder next to the ledger).
- Sync no longer replaces your files with an empty or much smaller copy from the backend, and no longer pushes an empty or much smaller local file. It tells you instead.
- A lost or damaged sync history no longer duplicates your events or loses local work: the old file is saved and you are told.
- The session start pull gives up after 15 seconds instead of hanging.
- Saving a file no longer fails or loses data when two things write at the same moment, and logging an event now appends to the log instead of rewriting it. Windows line endings and bytes that are not valid text survive a save.
- Turning storage off now forgets what was synced, so a new backend receives everything.

## 0.13.0
- Session start now gives Claude a short summary of your ledger (each concept with its status) instead of the whole file, kept under the 10,000 character limit on hook output so it is never cut off. Claude opens the full entry when a concept comes up.
- A ledger that exists but cannot be read, or a summary that fails, no longer makes Claude start a fresh ledger or paste the whole file.
- Odd characters (control characters, a byte order mark, Windows line endings, a capitalised status) in the ledger no longer break the session start.

## 0.12.0
- "Where in the code" now shows the real code as a block with line numbers and the key lines marked. The explanation sits under the block, not inside it. Examples recorded before this keep the old text-only box.
- New Docs tab in the viewer: what you can say ("I don't know", "skip the gates" and more) and the slash commands, at a glance.

## 0.11.2
- The session start line has a blank line above it.

## 0.11.1
- The session start line is now in bold and color so it stands out from other plugins' startup output. Set NO_COLOR to turn color off.

## 0.11.0
- The viewer now updates itself. Within about 30 seconds of a plugin update the running viewer restarts on the new version, and an open page reloads.
- The viewer has a lightbulb icon in the browser tab.

## 0.10.0
- New Projects screen: pick any PR, ticket or project and see the problem, what was done, the skills used with your current level in each, and the decisions behind it.
- Examples are one line each. Open one to see what it is, where in the code (now a code block with a Copy button) and why.
- Stats groups concepts by status and activity by day. The status counts are the filters.
- The page is wider, and the code dial shows all four rungs with their names.
- Every session start says "Running understand first at level N, view is here" with the viewer address.
- After an update, the next session start also shows what changed, like this.
