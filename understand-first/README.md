# understand-first

A Claude Code plugin that changes how Claude works with you, so every piece of work ends with you understanding it, able to explain it back, and able to rebuild it without Claude. It works in any language and starts small: the process ramps up slowly, one habit at a time.

### What it does
- A SessionStart hook injects the core rules and your concept ledger into every session.
- The `understand-first` skill holds the full protocol: six stages, gates, per-concept levels, a per-language code dial, light gates for chores, inline recall questions and a retro.
- Understanding concepts matters more than writing them in any language. Concepts you already know become shared vocabulary, so design conversations rise to a higher level over time.

### Stages
Each stage adds to the one before. Claude moves you up on its own after at least one week of real work together with mostly clean results, and you can say "go back a stage" at any time.
- Stage 1: you state the problem in your own words before Claude proposes anything.
- Stage 2: you explain the change back before it is committed. A miss triggers teaching. The code dial starts.
- Stage 3: you pick and retell the design, predict test results, and fix review findings first.
- Stage 4: skeptical-architect questions at teach-back.
- Stage 5: for work you are building, a pseudocode outline of the whole change in your own words. It is never asked for when you are understanding or reviewing code that already exists.
- Stage 6: a retro at the end of each task. This is the full process.

### Recent work
Claude keeps a work log, `work.md`, next to your ledger: one entry for each piece of work, whether you built it together or asked for a walkthrough of a PR or some code. Each entry has the problem, how it was solved, the concepts it used and how each was used, how well you understood it when it ended (understood, partly, not yet, or not assessed), and anything still unclear. The viewer's Recent screen shows the entries newest first, and each concept shows its current status from your ledger, so it changes when your ledger does. If you later miss a recall question about a concept, every piece of work that used it shows it as shaky again.

You can search it: type words and only the work where every word matches in the title, problem, solution, gaps, or any concept's name, use or current status is kept, with the matches highlighted. Searching "shaky" finds the work that used a concept you are currently shaky on. In the viewer the search covers everything, not only the work: it also finds concepts in your ledger (your own words, the recall question, every example, how it was applied in each language) and every logged event, shown in their own groups. Each piece of work is collapsed to its title and chips; click it to open the details, or use Expand all and Collapse all. A search opens the cards that match. You can also filter the work by understanding level and by built or walked through. `/understand-first:menu recent [search words]` prints the same list in the terminal.

### Understanding work that already exists
Ask in plain sentences: "help me understand this PR", "walk me through this function", "what does this commit do". Claude runs a walkthrough instead of explaining everything at once. You say what you think it does first. Claude splits it into small chunks, teaches the concepts you are missing with a link, and asks you to explain each chunk back or predict what happens in a case that is not in the code. It ends with you explaining the whole thing back, and it only counts as understood when you can. At stage 4 it adds the architect questions. It never asks for a pseudocode outline, because the code already exists. What you learn goes into your concept ledger, and a walkthrough alone can take a concept to explained but never to solid.

### Code review
When you have Claude review a PR or code ("review this PR", "do a code review"), the plugin runs a review: a walkthrough first, then your judgment, kept to your stage. At stages 1 and 2 you say what you would flag before Claude adds what it sees. From stage 3 you propose your own review comments for each chunk and the rule behind them before any finding is shown, and we compare what you caught and what you missed. From stage 4 the architect questions are asked about the PR. Like a walkthrough, a review never asks for the pseudocode outline, because the code is already written, and Claude never posts, votes on or changes a PR without your approval for that action. The result goes into the work log as a `reviewed` entry, with what you did not catch under "still unclear".

### Code dial
From stage 2 you write a little code, and the amount grows by itself: one line, one test assertion, one whole test, one whole function. It is tracked per language, so a new language starts at the bottom. It only applies to concepts you have earned at level 2 or higher; concept levels always win. You never write the whole change from scratch.

### Sources
`sources.md` is a map of trusted places to look concepts up, by area: software design, object-oriented patterns, data, distributed systems, messaging, system design, delivery pipelines, the runtime stack, security, observability and testing. Claude uses it only when the work reaches a concept, teaches from the source with a link, and appends new sources it finds to `sources-added.md` in your data directory.

### Status line badge
A plugin cannot own your status line, so the badge is one line you add yourself. Each session the plugin copies `status.sh` to `~/.claude/understand-first/status.sh`; it prints `[understand:stage N]` from your ledger and prints nothing when there is no ledger.

If you already have a status line script, add:
```
understand_status=$(sh "${UNDERSTAND_FIRST_DATA:-$HOME/.claude/understand-first}/status.sh" 2>/dev/null)
[ -n "$understand_status" ] && parts="$parts | $understand_status"
```
If you have no status line, set `statusLine` in `~/.claude/settings.json` to `{"type": "command", "command": "sh ~/.claude/understand-first/status.sh"}`.

### Install
```
/plugin marketplace add danfoley/claude-tools
/plugin install understand-first@claude-tools
```

Try it from a local checkout without installing:
```
claude --plugin-dir ./understand-first
```

### First run
Claude asks for your primary language once and creates your ledger at stage 1.

### Your data
Everything lives in `~/.claude/understand-first/` (override with `UNDERSTAND_FIRST_DATA`): `ledger.md` (stage, code dial and concepts), `events.jsonl` (every gate, recall, test, delegation, stage move and phase time) and `dashboard-url.txt`, plus `work.md` and `sources-added.md`. A `sync/` folder inside it holds this computer's sync settings and state. It is personal and never part of this repository.

### Keeping your data safe (storage backends)
Your data lives in a local folder, so a lost laptop loses it. A storage backend copies it somewhere else and brings it back on a new computer. Nothing changes for the plugin or for Claude: they keep reading and writing the local folder, and a small sync engine copies it to and from the backend. With no backend configured, nothing is copied and nothing leaves your machine.

The plugin ships one backend, `folder`, which copies your data into any directory you choose. Point it at a folder that OneDrive, Dropbox, iCloud Drive or Google Drive already syncs, or at a network drive.

The easiest way is the live viewer's Settings screen, which has a Storage card. It lists every backend the plugin found, shows the options each one needs, checks that the backend can be reached before it saves, and has a Sync now button to bring the backend's files to this computer. It works before your first session has created a ledger, so on a new computer you can choose your storage first and press Sync now.

The same thing from the command line, run from the plugin's `scripts` folder (inside `~/.claude/plugins/cache/claude-tools/understand-first/<version>/`):
```
python3 sync.py configure folder directory=/path/to/your/synced/folder
python3 sync.py status
python3 sync.py disable
```
`status` shows what is configured and the last sync problem, if any. `disable` goes back to local-only; your data in the backend is left where it is.

### How syncing works
- Session start: the plugin pulls from the backend before it reads your ledger.
- While you work: each prompt triggers a quick, non-blocking check. It pushes at most once every 20 minutes, and a prompt after 60 minutes of silence pulls first, so a session left open for days picks up work done on another computer.
- Session end: one last push.
- It pushes before it pulls, and it only replaces a local file that has no unsynced changes. A file this computer has never synced loses to the backend's copy, so a brand-new install never overwrites your real ledger.
- `ledger.md`, `work.md` and `sources-added.md` follow last writer wins. `events.jsonl` is merged line by line, so events recorded on two computers are both kept.
- Only those four files are synced. Per-machine state (the hashes, the push lock, the viewer's pid and log, `status.sh`, `dashboard-url.txt`) stays local.
- If your configured backend cannot be loaded or reached at session start, Claude tells you first and asks before falling back to local-only storage. A failed push is retried automatically.

Known limits: a slow backend delays session start, because the pull at session start is not time-limited. Two computers pushing a normal file around the same time keep only the later one. A pull can replace a file at the instant the viewer is writing it.

### Writing a new storage backend
A backend is one directory, and the plugin finds it by itself: nothing needs registering. Add `scripts/storage/backends/<name>/__init__.py` that defines a class named `Backend`:
```python
from storage.backend import Setting, StorageBackend


class Backend(StorageBackend):
    name = "s3"
    settings = (
        Setting(key="bucket", label="Bucket to keep a copy of your data in"),
        Setting(key="region", label="AWS region", default="us-east-1"),
    )

    def __init__(self, bucket, region):
        ...

    def get(self, name):
        ...

    def put(self, name, text):
        ...
```
- `name` is what users type in `configure`; use the same name as the directory.
- `settings` lists what the user must provide. Each one becomes a keyword argument of `__init__`, named by its `key`, with its `default` when the user leaves it out.
- `get(name)` returns the whole text of the file, or `None` when it does not exist. An empty file is `""`, not `None`.
- `put(name, text)` makes the file hold exactly this text, creating it when missing. Do it safely (for example write a temporary file, then rename) so a failure never leaves a half-written file.
- Let errors raise. The sync engine records them, keeps your local data, and retries later; never swallow an error or return `None` for a failure.
- `name` is always a plain file name such as `ledger.md`. Call `self.require_plain_file_name(name)` first to refuse anything with a path in it.
- You never deal with caching, change detection, locking, retries or merging: the sync engine does all of it for every backend.

The scanner skips a backend that fails to import, does not extend `StorageBackend`, leaves a method unimplemented, has no name, repeats a setting key or reuses another backend's name, and reports the reason. A skipped backend never affects the others.

To test it, copy the `StorageContract` tests in `tests/test_storage.py` for your backend (it needs a way to build one against a fake or temporary store), then run `PYTHONPATH=understand-first/scripts python3 -m unittest discover -s tests`. A test there already checks that every shipped backend loads. CI also lints and type-checks your backend with `npm run lint` (run it from `tests/`); no lint rule may be disabled, so fix the code instead. In your pull request, bump `version` in `.claude-plugin/plugin.json` as described in the repository's `CLAUDE.md`.

### Windows
Not supported yet, and untested. The hook commands use bash syntax and `python3`, files are read and written with the system's default text encoding instead of UTF-8, and Windows can refuse to replace a file another program has open. Someone needs to test the plugin on Windows and open a pull request with the fixes.

### Stats
Type `/understand-first:menu` to see your stats as a short text scoreboard: stage, concepts by status, recent activity and the code dial. Nothing leaves your machine, and there are no popups.

### Settings
Settings are a separate screen: `/understand-first:menu settings` shows your current values and the commands that change them.
- `stage <n>` goes back to a lower stage. Moving up happens on its own.
- `language <name>`, `add <language>` and `dial <language>` set the primary language, add a language to the code dial, and lower a rung.
- `skip` skips the gates for the next task, and `reset` goes back to stage 1 after a confirmation.

### Live viewer
The viewer is a small local page, served only on your machine at `http://127.0.0.1:37750`, with three screens. Stats is language-neutral: your stage, concepts and activity. Languages has a switcher; for the selected language it shows that language's code dial, every concept with how you applied it there (or "not applied yet"), and its own events. Switching language never changes the concept list. Settings has the buttons. It updates by itself every couple of seconds, so you can keep it open in a tab. Click a status chip on Stats to show only the concepts with that status.
- Turn it on with `/understand-first:menu viewer on`. It is off by default. While it is on, every session start keeps it running, and it stays up after the session ends. After a reboot it starts again at your next session.
- `viewer open`, `viewer stop`, `viewer off` and `viewer status` control it. Set `UNDERSTAND_FIRST_PORT` to use another port.
- It needs `python3` and nothing else, and it reads and writes only your ledger and event log. It listens on `127.0.0.1` only, checks the Host header, and every change needs a token that only the page it served can read.

### Hosted dashboard (opt-in)
`/understand-first:menu mode dashboard` asks you once, then publishes your ledger and event log to a private claude.ai page and refreshes it at the end of each piece of work. `mode terminal` turns it off. `dashboard` publishes once without changing the mode, and `page` also refreshes the dashboard's page from `dashboard/index.html` after the plugin changes.

### Customizing
- Rules injected every session: `hooks/core-rules.md`.
- Full protocol: `skills/understand-first/SKILL.md`.

### Skipping
Say "skip the gates" when you are in a hurry, or run `/understand-first:menu skip`. Claude does the work without slowing you down, and records it in the work log as `skipped` with your reason. It shows in the Recent screen with a note on how to go back to it, and you can filter Recent by `skipped` to find everything you still owe yourself. To go back to an item, ask for a walkthrough of it ("help me understand this"); when that ends, the same entry gets its real understanding level. A short debrief is offered, never forced.
