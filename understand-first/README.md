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
- Stage 5: a pseudocode outline of the whole change in your own words.
- Stage 6: a retro at the end of each task. This is the full process.

### Recent work
Claude keeps a work log, `work.md`, next to your ledger: one entry for each piece of work, whether you built it together or asked for a walkthrough of a PR or some code. Each entry has the problem, how it was solved, the concepts it used and how each was used, how well you understood it when it ended (understood, partly, not yet, or not assessed), and anything still unclear. The viewer's Recent screen shows the entries newest first, and each concept shows its current status from your ledger, so it changes when your ledger does. If you later miss a recall question about a concept, every piece of work that used it shows it as shaky again.

You can search it: type words and only the work where every word matches in the title, problem, solution, gaps, or any concept's name, use or current status is kept, with the matches highlighted. Searching "shaky" finds the work that used a concept you are currently shaky on. You can also filter by understanding level and by built or walked through. `/understand-first:menu recent [search words]` prints the same list in the terminal.

### Understanding work that already exists
Ask in plain sentences: "help me understand this PR", "walk me through this function", "what does this commit do". Claude runs a walkthrough instead of explaining everything at once. You say what you think it does first. Claude splits it into small chunks, teaches the concepts you are missing with a link, and asks you to explain each chunk back or predict what happens in a case that is not in the code. It ends with you explaining the whole thing back, and it only counts as understood when you can. At stage 4 it adds the architect questions, and at stage 5 a pseudocode outline. What you learn goes into your concept ledger, and a walkthrough alone can take a concept to explained but never to solid.

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
Everything lives in `~/.claude/understand-first/` (override with `UNDERSTAND_FIRST_DATA`): `ledger.md` (stage, code dial and concepts), `events.jsonl` (every gate, recall, test, delegation, stage move and phase time) and `dashboard-url.txt`. It is personal and never part of this repository.

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
Say "skip the gates" for an emergency. Claude will comply and run a short debrief afterward.
