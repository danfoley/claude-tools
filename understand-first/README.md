# understand-first

A Claude Code plugin that changes how Claude works with you. Every piece of work ends with you able to understand it, explain it back, and write it yourself without Claude.

### What it does
- A SessionStart hook injects the core rules and your concept ledger into every session.
- The `understand-first` skill holds the full protocol: seven gates, drive levels, light gates for chores, recall questions, and a retro after each ticket.
- Your concept ledger grows as you learn. Concepts you already know are used as shared vocabulary, so design conversations move to a higher level over time.

### Install
```
/plugin marketplace add danjfoleyrp/claude-customizations
/plugin install understand-first@claude-customizations
```

Try it from a local checkout without installing:
```
claude --plugin-dir ./understand-first
```

### Your data
The ledger lives in the plugin data directory (`$CLAUDE_PLUGIN_DATA/concepts.md`, falling back to `~/.claude/plugins/data/understand-first/concepts.md`). It is personal and never part of this repository.

### Customizing
- Target language: set once on first run, stored in the ledger header.
- Rules injected every session: `hooks/core-rules.md`.
- Full protocol: `skills/understand-first/SKILL.md`.

### Skipping
Say "skip the gates" for an emergency. Claude will comply and run a short debrief afterward.
