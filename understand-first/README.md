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

### Menu and settings
Type `/understand-first:menu` to open the menu: Stats or Settings. Settings shows your current values and lets you change them: go back a stage (moving up happens on its own), switch stats mode, change your primary language, add a language or lower a code dial rung, skip the gates for one task, or reset to stage 1.

### Stats
Stats open in the terminal by default, with a menu for view, range and filter. Nothing leaves your machine.

Dashboard mode is opt-in. `/understand-first:menu mode dashboard` asks you once, then publishes your ledger and event log to a private claude.ai page with interactive filters, and refreshes it automatically at the end of each piece of work. `/understand-first:menu mode terminal` turns that off. The mode is stored as `stats-mode` in your ledger header.

For a one-off publish without changing the mode, use `/understand-first:menu dashboard`. `/understand-first:menu page` is the same and also refreshes the dashboard's page from `dashboard/index.html` after the plugin changes. `/understand-first:menu terminal` forces the terminal view while dashboard mode is on.

### Customizing
- Rules injected every session: `hooks/core-rules.md`.
- Full protocol: `skills/understand-first/SKILL.md`.

### Skipping
Say "skip the gates" for an emergency. Claude will comply and run a short debrief afterward.
