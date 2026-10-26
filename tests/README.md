# Tests

Tests for the plugins in this marketplace. They live outside the plugin folders, so installing a plugin never downloads them.

### What is tested
- `test_viewer.py`: unit tests for the understand-first viewer server. They check how the ledger and event log are read, that every change needs the page's token and the right Host, and that each settings change edits only what it should.
- `viewer.spec.ts`: a browser test of the viewer page. It checks the status filter on the concept list, including a reload, the live refresh and the keyboard; that the core Stats screen names no language; that the Languages screen switches the code dial, the per-concept notes and the events without changing the concept list; and that the page throws no JS error.

Both start their own viewer on a spare port against a temporary data folder, so a real ledger is never touched.

### Run them
- Unit tests, which need only `python3`: `python3 -m unittest discover -s tests`
- Browser test, from this folder: `npm install`, then `npx playwright install chromium` the first time, then `npx playwright test`
- Both: `npm test`
