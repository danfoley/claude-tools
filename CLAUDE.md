# claude-tools

A Claude Code plugin marketplace. The plugin lives in `understand-first/`.

### Release rule
Every commit that changes anything under `understand-first/` must bump `version` in `understand-first/.claude-plugin/plugin.json` in the same commit. Otherwise users never receive the change: `claude plugin update` reports "already at the latest version" and they keep the old copy.

### Which number to bump (Semantic Versioning 2.0.0, https://semver.org)
- MAJOR (x.0.0): a backward-incompatible change. While the version is 0.y.z, do not use it.
- MINOR (0.x.0): new backward-compatible functionality. While the version is 0.y.z, also use it for backward-incompatible changes, because 0.y.z is initial development where anything may change.
- PATCH (0.0.x): backward-compatible bug fixes, plus docs-only and internal changes.
- When a higher number goes up, the lower numbers reset to 0.
- A version that has been pushed is never edited again. The next change gets a new version.

### Tests
- Tests live in `tests/` at the repo root, outside the plugin folder, so installing the plugin never downloads them. Do not put test files inside `understand-first/`.
- A commit that changes only `tests/` does not need a version bump, because it does not change what users receive.
- Unit tests: `python3 -m unittest discover -s tests`. Browser test: `cd tests && npm install && npx playwright test`. Both start their own viewer against a temporary data folder, never a real ledger.

### After pushing a release
- Refresh the marketplace listing before updating, or `claude plugin update` can say "already at the latest version" for a version that is already on GitHub: run `claude plugin marketplace update claude-tools`, then `claude plugin update understand-first@claude-tools`.
- Restart the live viewer from the new version folder so it never runs from an old one: `python3 <installed plugin folder>/scripts/viewer.py stop`, then `ensure`. The next session start does this by itself when the version changed; do it by hand to have it right away.
- Changed skill, rules or command text loads only in a new session.

### Before committing
- Run `claude plugin validate understand-first` and `claude plugin validate .`.
- Run the unit tests and the browser test.
- Mark a breaking change with `!` after the commit scope, as in `feat(understand-first)!: ...`.
