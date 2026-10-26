---
description: Open the understand-first menu (stats and settings), or use a shortcut: terminal, dashboard, page, mode dashboard, mode terminal
argument-hint: [terminal | dashboard | page | mode dashboard | mode terminal]
---

Open the understand-first menu. Looking at stats is not a learning event, so the stats views only read data and never write to the ledger or the event log. Changing a setting does write: it edits only the header lines of the ledger (never a concept entry) and appends one line to the event log.

Data directory: `${UNDERSTAND_FIRST_DATA:-$HOME/.claude/understand-first}`. It holds `ledger.md`, `events.jsonl` and `dashboard-url.txt`. If the ledger does not exist, say so and stop; the first session creates it.

Argument: `$ARGUMENTS`

### Which screen

- No argument: Main menu.
- `terminal`: Terminal view. `dashboard` or `page`: Publish. `mode dashboard` or `mode terminal`: Mode.

### Main menu

Ask with AskUserQuestion what the learner wants: Stats or Settings. Stats opens the Terminal view when `stats-mode` in the ledger header is `terminal` (a missing line means `terminal`), and Publish when it is `dashboard`. Settings opens the Settings menu.

### Settings menu

Before asking, read the ledger header and event log and show the current values in a few lines: stage and the date it started, stats mode, primary language, and the code dial rung for each language. Then ask with AskUserQuestion, with these options: Stage, Stats mode, Language and code dial, Skip or reset. After each change, show the new values and return to this menu. Stop when the learner is done.

**Stage.** Show the stage, when it started, and what the next stage adds. Offer: go back one stage, choose a lower stage, or back. The menu only lowers the stage; moving up happens on its own, after at least one active week of mostly clean work. A change sets `stage` to the new value and `stage-since` to today, and appends a `stage-down` event with the reason "learner request via settings".

**Stats mode.** Offer terminal or dashboard, following Mode below.

**Language and code dial.** List each language with its rung. Offer: lower a rung for a language (rung 1 is the floor), add a language at rung 1, or change the primary language (adding it to the dial at rung 1 if it is new). Append a `dial-down` event for a lowered rung and a `setting-changed` event for the others. The menu never raises a rung; that happens on its own, after three clean pieces in a row.

**Skip or reset.** Offer: skip the gates for this task, or reset to stage 1. Skipping appends a `gates-skipped` event and tells the learner that Claude will comply for this task and run a short debrief afterward. Resetting asks for confirmation first, then sets `stage: 1` and `stage-since` to today, appends a `stage-down` event with the reason "reset via settings", and leaves the concepts and the code dial as they are.

### Terminal view

Nothing leaves the machine. Read the ledger and the event log and ask the learner, with AskUserQuestion, which view they want: overview, concepts, tests, recall, delegations, or time per ticket. Then ask for the range (7 days, 30 days, 90 days, all time) and an optional filter by ticket or concept. Report from the data using the stats rules in the `understand-first` skill, say plainly when there is too little data, then offer the menu again so the learner can change the view, range or filter. Stop when they say so.

### Mode

- `mode terminal`: set `stats-mode: terminal` in the ledger header, adding the line if it is missing, and append a `setting-changed` event. Say that automatic publishing is off and the existing dashboard page is left as it is. Stop.
- `mode dashboard`: tell the learner that the concept ledger and the event log will be published to a private claude.ai page and refreshed automatically at the end of each piece of work, and ask with AskUserQuestion whether to turn it on. Stop if they decline. If they agree, set `stats-mode: dashboard` in the ledger header, adding the line if it is missing, append a `setting-changed` event, then Publish.

### Publish

Used by `dashboard`, `page`, dashboard mode, and the automatic refresh at the end of each piece of work. `page` also rewrites the dashboard's page file (step 6). When `stats-mode` is not `dashboard` and `dashboard-url.txt` does not exist yet, first tell the learner that the concept ledger and the event log will be published to a private claude.ai page, and ask with AskUserQuestion whether to go ahead. Stop if they decline.

1. Run `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/export_stats.py" <data directory> <scratchpad>/stats-out`. It writes `events.json` and `concepts.json`.
2. If `dashboard-url.txt` does not exist, create the dashboard once:
   - Call the Artifact tool with `action: "quickstart"`, `intent: "other"`, `design_systems: false`, then publish with the Dashboard `type_url` it returns, the title `Understand First Stats` and `auto_open: "after_first_write"`.
   - Save the new artifact URL in `dashboard-url.txt`.
   - Write the page: wrap `${CLAUDE_PLUGIN_ROOT}/dashboard/index.html` as `{"text": "<the file>"}` in a JSON file and write it with ArtifactData `set` to `files/index.html`. Also write `dash/meta` `{"title": "Understand First"}` and `dash/params` `{"range": "30", "ticket": "", "concept": ""}` in the same batch.
3. Upload `events.json` and then `concepts.json` as assets to the dashboard URL, one call each, and note the returned `/_blob/<id>` urls.
4. Read `datasets/events` and `datasets/concepts`, then update each with the new `source.url`, `source.name`, `source.format: "json"`, `updated: {at, by: "Claude"}` and `fixed: true`, pinning the version you read. Create them first if they do not exist: `{title, description, source, updated, fixed}`.
5. Delete the assets the datasets used before, so uploads do not pile up.
6. With the argument `page`, also rewrite `files/index.html` from `${CLAUDE_PLUGIN_ROOT}/dashboard/index.html`, pinning the version you read.
7. Open the dashboard with the Artifact tool, `action: "open"`, only when the learner asked for it with a command. In the automatic refresh, do not open it.

For a command, tell the learner in two lines: the link, that it is private to them, and that it is a snapshot of their ledger and event log taken now. Name what left their machine: the concept ledger and the event log, nothing else. Remind them that `/understand-first:menu terminal` keeps everything local. For the automatic refresh, say in one line that the dashboard was updated.

If the Artifact tool is not available or a step fails, fall back to the terminal view for a command, or say so in one line and carry on for the automatic refresh. Never block the work.
