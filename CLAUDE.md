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

### Before committing
- Run `claude plugin validate understand-first` and `claude plugin validate .`.
- Mark a breaking change with `!` after the commit scope, as in `feat(understand-first)!: ...`.
