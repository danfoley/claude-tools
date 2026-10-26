/**
 * SPEC:        The understand-first live viewer page.
 *              Stats: filters its concepts by status (a summary chip or a row chip keeps only that
 *              status, again or "Show all" clears it, an empty status says so, the filter survives
 *              a reload and the live refresh, and works from the keyboard) and names no language.
 *              Languages: a switcher shows the selected language's code dial, how each concept
 *              was applied in it and its own events, never changes the concept list, and is
 *              remembered across a reload. No test may leave a JS error behind.
 * TICKET:      none
 * LAST RUN:    2026-10-26, 18 passed in Chromium on 6 parallel workers (Playwright 1.60.0, 4.3s);
 *              54 of 54 passed with --repeat-each=3 (8.2s)
 * CODE STATE:  claude-tools @ main @ 487b3e9 plus the uncommitted viewer work (INFERRED, not
 *              recorded at run time)
 * ENV:         No URL is written in this file. A worker fixture starts the viewer
 *              (python3 viewer.py serve, port 0 so the OS picks a free one) against a temporary
 *              data folder and provides it as the baseURL, so a real ledger is never touched.
 *              Needs python3. Chromium comes from Playwright (npx playwright install chromium).
 * IF IT BREAKS: Coupled to understand-first/viewer/index.html (regions named Stats, Languages
 *              and Settings; lists named "Concepts", "Concepts in <language>" and "Recent in
 *              <language>"; chips named "<n> <status>"; "Show all"; the headings "Concepts (...)",
 *              "<language> code dial" and "Concepts in <language> (...)") and to
 *              scripts/viewer.py serve writing viewer.pid with its port.
 * RUN:         cd tests && npm install && npx playwright test
 */
import { test as base, expect, type Locator, type Page } from '@playwright/test';
import { spawn } from 'node:child_process';
import { appendFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

type ViewerServer = { url: string; dataDir: string };
type Ledger = { addConcepts: (...blocks: string[]) => void };
type SeededConcept = [name: string, status: string, applied: Record<string, string>];

const PLUGIN_ROOT = resolve(__dirname, '..', 'understand-first');
const LEDGER_HEAD = [
  'stage: 2',
  'stage-since: 2026-10-26',
  'primary-language: PHP',
  '',
  '## Code dial',
  '- PHP: rung 2, clean streak 1',
  '- TypeScript: rung 1, clean streak 0',
  '',
  '# Concept ledger',
  '',
].join('\n');
const SEEDED_CONCEPTS: SeededConcept[] = [
  ['idempotency', 'shaky', { PHP: 'a dispatched-at column per recipient', TypeScript: 'an idempotency key header' }],
  ['checkpointing', 'explained', { PHP: 'delete each conversation once its emails are queued' }],
  ['lease-with-expiry', 'shaky', {}],
  ['failure-isolation', 'new', {}],
  ['batching', 'explained', {}],
];
const SEEDED_EVENTS = [
  { date: '2026-10-24', time: '13:56', event: 'gate-retry', concept: 'idempotency', note: '', language: '' },
  { date: '2026-10-25', time: '09:10', event: 'dial-down', concept: '', note: 'PHP lowered one rung', language: 'PHP' },
  { date: '2026-10-25', time: '09:12', event: 'setting-changed', concept: '', note: 'added TypeScript at rung 1', language: 'TypeScript' },
];
const ALL_CONCEPTS = SEEDED_CONCEPTS.map(([name]) => name);

const test = base.extend<{ ledger: Ledger }, { viewerServer: ViewerServer }>({
  viewerServer: [
    async ({}, use) => {
      const dataDir = mkdtempSync(join(tmpdir(), 'understand-first-spec-'));
      seedData(dataDir);
      const viewer = spawn('python3', [join(PLUGIN_ROOT, 'scripts', 'viewer.py'), 'serve'], {
        env: { ...process.env, UNDERSTAND_FIRST_DATA: dataDir, UNDERSTAND_FIRST_PORT: '0' },
        stdio: 'ignore',
      });
      await expect.poll(() => listeningPort(dataDir), { timeout: 10_000 }).toBeGreaterThan(0);
      await use({ url: `http://127.0.0.1:${listeningPort(dataDir)}`, dataDir });
      viewer.kill();
      rmSync(dataDir, { recursive: true, force: true });
    },
    { scope: 'worker' },
  ],

  baseURL: async ({ viewerServer }, use) => {
    await use(viewerServer.url);
  },

  ledger: async ({ viewerServer }, use) => {
    seedData(viewerServer.dataDir);
    await use({ addConcepts: (...blocks) => appendFileSync(join(viewerServer.dataDir, 'ledger.md'), `\n${blocks.join('\n')}`) });
  },

  page: async ({ page, ledger }, use) => {
    const pageErrors: Error[] = [];
    page.on('pageerror', error => pageErrors.push(error));
    await page.goto('/');
    await use(page);
    expect(pageErrors).toEqual([]);
  },
});

test.describe('stats screen', () => {
  test('clicking a status in the summary keeps only the concepts with that status', async ({ page }) => {
    await summaryChip(page, '2 shaky').click();

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
    await expect(page.getByRole('heading', { name: 'Concepts (2 shaky of 5)' })).toBeVisible();
    await expect(summaryChip(page, '2 shaky')).toHaveAttribute('aria-pressed', 'true');
  });

  test('clicking the same status again brings every concept back', async ({ page }) => {
    await summaryChip(page, '2 shaky').click();
    await summaryChip(page, '2 shaky').click();

    await expect(statsConcepts(page)).toHaveText(namesStartingWith(ALL_CONCEPTS));
    await expect(page.getByRole('heading', { name: 'Concepts (5)' })).toBeVisible();
    await expect(summaryChip(page, '2 shaky')).toHaveAttribute('aria-pressed', 'false');
  });

  test('Show all appears only while filtered and clears the filter', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Show all' })).toBeHidden();

    await summaryChip(page, '2 explained').click();
    await expect(page.getByRole('button', { name: 'Show all' })).toBeVisible();
    await page.getByRole('button', { name: 'Show all' }).click();

    await expect(statsConcepts(page)).toHaveText(namesStartingWith(ALL_CONCEPTS));
    await expect(page.getByRole('button', { name: 'Show all' })).toBeHidden();
  });

  test('clicking the status on a concept row filters by that status', async ({ page }) => {
    await statsConcepts(page).filter({ hasText: 'failure-isolation' }).getByRole('button', { name: 'new' }).click();

    await expect(statsConcepts(page)).toHaveText([/^failure-isolation/]);
    await expect(page.getByRole('heading', { name: 'Concepts (1 new of 5)' })).toBeVisible();
  });

  test('a status with no concepts shows an empty message', async ({ page }) => {
    await summaryChip(page, '0 solid').click();

    await expect(statsConcepts(page)).toHaveCount(0);
    await expect(page.getByText('No solid concepts.')).toBeVisible();
  });

  test('switching from one status to another and back to all keeps working', async ({ page }) => {
    await test.step('filter by shaky, then by explained', async () => {
      await summaryChip(page, '2 shaky').click();
      await summaryChip(page, '2 explained').click();
      await expect(statsConcepts(page)).toHaveText([/^checkpointing/, /^batching/]);
    });
    await test.step('clear the filter', async () => {
      await summaryChip(page, '2 explained').click();
      await expect(statsConcepts(page)).toHaveText(namesStartingWith(ALL_CONCEPTS));
    });
    await test.step('filter by shaky again', async () => {
      await summaryChip(page, '2 shaky').click();
      await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
    });
  });

  test('the filter works from the keyboard', async ({ page }) => {
    await summaryChip(page, '2 shaky').focus();
    await page.keyboard.press('Enter');

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
  });

  test('the filter survives a reload', async ({ page }) => {
    await summaryChip(page, '2 shaky').click();
    await page.reload();

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
  });

  test('a concept added while the filter is on appears on the live refresh if it matches', async ({ page, ledger }) => {
    await summaryChip(page, '2 shaky').click();

    ledger.addConcepts(conceptBlock('async-boundaries', 'shaky'), conceptBlock('retries', 'solid'));

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/, /^async-boundaries/], { timeout: 10_000 });
    await expect(page.getByRole('heading', { name: 'Concepts (3 shaky of 7)' })).toBeVisible();
    await expect(summaryChip(page, '3 shaky')).toHaveAttribute('aria-pressed', 'true');
  });

  test('the stats screen does not name a language', async ({ page }) => {
    const stats = page.getByRole('region', { name: 'Stats' });

    await expect(stats.getByRole('heading', { name: 'Stage' })).toBeVisible();
    await expect(stats.getByText('PHP')).toHaveCount(0);
    await expect(stats.getByText('TypeScript')).toHaveCount(0);
  });
});

test.describe('languages screen', () => {
  test.beforeEach(async ({ page }) => {
    await page.getByRole('link', { name: 'Languages' }).click();
  });

  test('opens on the primary language and its code dial', async ({ page }) => {
    const languages = page.getByRole('region', { name: 'Languages' });

    await expect(languages.getByRole('heading', { name: 'PHP code dial' })).toBeVisible();
    await expect(languages.getByText('Rung 2 of 4')).toBeVisible();
  });

  test('switching language shows that language\'s code dial', async ({ page }) => {
    const languages = page.getByRole('region', { name: 'Languages' });

    await languages.getByRole('button', { name: 'TypeScript' }).click();

    await expect(languages.getByRole('heading', { name: 'TypeScript code dial' })).toBeVisible();
    await expect(languages.getByText('Rung 1 of 4')).toBeVisible();
  });

  test('switching language leaves the concept list unchanged', async ({ page }) => {
    await expect(languageConcepts(page, 'PHP')).toHaveText(namesStartingWith(ALL_CONCEPTS));

    await page.getByRole('region', { name: 'Languages' }).getByRole('button', { name: 'TypeScript' }).click();

    await expect(languageConcepts(page, 'TypeScript')).toHaveText(namesStartingWith(ALL_CONCEPTS));
  });

  test('shows how a concept was applied in the primary language, or that it was not', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Concepts in PHP (2 of 5 applied)' })).toBeVisible();
    await expect(languageConcepts(page, 'PHP').filter({ hasText: 'idempotency' })).toContainText('a dispatched-at column per recipient');
    await expect(languageConcepts(page, 'PHP').filter({ hasText: 'failure-isolation' })).toContainText('Not applied in PHP yet.');
  });

  test('shows how a concept was applied in another language, or that it was not', async ({ page }) => {
    await page.getByRole('region', { name: 'Languages' }).getByRole('button', { name: 'TypeScript' }).click();

    await expect(page.getByRole('heading', { name: 'Concepts in TypeScript (1 of 5 applied)' })).toBeVisible();
    await expect(languageConcepts(page, 'TypeScript').filter({ hasText: 'idempotency' })).toContainText('an idempotency key header');
    await expect(languageConcepts(page, 'TypeScript').filter({ hasText: 'checkpointing' })).toContainText('Not applied in TypeScript yet.');
  });

  test('lists only the events logged for the selected language', async ({ page }) => {
    const languages = page.getByRole('region', { name: 'Languages' });
    await expect(languages.getByText('PHP lowered one rung')).toBeVisible();
    await expect(languages.getByText('added TypeScript at rung 1')).toBeHidden();

    await languages.getByRole('button', { name: 'TypeScript' }).click();

    await expect(languages.getByText('added TypeScript at rung 1')).toBeVisible();
    await expect(languages.getByText('PHP lowered one rung')).toBeHidden();
  });

  test('remembers the selected language across a reload', async ({ page }) => {
    await page.getByRole('region', { name: 'Languages' }).getByRole('button', { name: 'TypeScript' }).click();
    await page.reload();

    await expect(page.getByRole('heading', { name: 'TypeScript code dial' })).toBeVisible();
  });

  test('switching language leaves the stats screen and its status filter alone', async ({ page }) => {
    await page.getByRole('link', { name: 'Stats' }).click();
    await summaryChip(page, '2 shaky').click();
    await page.getByRole('link', { name: 'Languages' }).click();
    await page.getByRole('region', { name: 'Languages' }).getByRole('button', { name: 'TypeScript' }).click();
    await page.getByRole('link', { name: 'Stats' }).click();

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
    await expect(page.getByRole('heading', { name: 'Concepts (2 shaky of 5)' })).toBeVisible();
  });
});

function statsConcepts(page: Page): Locator {
  return page.getByRole('region', { name: 'Stats' }).getByRole('list', { name: 'Concepts', exact: true }).getByRole('listitem');
}

function languageConcepts(page: Page, language: string): Locator {
  return page.getByRole('region', { name: 'Languages' }).getByRole('list', { name: `Concepts in ${language}`, exact: true }).getByRole('listitem');
}

function summaryChip(page: Page, name: string): Locator {
  return page.getByRole('button', { name, exact: true });
}

function namesStartingWith(names: string[]): RegExp[] {
  return names.map(name => new RegExp(`^${name}`));
}

function conceptBlock(name: string, status: string, applied: Record<string, string> = {}): string {
  const appliedLines = Object.entries(applied).map(([language, note]) => `- applied in ${language}: ${note}`);
  return [
    `### ${name}`,
    `- status: ${status}`,
    '- last verified: 2026-10-24',
    `- in the learner's words: ${name} in my own words`,
    `- recall question: what is ${name}?`,
    ...appliedLines,
    '- examples:',
    '  - example one (PR 1): something',
    '',
  ].join('\n');
}

function seedData(dataDir: string): void {
  const blocks = SEEDED_CONCEPTS.map(([name, status, applied]) => conceptBlock(name, status, applied)).join('\n');
  writeFileSync(join(dataDir, 'ledger.md'), `${LEDGER_HEAD}${blocks}`);
  writeFileSync(join(dataDir, 'events.jsonl'), SEEDED_EVENTS.map(event => JSON.stringify(event)).join('\n') + '\n');
}

function listeningPort(dataDir: string): number {
  try {
    return JSON.parse(readFileSync(join(dataDir, 'viewer.pid'), 'utf8')).port;
  } catch {
    return 0;
  }
}
