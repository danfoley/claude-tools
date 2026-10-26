---
description: Show your understand-first stats, change settings, or control the live viewer
argument-hint: [settings | recent [search words] | stats [days] | stage <n> | skip | reset | language <name> | add <language> | dial <language> | viewer on|off|open|stop|status | mode dashboard|terminal | dashboard | page]
---

Show the learner their understand-first stats first; settings are a separate screen. Looking at stats is not a learning event, so the stats views only read data. Changing a setting writes only the ledger header lines (never a concept entry) and appends one line to the event log, and it is always done through the plugin's own script, never by editing the files by hand.

Data directory: `${UNDERSTAND_FIRST_DATA:-$HOME/.claude/understand-first}`. It holds `ledger.md`, `events.jsonl` and `dashboard-url.txt`. If the ledger does not exist, say so and stop; the first session creates it.

Argument: `$ARGUMENTS`

Script: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/viewer.py"`, called below as `viewer.py`. It prints plain text or JSON and needs no network.

### Which screen

- No argument or `stats [days]`: Stats.
- `settings`: Settings.
- `recent [search words]`: Recent.
- `stage <n>`, `skip`, `reset`, `language <name>`, `add <language>`, `dial <language>`: Change a setting.
- `viewer on|off|open|stop|status`: Viewer.
- `mode dashboard`, `mode terminal`, `dashboard`, `page`: the hosted dashboard, which is opt-in. Follow Mode and Publish below.

### Stats

Run `viewer.py state` and print a compact plain-text scoreboard from its JSON: no pickers, no menus, nothing leaves the machine. Use this shape and nothing more:

- A line with the stage ("Stage 2 of 6, since 2026-10-26"), the primary language and the stats mode.
- A line counting concepts by status, then one line per concept: status, name, last verified date.
- A "Recent" list of the last 8 events, newest first, as `MM-DD HH:MM event` with the concept or note after it. With a number of days, show only events from that many days back.
- The code dial: one line per language with its rung.
- A footer: the live viewer address when it is running (`viewer.py status`), or "viewer off: /understand-first:menu viewer on" when it is not, then "Settings: /understand-first:menu settings".

Say plainly when there is too little data for a number to mean anything.

### Recent

Run `viewer.py state` and print the work log from the `work` list of its JSON as plain text, newest first by `date` (later entries first on a tie). With search words, keep only the items where every word appears, ignoring case, in the title, kind, understanding, date, source, problem, solution, gaps, or any concept's name, use or current status. The current status comes from the `concepts` list by name; a concept that is not in it is "not in ledger". Show up to 8 items. For each one print:

- `date · kind · understanding`, then the title.
- `Problem:` and `Solved:`, one line each.
- The concepts as `name (current status): how it was used`.
- `Unclear:` when there are gaps.

End with "Showing N of M", and say the viewer's Recent screen has the same list with filters. With no work recorded, say so: Claude adds an entry when a piece of work or a walkthrough ends.

### Settings

Run `viewer.py state` and print the current values in a few lines: stage and its start date, primary language, stats mode, whether the viewer is on, and the code dial rung per language. Then list the commands that change them, one per line:

- `stage <n>`: go back to a lower stage. Moving up happens on its own.
- `language <name>`: set the primary language.
- `add <language>`: add a language to the code dial at rung 1.
- `dial <language>`: lower that language's rung by one.
- `skip`: skip the gates for the next task.
- `reset`: go back to stage 1, after a confirmation.
- `viewer on|off`: keep the live viewer running, or not.
- `mode dashboard|terminal`: publish to a hosted page, or not.

### Change a setting

Run `viewer.py act '<json>'` with the matching request and report its one-line answer or its refusal as it came:

- `stage <n>`: `{"action": "stage-down", "to": <n>}`
- `skip`: `{"action": "skip-gates"}`, then tell the learner Claude will skip the gates for the next task and debrief afterward.
- `reset`: ask in plain text "Reset to stage 1? Your concepts and code dial stay. Reply yes." and wait. Only on a yes run `{"action": "reset-stage", "confirm": true}`.
- `language <name>`: `{"action": "set-language", "language": "<name>"}`
- `add <language>`: `{"action": "add-language", "language": "<language>"}`
- `dial <language>`: `{"action": "dial-down", "language": "<language>"}`

### Viewer

The live viewer is a small local page, served only on this machine at `http://127.0.0.1:37750`, that shows the stats and the settings and updates by itself.

- `viewer on`: set `viewer: on` in the ledger header (add the line after `primary-language` if it is missing), run `viewer.py ensure`, and print the address it returns. From then on every session start keeps it running.
- `viewer off`: set `viewer: off` in the ledger header and run `viewer.py stop`.
- `viewer open`: run `viewer.py ensure`, then open the address it prints in the browser (`open <address>` on macOS).
- `viewer stop`: run `viewer.py stop`. It starts again at the next session start while `viewer: on`.
- `viewer status`: run `viewer.py status`.

### Mode

- `mode terminal`: run `viewer.py act '{"action": "stats-mode-terminal"}'`. Say that automatic publishing is off and the existing dashboard page is left as it is. Stop.
- `mode dashboard`: tell the learner that the concept ledger and the event log will be published to a private claude.ai page and refreshed automatically at the end of each piece of work, and ask in plain text whether to turn it on. Stop unless they say yes. On a yes, run `viewer.py act '{"action": "stats-mode-dashboard"}'`, then Publish. The live viewer page cannot turn this on, because it needs this consent.

### Publish

Used by `dashboard`, `page`, dashboard mode, and the automatic refresh at the end of each piece of work. `page` also rewrites the dashboard's page file (step 6). When `stats-mode` is not `dashboard` and `dashboard-url.txt` does not exist yet, first tell the learner that the concept ledger and the event log will be published to a private claude.ai page, and ask in plain text whether to go ahead. Stop if they decline.

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

For a command, tell the learner in two lines: the link, that it is private to them, and that it is a snapshot of their ledger and event log taken now. Name what left their machine: the concept ledger and the event log, nothing else. Remind them that plain `/understand-first:menu` keeps everything local. For the automatic refresh, say in one line that the dashboard was updated.

If the Artifact tool is not available or a step fails, say so in one line and carry on. Never block the work.
