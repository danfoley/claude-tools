/**
 * SPEC:        The understand-first live viewer page.
 *              Stats: filters its concepts by status (a summary chip or a row chip keeps only that
 *              status, again or "Show all" clears it, an empty status says so, the filter survives
 *              a reload and the live refresh, and works from the keyboard) and names no language.
 *              Languages: a switcher shows the selected language's code dial, how each concept
 *              was applied in it and its own events, never changes the concept list, and is
 *              remembered across a reload.
 *              Recent: lists the work log newest first with its understanding level, problem,
 *              solution and concepts, shows each concept's live status from the ledger, and is
 *              searchable (title, solution, concept name or status, several words, case,
 *              highlighting) and filterable by understanding and kind (built, walked through,
 *              reviewed).
 *              No test may leave a JS error behind.
 * TICKET:      none
 * LAST RUN:    2026-10-26, 46 tests; 138 of 138 passed with --repeat-each=3 in Chromium on
 *              parallel workers (Playwright 1.60.0, 18.6s)
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
 *              scripts/viewer.py serve writing viewer.pid with its port, and to the work.md format
 *              (### title, - kind / date / source / understanding / problem / solution / gaps,
 *              and "  - concept: use" lines under "- concepts:").
 * RUN:         cd tests && npm install && npx playwright test
 */
import { test as base, expect, type Locator, type Page } from '@playwright/test';
import { spawn } from 'node:child_process';
import { appendFileSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

type ViewerServer = { url: string; dataDir: string };
type Ledger = {
  addConcepts: (...blocks: string[]) => void;
  setStatus: (concept: string, status: string) => void;
  addWork: (item: SeededWork) => void;
  removeWork: () => void;
  addEvents: (...events: SeededEvent[]) => void;
};
type SeededEvent = { date: string; time: string; event: string; concept: string; note: string; language: string };
type SeededWork = {
  title: string; kind: string; date: string; source: string; understanding: string;
  problem: string; solution: string; concepts: Array<[name: string, use: string]>; gaps: string;
};
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
  ['idempotency', 'learning', { PHP: 'a dispatched-at column per recipient', TypeScript: 'an idempotency key header' }],
  ['checkpointing', 'getting it', { PHP: 'delete each conversation once its emails are queued' }],
  ['lease-with-expiry', 'learning', {}],
  ['failure-isolation', 'new', {}],
  ['batching', 'getting it', {}],
];
const SEEDED_EVENTS = [
  { date: '2026-10-24', time: '13:56', event: 'gate-retry', concept: 'idempotency', note: '', language: '' },
  { date: '2026-10-25', time: '09:10', event: 'dial-down', concept: '', note: 'PHP lowered one rung', language: 'PHP' },
  { date: '2026-10-25', time: '09:12', event: 'setting-changed', concept: '', note: 'added TypeScript at rung 1', language: 'TypeScript' },
];
const SEEDED_WORK: SeededWork[] = [
  {
    title: 'PR 449462: bulk messages sent in batch jobs', kind: 'walked through', date: '2026-10-27', source: 'PR 449462',
    understanding: 'partly', problem: 'a retry of the whole send re-emailed people who already got it',
    solution: 'the parent job only plans; small batch jobs send and mark recipients dispatched',
    concepts: [['idempotency', 'a redelivered batch skips recipients already dispatched'], ['batching', 'the unit of retry became 50 recipients']],
    gaps: 'what happens when the parent fails while enqueuing batches',
  },
  {
    title: 'Email digest sends each conversation as it goes', kind: 'built', date: '2026-10-24', source: 'PR 448805',
    understanding: 'understood', problem: 'one bad conversation blocked the whole digest',
    solution: 'delete each conversation once its emails are queued, so a retry only sees what is left',
    concepts: [['checkpointing', 'progress is recorded as it goes'], ['failure-isolation', 'one failing conversation no longer stops the others']],
    gaps: '',
  },
  {
    title: 'Renew the wildcard certificate', kind: 'built', date: '2026-10-20', source: '',
    understanding: 'not yet', problem: 'the local certificate expired',
    solution: 'issued a new one and replaced the encrypted files',
    concepts: [['certificate-chains', 'the intermediate must be replaced with the leaf']],
    gaps: '',
  },
];
const ALL_CONCEPTS = SEEDED_CONCEPTS.map(([name]) => name);
const CONCEPTS_BY_STATUS = ['idempotency', 'lease-with-expiry', 'checkpointing', 'batching', 'failure-isolation'];

const test = base.extend<{ ledger: Ledger }, { viewerServer: ViewerServer }>({
  viewerServer: [
    async ({ browserName }, use) => {
      const dataDir = mkdtempSync(join(tmpdir(), `understand-first-spec-${browserName}-`));
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

  ledger: [
    async ({ viewerServer }, use) => {
      seedData(viewerServer.dataDir);
      rmSync(join(viewerServer.dataDir, 'sync'), { recursive: true, force: true });
      const ledgerPath = join(viewerServer.dataDir, 'ledger.md');
      await use({
        addConcepts: (...blocks) => appendFileSync(ledgerPath, `\n${blocks.join('\n')}`),
        setStatus: (concept, status) => {
          const pattern = new RegExp(`(### ${concept}\\n- status: )[a-z]+`);
          writeFileSync(ledgerPath, readFileSync(ledgerPath, 'utf8').replace(pattern, `$1${status}`));
        },
        addWork: item => appendFileSync(join(viewerServer.dataDir, 'work.md'), `\n${workBlock(item)}`),
        removeWork: () => rmSync(join(viewerServer.dataDir, 'work.md'), { force: true }),
        addEvents: (...events) => appendFileSync(join(viewerServer.dataDir, 'events.jsonl'), events.map(event => JSON.stringify(event)).join('\n') + '\n'),
      });
    },
    { auto: true },
  ],

  page: async ({ page }, use) => {
    const pageErrors: Error[] = [];
    page.on('pageerror', error => pageErrors.push(error));
    await page.goto('/');
    await use(page);
    expect(pageErrors).toEqual([]);
  },
});

test.describe('stats screen', () => {
  test('clicking a status in the summary keeps only the concepts with that status', async ({ page }) => {
    await summaryChip(page, '2 learning').click();

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
    await expect(page.getByRole('heading', { name: 'Concepts (2 learning of 5)' })).toBeVisible();
    await expect(summaryChip(page, '2 learning')).toHaveAttribute('aria-pressed', 'true');
  });

  test('clicking the same status again brings every concept back', async ({ page }) => {
    await summaryChip(page, '2 learning').click();
    await summaryChip(page, '2 learning').click();
    await expandConceptGroups(page);

    await expect(statsConcepts(page)).toHaveText(namesStartingWith(CONCEPTS_BY_STATUS));
    await expect(page.getByRole('heading', { name: 'Concepts (5)' })).toBeVisible();
    await expect(summaryChip(page, '2 learning')).toHaveAttribute('aria-pressed', 'false');
  });

  test('Show all appears only while filtered and clears the filter', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Show all' })).toBeHidden();

    await summaryChip(page, '2 getting it').click();
    await expect(page.getByRole('button', { name: 'Show all' })).toBeVisible();
    await page.getByRole('button', { name: 'Show all' }).click();
    await expandConceptGroups(page);

    await expect(statsConcepts(page)).toHaveText(namesStartingWith(CONCEPTS_BY_STATUS));
    await expect(page.getByRole('button', { name: 'Show all' })).toBeHidden();
  });

  test('groups the concepts by status and opens only the learning group', async ({ page }) => {
    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);

    await expandConceptGroups(page);

    await expect(statsConcepts(page)).toHaveText(namesStartingWith(CONCEPTS_BY_STATUS));
  });

  test('activity is grouped by day with readable event names', async ({ page }) => {
    const day = page.getByRole('region', { name: 'Stats' }).getByRole('list', { name: 'Activity on 2026-10-24' });

    await expect(day.getByRole('listitem')).toHaveCount(1);
    await expect(day.getByRole('listitem')).toContainText('Gate retry');
    await expect(day.getByRole('listitem')).toContainText('idempotency');
  });

  test('older days wait behind a button and repeated study checks fold into one line', async ({ page, ledger }) => {
    ledger.addEvents(
      { date: '2026-10-26', time: '10:00', event: 'study-check', concept: 'idempotency', note: '', language: '' },
      { date: '2026-10-26', time: '10:01', event: 'study-check', concept: 'idempotency', note: '', language: '' },
      { date: '2026-10-27', time: '10:00', event: 'phase-end', concept: '', note: 'third day', language: '' },
    );
    const stats = page.getByRole('region', { name: 'Stats' });

    await expect(stats.getByRole('button', { name: 'Show older (1 events)' })).toBeVisible({ timeout: 10_000 });
    await stats.getByText('2026-10-26', { exact: true }).click();
    await expect(stats.getByRole('list', { name: 'Activity on 2026-10-26' }).getByRole('listitem')).toHaveText([/Study check ×2/]);

    await stats.getByRole('button', { name: 'Show older (1 events)' }).click();
    await stats.getByText('2026-10-24', { exact: true }).click();

    await expect(stats.getByRole('list', { name: 'Activity on 2026-10-24' }).getByRole('listitem')).toHaveCount(1);
  });

  test('a status with no concepts shows an empty message', async ({ page }) => {
    await summaryChip(page, '0 solid').click();

    await expect(statsConcepts(page)).toHaveCount(0);
    await expect(page.getByText('No solid concepts.')).toBeVisible();
  });

  test('switching from one status to another and back to all keeps working', async ({ page }) => {
    await test.step('filter by learning, then by getting it', async () => {
      await summaryChip(page, '2 learning').click();
      await summaryChip(page, '2 getting it').click();
      await expect(statsConcepts(page)).toHaveText([/^checkpointing/, /^batching/]);
    });
    await test.step('clear the filter', async () => {
      await summaryChip(page, '2 getting it').click();
      await expandConceptGroups(page);
      await expect(statsConcepts(page)).toHaveText(namesStartingWith(CONCEPTS_BY_STATUS));
    });
    await test.step('filter by learning again', async () => {
      await summaryChip(page, '2 learning').click();
      await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
    });
  });

  test('the filter works from the keyboard', async ({ page }) => {
    await summaryChip(page, '2 learning').focus();
    await page.keyboard.press('Enter');

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
  });

  test('the filter survives a reload', async ({ page }) => {
    await summaryChip(page, '2 learning').click();
    await page.reload();

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
  });

  test('opening a concept row lists its examples as one line each until one is opened', async ({ page, ledger }) => {
    ledger.addConcepts(conceptWithExamples('retry-safety', ['sent twice', 'skipped a stored id', 'resumed from a marker']));
    await expandConceptGroups(page);
    await expect(statsConcepts(page)).toHaveCount(6, { timeout: 10_000 });
    const row = statsConcepts(page).filter({ hasText: 'retry-safety' });

    await row.locator('summary').first().click();

    await expect(row.getByText('Example 1:', { exact: false })).toBeVisible();
    await expect(row.getByText('Example 2: skipped a stored id')).toBeVisible();
    await expect(row.getByText('Example 3:', { exact: false })).toBeVisible();
    await expect(row.getByText('what 2')).toBeHidden();

    await row.getByText('Example 2:', { exact: false }).click();

    await expect(row.getByText('What it is: what 2')).toBeVisible();
    await expect(row.getByText('Why it is retry-safety: why 2')).toBeVisible();
    await expect(row.getByText('what 1')).toBeHidden();
  });

  test('where in the code is a code block with a copy button', async ({ page, ledger }) => {
    ledger.addConcepts(conceptWithExamples('retry-safety', ['sent twice']));
    await expandConceptGroups(page);
    const row = statsConcepts(page).filter({ hasText: 'retry-safety' });
    await expect(row).toHaveCount(1, { timeout: 10_000 });

    await row.locator('summary').first().click();
    await row.getByText('Example 1:', { exact: false }).click();

    await expect(row.locator('.code')).toContainText('Where in the code');
    await expect(row.locator('.code pre')).toHaveText('where 1');
    await expect(row.getByRole('button', { name: 'Copy code locations' })).toBeVisible();
  });

  test('a code snapshot shows numbered lines, marks the key lines, and keeps the explanation outside the block', async ({ page, ledger }) => {
    ledger.addConcepts(conceptWithSnapshot('retry-safety'));
    await expandConceptGroups(page);
    const row = statsConcepts(page).filter({ hasText: 'retry-safety' });
    await expect(row).toHaveCount(1, { timeout: 10_000 });

    await row.locator('summary').first().click();
    await row.getByText('Example 1:', { exact: false }).click();

    const block = row.locator('.code');
    await expect(block.locator('.code-head')).toContainText('services/Notifier.php:41-43');
    await expect(block.locator('.code-line .ln')).toHaveText(['41', '42', '43']);
    await expect(block.locator('.code-line.hl .ct')).toHaveText(['$this->messages->deleteClaimed($ids);']);
    await expect(block).not.toContainText('the send then the delete');
    await expect(row.locator('.code-caption')).toHaveText('the send then the delete');
    await expect(row.getByRole('button', { name: 'Copy code' })).toBeVisible();
  });

  test('an example written as plain text still shows under its number', async ({ page }) => {
    await statsConcepts(page).filter({ hasText: 'idempotency' }).locator('summary').first().click();

    await expect(statsConcepts(page).filter({ hasText: 'idempotency' }).getByText('Example 1: example one (PR 1): something')).toBeVisible();
  });

  test('an opened concept row stays open when the stats refresh', async ({ page, ledger }) => {
    await statsConcepts(page).filter({ hasText: 'idempotency' }).locator('summary').first().click();

    ledger.addConcepts(conceptBlock('retries', 'solid'));

    await expect(page.getByRole('button', { name: '1 solid' })).toBeVisible({ timeout: 10_000 });
    await expect(statsConcepts(page).filter({ hasText: 'idempotency' }).getByText('example one (PR 1): something')).toBeVisible();
  });

  test('a concept added while the filter is on appears on the live refresh if it matches', async ({ page, ledger }) => {
    await summaryChip(page, '2 learning').click();

    ledger.addConcepts(conceptBlock('async-boundaries', 'learning'), conceptBlock('retries', 'solid'));

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/, /^async-boundaries/], { timeout: 10_000 });
    await expect(page.getByRole('heading', { name: 'Concepts (3 learning of 7)' })).toBeVisible();
    await expect(summaryChip(page, '3 learning')).toHaveAttribute('aria-pressed', 'true');
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

  test('shows where a concept was used and its code, only for the language of the code file', async ({ page, ledger }) => {
    ledger.addConcepts(conceptWithMixedLanguageExamples());
    await page.reload();
    await page.getByRole('link', { name: 'Languages' }).click();
    const languages = page.getByRole('region', { name: 'Languages' });

    await languages.getByRole('button', { name: 'TypeScript' }).click();
    await languageConcepts(page, 'TypeScript').filter({ hasText: 'retry-safety' }).getByText('typescript sender').click();

    await expect(languages.getByText('src/sender.ts:3')).toBeVisible();
    await expect(languages.getByText('const key = messageId;')).toBeVisible();
    await expect(languages.getByText('php sender')).toBeHidden();

    await languages.getByRole('button', { name: 'PHP' }).click();

    await expect(languages.getByText('php sender')).toBeVisible();
    await expect(languages.getByText('typescript sender')).toBeHidden();
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
    await summaryChip(page, '2 learning').click();
    await page.getByRole('link', { name: 'Languages' }).click();
    await page.getByRole('region', { name: 'Languages' }).getByRole('button', { name: 'TypeScript' }).click();
    await page.getByRole('link', { name: 'Stats' }).click();

    await expect(statsConcepts(page)).toHaveText([/^idempotency/, /^lease-with-expiry/]);
    await expect(page.getByRole('heading', { name: 'Concepts (2 learning of 5)' })).toBeVisible();
  });
});

test.describe('docs screen', () => {
  test('the Docs tab lists what you can say and the slash commands', async ({ page }) => {
    await page.getByRole('link', { name: 'Docs' }).click();

    const docs = page.getByRole('region', { name: 'Docs' });
    await expect(docs.getByRole('heading', { level: 2 })).toHaveText(['Things you can say', 'Stages', 'Slash commands']);
    await expect(docs.locator('code')).toContainText(['Stage 1', 'Stage 6']);
    await expect(page.getByRole('link', { name: 'Docs' })).toHaveAttribute('aria-current', 'page');
  });

  test('the Docs tab can be opened straight from its address and names the override phrases', async ({ page }) => {
    await page.goto('/#docs');

    const docs = page.getByRole('region', { name: 'Docs' });
    await expect(docs.locator('code', { hasText: '"I don\'t know"' })).toBeVisible();
    await expect(docs.locator('code', { hasText: '"skip the gates"' })).toBeVisible();
    await expect(docs.locator('code', { hasText: '/understand-first:learn [topic]' })).toBeVisible();
  });
});

test.describe('browser tab icon', () => {
  test('the page links an icon the viewer serves as an image', async ({ page }) => {
    await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', '/favicon.svg');

    const response = await page.request.get('/favicon.svg');

    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('image/svg+xml');
  });
});

test.describe('viewer update', () => {
  test('the open page reloads itself when the viewer has been updated to a new version', async ({ page }) => {
    let reloads = 0;
    page.on('load', () => { reloads += 1; });
    await page.route('**/api/state', async route => {
      const response = await route.fetch();
      const state = await response.json();
      await route.fulfill({ response, json: { ...state, version: '99.0.0' } });
    });

    await expect.poll(() => reloads, { timeout: 10_000 }).toBeGreaterThan(0);
  });
});

test.describe('projects screen', () => {
  test.beforeEach(async ({ page }) => {
    await page.getByRole('link', { name: 'Projects' }).click();
  });

  test('lists the work newest first and opens the newest one', async ({ page }) => {
    await expect(projectTitles(page)).toHaveText([
      'PR 449462: bulk messages sent in batch jobs',
      'Email digest sends each conversation as it goes',
      'Renew the wildcard certificate',
    ]);
    await expect(projects(page).getByRole('heading', { level: 1 })).toHaveText('PR 449462: bulk messages sent in batch jobs');
  });

  test('selecting a project shows its problem and what was done', async ({ page }) => {
    await projects(page).getByRole('button', { name: /Renew the wildcard certificate/ }).click();

    await expect(projects(page).getByRole('heading', { level: 1 })).toHaveText('Renew the wildcard certificate');
    await expect(projects(page).getByText('the local certificate expired')).toBeVisible();
    await expect(projects(page).getByText('issued a new one and replaced the encrypted files')).toBeVisible();
  });

  test('shows each skill used with its current level and how it was used', async ({ page }) => {
    const skills = projects(page).getByRole('list', { name: 'Skills used' }).getByRole('listitem');

    await expect(skills).toHaveCount(2);
    await expect(skills.filter({ hasText: 'idempotency' })).toContainText('learning');
    await expect(skills.filter({ hasText: 'idempotency' })).toContainText('a redelivered batch skips recipients already dispatched');
    await expect(skills.filter({ hasText: 'batching' })).toContainText('getting it');
  });

  test('a skill level follows the ledger on the live refresh', async ({ page, ledger }) => {
    ledger.setStatus('batching', 'solid');

    await expect(projects(page).getByRole('list', { name: 'Skills used' }).getByRole('listitem').filter({ hasText: 'batching' })).toContainText('solid', { timeout: 10_000 });
  });

  test('finds a project by the number of its PR', async ({ page }) => {
    await projects(page).getByRole('searchbox', { name: 'Find a project' }).fill('448805');

    await expect(projectTitles(page)).toHaveText(['Email digest sends each conversation as it goes']);
    await expect(projects(page).getByText('1 of 3 projects shown')).toBeVisible();
  });

  test('the selected project is marked in the list', async ({ page }) => {
    await projects(page).getByRole('button', { name: /Renew the wildcard certificate/ }).click();

    await expect(projects(page).getByRole('button', { name: /Renew the wildcard certificate/ })).toHaveAttribute('aria-current', 'true');
    await expect(projects(page).getByRole('button', { name: /PR 449462/ })).toHaveAttribute('aria-current', 'false');
  });

  test('lists the decisions tied to a PR as collapsed examples with a code block', async ({ page, ledger }) => {
    ledger.addConcepts(conceptWithExamples('retry-safety', ['sent twice (PR 449462)', 'unrelated (PR 450999)']));
    const decisions = projects(page).getByRole('heading', { name: 'Decisions and why (1)' });
    await expect(decisions).toBeVisible({ timeout: 10_000 });
    await expect(projects(page).getByText('what 1')).toBeHidden();

    await projects(page).getByText('sent twice (PR 449462)').click();

    await expect(projects(page).getByText('What it is: what 1')).toBeVisible();
    await expect(projects(page).locator('.code pre')).toHaveText('where 1');
    await expect(projects(page).getByRole('button', { name: 'Copy code locations' })).toBeVisible();
    await expect(projects(page).getByText('unrelated (PR 450999)')).toHaveCount(0);
  });

  test('says tradeoffs are not recorded yet', async ({ page }) => {
    await expect(projects(page).getByText('Not recorded yet.', { exact: false })).toBeVisible();
  });
});

test.describe('recent screen', () => {
  test.beforeEach(async ({ page }) => {
    await page.getByRole('link', { name: 'Recent' }).click();
  });

  test('lists the work newest first', async ({ page }) => {
    await expect(workTitles(page)).toHaveText([
      'PR 449462: bulk messages sent in batch jobs',
      'Email digest sends each conversation as it goes',
      'Renew the wildcard certificate',
    ]);
  });

  test('shows how well each piece of work is understood', async ({ page }) => {
    await expect(workCard(page, 'PR 449462')).toContainText('partly');
    await expect(workCard(page, 'Email digest')).toContainText('understood');
    await expect(workCard(page, 'wildcard certificate')).toContainText('not yet');
  });

  test('shows whether it was built or walked through, and when', async ({ page }) => {
    await expect(workCard(page, 'PR 449462')).toContainText('walked through');
    await expect(workCard(page, 'PR 449462')).toContainText('2026-10-27');
    await expect(workCard(page, 'Email digest')).toContainText('built');
  });

  test('shows the problem and how it was solved', async ({ page }) => {
    await expect(workCard(page, 'PR 449462')).toContainText('a retry of the whole send re-emailed people who already got it');
    await expect(workCard(page, 'PR 449462')).toContainText('the parent job only plans; small batch jobs send and mark recipients dispatched');
  });

  test('shows the concepts involved and how each was used', async ({ page }) => {
    await openWork(page, 'PR 449462');
    const idempotency = workConcept(page, 'PR 449462', 'idempotency');

    await expect(idempotency).toContainText('a redelivered batch skips recipients already dispatched');
    await expect(workConcept(page, 'PR 449462', 'batching')).toContainText('the unit of retry became 50 recipients');
  });

  test('shows what is still unclear', async ({ page }) => {
    await expect(workCard(page, 'PR 449462')).toContainText('what happens when the parent fails while enqueuing batches');
  });

  test('each concept shows its current status from the ledger', async ({ page }) => {
    await openWork(page, 'PR 449462');
    await expect(workConcept(page, 'PR 449462', 'idempotency')).toContainText('learning');
    await expect(workConcept(page, 'PR 449462', 'batching')).toContainText('getting it');
  });

  test('a concept status follows the ledger on the live refresh', async ({ page, ledger }) => {
    await openWork(page, 'PR 449462');
    ledger.setStatus('idempotency', 'solid');

    await expect(workConcept(page, 'PR 449462', 'idempotency')).toContainText('solid', { timeout: 10_000 });
    await expect(workConcept(page, 'PR 449462', 'idempotency')).not.toContainText('learning');
  });

  test('a concept that is not in the ledger says so', async ({ page }) => {
    await openWork(page, 'wildcard certificate');
    await expect(workConcept(page, 'wildcard certificate', 'certificate-chains')).toContainText('not in ledger');
  });

  test('searching a word in the title narrows the list', async ({ page }) => {
    await search(page).fill('certificate');

    await expect(workTitles(page)).toHaveText(['Renew the wildcard certificate']);
  });

  test('searching a word in the solution finds the work', async ({ page }) => {
    await search(page).fill('dispatched');

    await expect(workTitles(page)).toHaveText(['PR 449462: bulk messages sent in batch jobs']);
  });

  test('searching a concept name finds the work that used it', async ({ page }) => {
    await search(page).fill('checkpointing');

    await expect(workTitles(page)).toHaveText(['Email digest sends each conversation as it goes']);
  });

  test('searching by a concept\'s current status finds the work that used a concept in that status', async ({ page }) => {
    await search(page).fill('learning');

    await expect(workTitles(page)).toHaveText(['PR 449462: bulk messages sent in batch jobs']);
  });

  test('searching "not in ledger" finds work that used a concept the ledger lacks', async ({ page }) => {
    await search(page).fill('not in ledger');

    await expect(workTitles(page)).toHaveText(['Renew the wildcard certificate']);
  });

  test('every word of the search must match', async ({ page }) => {
    await search(page).fill('batch dispatched');
    await expect(workTitles(page)).toHaveText(['PR 449462: bulk messages sent in batch jobs']);

    await search(page).fill('batch certificate');
    await expect(workTitles(page)).toHaveCount(0);
  });

  test('the search ignores case', async ({ page }) => {
    await search(page).fill('CERTIFICATE');

    await expect(workTitles(page)).toHaveText(['Renew the wildcard certificate']);
  });

  test('matches are highlighted', async ({ page }) => {
    await search(page).fill('digest');

    await expect(workCard(page, 'Email digest').locator('mark').first()).toHaveText('digest');
  });

  test('a search with no match says so and can be cleared', async ({ page }) => {
    await search(page).fill('zebra');
    await expect(page.getByText('Nothing matches.')).toBeVisible();
    await expect(page.getByText('Showing 0 of 3')).toBeVisible();

    await page.getByRole('button', { name: 'Clear search and filters' }).click();

    await expect(workTitles(page)).toHaveCount(3);
    await expect(search(page)).toHaveValue('');
  });

  test('the understanding filter narrows the list', async ({ page }) => {
    await recent(page).getByRole('button', { name: 'partly', exact: true }).click();

    await expect(workTitles(page)).toHaveText(['PR 449462: bulk messages sent in batch jobs']);
  });

  test('the kind filter narrows the list', async ({ page }) => {
    await recent(page).getByRole('button', { name: 'built', exact: true }).click();

    await expect(workTitles(page)).toHaveText(['Email digest sends each conversation as it goes', 'Renew the wildcard certificate']);
  });

  test('a reviewed piece of work can be filtered by its kind and shows what was missed', async ({ page, ledger }) => {
    ledger.addWork({
      title: 'Review of PR 450001: retry the webhook', kind: 'reviewed', date: '2026-10-28', source: 'PR 450001',
      understanding: 'partly', problem: 'webhooks were dropped on a timeout', solution: 'the PR adds a retry with backoff',
      concepts: [['idempotency', 'the handler must be safe to run twice']], gaps: 'missed that the retry is not capped',
    });

    await recent(page).getByRole('button', { name: 'reviewed', exact: true }).click();

    await expect(workTitles(page)).toHaveText(['Review of PR 450001: retry the webhook']);
    await expect(workCard(page, 'PR 450001')).toContainText('missed that the retry is not capped');
  });

  test('work skipped on override can be filtered and says how to go back to it', async ({ page, ledger }) => {
    ledger.addWork(skippedWork());

    await recent(page).getByRole('button', { name: 'skipped', exact: true }).click();

    await expect(workTitles(page)).toHaveText(['Add the retry cap']);
    await expect(workCard(page, 'Add the retry cap')).toContainText('skipped on override: in a hurry');
    await expect(workCard(page, 'Add the retry cap')).toContainText('help me understand PR 450002');
  });

  test('searching "override" finds the work that was skipped', async ({ page, ledger }) => {
    ledger.addWork(skippedWork());

    await search(page).fill('override');

    await expect(workTitles(page)).toHaveText(['Add the retry cap']);
  });

  test('work that was not skipped has no note about going back to it', async ({ page }) => {
    await expect(workCard(page, 'PR 449462')).not.toContainText('Skipped on override');
  });

  test('a filter and a search combine', async ({ page }) => {
    await recent(page).getByRole('button', { name: 'built', exact: true }).click();
    await search(page).fill('expired');

    await expect(workTitles(page)).toHaveText(['Renew the wildcard certificate']);
  });

  test('the count shows how many of the total are shown', async ({ page }) => {
    await expect(page.getByText('Showing 3 of 3')).toBeVisible();

    await search(page).fill('certificate');

    await expect(page.getByText('Showing 1 of 3')).toBeVisible();
  });

  test('the search text and results survive a live refresh', async ({ page, ledger }) => {
    await search(page).fill('batch');
    await expect(workTitles(page)).toHaveCount(1);

    ledger.setStatus('batching', 'solid');

    await expect(workConcept(page, 'PR 449462', 'batching')).toContainText('solid', { timeout: 10_000 });
    await expect(search(page)).toHaveValue('batch');
    await expect(workTitles(page)).toHaveCount(1);
  });

  test('without a work log it says nothing is recorded yet', async ({ page, ledger }) => {
    ledger.removeWork();

    await expect(page.getByText('No work recorded yet.')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('Showing 0 of 0')).toBeVisible();
  });
});

test.describe('recent screen: collapsing', () => {
  test.beforeEach(async ({ page }) => {
    await page.getByRole('link', { name: 'Recent' }).click();
  });

  test('each piece of work starts collapsed, showing only its title and chips', async ({ page }) => {
    const card = workCard(page, 'PR 449462');

    await expect(card.getByRole('heading', { level: 3 })).toBeVisible();
    await expect(card).toContainText('partly');
    await expect(card.getByText('a retry of the whole send re-emailed people')).toBeHidden();
    await expect(card.getByText('a redelivered batch skips recipients already dispatched')).toBeHidden();
  });

  test('clicking the title opens the details and clicking again closes them', async ({ page }) => {
    const card = workCard(page, 'PR 449462');

    await card.getByRole('heading', { level: 3 }).click();
    await expect(card.getByText('a retry of the whole send re-emailed people')).toBeVisible();
    await expect(card.getByText('what happens when the parent fails while enqueuing batches')).toBeVisible();

    await card.getByRole('heading', { level: 3 }).click();
    await expect(card.getByText('a retry of the whole send re-emailed people')).toBeHidden();
  });

  test('the details open from the keyboard', async ({ page }) => {
    const card = workCard(page, 'PR 449462');

    await card.locator('summary').focus();
    await page.keyboard.press('Enter');

    await expect(card.getByText('a retry of the whole send re-emailed people')).toBeVisible();
  });

  test('Expand all opens every card and Collapse all closes them', async ({ page }) => {
    await page.getByRole('button', { name: 'Expand all' }).click();
    await expect(recent(page).getByText('delete each conversation once its emails are queued')).toBeVisible();
    await expect(recent(page).getByText('issued a new one and replaced the encrypted files')).toBeVisible();

    await page.getByRole('button', { name: 'Collapse all' }).click();
    await expect(recent(page).getByText('delete each conversation once its emails are queued')).toBeHidden();
    await expect(recent(page).getByText('issued a new one and replaced the encrypted files')).toBeHidden();
  });

  test('an open card stays open on the live refresh', async ({ page, ledger }) => {
    const card = workCard(page, 'PR 449462');
    await card.getByRole('heading', { level: 3 }).click();

    ledger.setStatus('idempotency', 'solid');

    await expect(workConcept(page, 'PR 449462', 'idempotency')).toContainText('solid', { timeout: 10_000 });
    await expect(card.getByText('a retry of the whole send re-emailed people')).toBeVisible();
  });

  test('a search opens the cards that match so the match can be seen', async ({ page }) => {
    await search(page).fill('unit of retry');

    await expect(workCard(page, 'PR 449462').getByText('the unit of retry became 50 recipients')).toBeVisible();
  });

  test('clearing the search closes the cards again', async ({ page }) => {
    await search(page).fill('unit of retry');
    await search(page).fill('');

    await expect(workCard(page, 'PR 449462').getByText('the unit of retry became 50 recipients')).toBeHidden();
  });
});

test.describe('recent screen: search across everything', () => {
  test.beforeEach(async ({ page }) => {
    await page.getByRole('link', { name: 'Recent' }).click();
  });

  test('without a search only the work is listed', async ({ page }) => {
    await expect(recent(page).getByRole('heading', { level: 2, name: /^Concepts/ })).toHaveCount(0);
    await expect(recent(page).getByRole('heading', { level: 2, name: /^Activity/ })).toHaveCount(0);
  });

  test('a search finds a concept by what you said in your own words', async ({ page }) => {
    await search(page).fill('checkpointing in my own words');

    await expect(matchedConcepts(page)).toHaveText([/^checkpointing/]);
  });

  test('a search finds a concept by its recall question', async ({ page }) => {
    await search(page).fill('what is lease-with-expiry');

    await expect(matchedConcepts(page)).toHaveText([/^lease-with-expiry/]);
  });

  test('a search finds a concept by the text of one of its examples', async ({ page, ledger }) => {
    ledger.addConcepts(conceptBlock('backpressure', 'new', {}, 'slow producers when the queue is full'));

    await search(page).fill('slow producers');

    await expect(matchedConcepts(page)).toHaveText([/^backpressure/]);
  });

  test('a search finds a concept by how it was applied in a language', async ({ page }) => {
    await search(page).fill('idempotency key header');

    await expect(matchedConcepts(page)).toHaveText([/^idempotency/]);
  });

  test('a concept with no work entry is still found', async ({ page }) => {
    await search(page).fill('failure-isolation');

    await expect(workTitles(page)).toHaveCount(1);
    await expect(matchedConcepts(page)).toHaveText([/^failure-isolation/]);
  });

  test('a matched concept opens to show its details', async ({ page }) => {
    await search(page).fill('lease-with-expiry');

    await expect(matchedConcepts(page).first().getByText('what is lease-with-expiry?')).toBeVisible();
  });

  test('a matched concept lists its published sources as links', async ({ page, ledger }) => {
    const sourceLine = '- source: Timeouts, retries and backoff | https://example.com/retries | guide | checked 2026-11-05\n';
    ledger.addConcepts(conceptBlock('retries-with-backoff', 'learning') + sourceLine);

    await search(page).fill('retries-with-backoff');
    await page.getByRole('button', { name: 'Expand all' }).click();

    const link = matchedConcepts(page).first().getByRole('link', { name: 'Timeouts, retries and backoff' });
    await expect(link).toHaveAttribute('href', 'https://example.com/retries');
    await expect(matchedConcepts(page).first()).toContainText('guide, checked 2026-11-05');
  });

  test('a source that is not a web link is shown as text and not as a link', async ({ page, ledger }) => {
    const sourceLine = '- source: Local notes | javascript:alert(1) | guide | checked 2026-11-05\n';
    ledger.addConcepts(conceptBlock('unsafe-source', 'new') + sourceLine);

    await search(page).fill('unsafe-source');
    await page.getByRole('button', { name: 'Expand all' }).click();

    await expect(matchedConcepts(page).first()).toContainText('Local notes');
    await expect(matchedConcepts(page).first().getByRole('link')).toHaveCount(0);
  });

  test('a search finds an activity event by its note', async ({ page }) => {
    await search(page).fill('lowered one rung');

    await expect(matchedEvents(page)).toHaveCount(1);
    await expect(matchedEvents(page).first()).toContainText('dial-down');
  });

  test('a search finds an activity event for a language', async ({ page }) => {
    await search(page).fill('typescript');

    await expect(matchedEvents(page).first()).toContainText('setting-changed');
  });

  test('a search that only matches a concept does not say nothing matches', async ({ page }) => {
    await search(page).fill('checkpointing in my own words');

    await expect(page.getByText('Nothing matches.')).toHaveCount(0);
    await expect(workTitles(page)).toHaveCount(0);
  });

  test('matches in concepts and activity are highlighted', async ({ page }) => {
    await search(page).fill('lowered');

    await expect(matchedEvents(page).first().locator('mark')).toHaveText('lowered');
  });

  test('the understanding filter does not hide matched concepts', async ({ page }) => {
    await search(page).fill('checkpointing');
    await recent(page).getByRole('button', { name: 'skipped', exact: true }).click();

    await expect(matchedConcepts(page)).toHaveText([/^checkpointing/]);
  });
});

test.describe('settings screen: storage', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/#settings');
  });

  test('starts as local only and offers the folder backend', async ({ page }) => {
    await expect(storageCard(page).getByRole('heading', { name: 'Storage' })).toBeVisible();
    await expect(storageCard(page)).toContainText('Your data is only on this computer');
    await expect(storageCard(page).getByRole('combobox', { name: 'Storage backend' })).toHaveValue('folder');
    await expect(storageCard(page).getByLabel('Folder to keep a copy of your data in')).toBeVisible();
    await expect(storageCard(page).getByRole('button', { name: 'Sync now' })).toBeHidden();
  });

  test('saving a folder switches storage to it', async ({ page, viewerServer }) => {
    const cloud = mkdtempSync(join(tmpdir(), 'understand-first-cloud-'));
    await storageCard(page).getByLabel('Folder to keep a copy of your data in').fill(cloud);
    await storageCard(page).getByRole('button', { name: 'Save and use' }).click();

    await expect(storageCard(page)).toContainText('Your data is copied to folder');
    await expect(storageCard(page).getByRole('button', { name: 'Sync now' })).toBeVisible();
    await expect(storageCard(page).getByRole('button', { name: 'Use local storage only' })).toBeVisible();
    expect(JSON.parse(readFileSync(join(viewerServer.dataDir, 'sync', 'config.json'), 'utf8'))).toEqual({
      backend: 'folder', settings: { directory: cloud },
    });
    rmSync(cloud, { recursive: true, force: true });
  });

  test('a folder that is left empty is refused with the reason and nothing changes', async ({ page, viewerServer }) => {
    await storageCard(page).getByRole('button', { name: 'Save and use' }).click();

    await expect(page.getByText(/Choose the folder/)).toBeVisible();
    await expect(storageCard(page)).toContainText('Your data is only on this computer');
    expect(existsSync(join(viewerServer.dataDir, 'sync', 'config.json'))).toBe(false);
  });

  test('Sync now brings the backend files to this computer', async ({ page, viewerServer }) => {
    const cloud = mkdtempSync(join(tmpdir(), 'understand-first-cloud-'));
    writeFileSync(join(cloud, 'sources-added.md'), 'from the cloud\n');
    await storageCard(page).getByLabel('Folder to keep a copy of your data in').fill(cloud);
    await storageCard(page).getByRole('button', { name: 'Save and use' }).click();
    await storageCard(page).getByRole('button', { name: 'Sync now' }).click();

    await expect.poll(() => textOf(join(viewerServer.dataDir, 'sources-added.md'))).toBe('from the cloud');
    rmSync(cloud, { recursive: true, force: true });
  });

  test('Use local storage only goes back to keeping data on this computer', async ({ page, viewerServer }) => {
    const cloud = mkdtempSync(join(tmpdir(), 'understand-first-cloud-'));
    await storageCard(page).getByLabel('Folder to keep a copy of your data in').fill(cloud);
    await storageCard(page).getByRole('button', { name: 'Save and use' }).click();
    await storageCard(page).getByRole('button', { name: 'Use local storage only' }).click();

    await expect(storageCard(page)).toContainText('Your data is only on this computer');
    expect(existsSync(join(viewerServer.dataDir, 'sync', 'config.json'))).toBe(false);
    rmSync(cloud, { recursive: true, force: true });
  });

  test('storage can be chosen before the first session has created a ledger', async ({ page, viewerServer }) => {
    rmSync(join(viewerServer.dataDir, 'ledger.md'));
    await page.reload();

    await expect(storageCard(page).getByRole('button', { name: 'Save and use' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Settings' }).getByText('No ledger yet.')).toBeVisible();
  });
});

function textOf(path: string): string {
  return existsSync(path) ? readFileSync(path, 'utf8').trim() : '';
}

function storageCard(page: Page): Locator {
  return page.getByRole('region', { name: 'Settings' }).locator('#storage');
}

async function openWork(page: Page, title: string): Promise<void> {
  await workCard(page, title).getByRole('heading', { level: 3 }).click();
}

function matchedConcepts(page: Page): Locator {
  return recent(page).getByRole('list', { name: 'Matching concepts' }).getByRole('listitem');
}

function matchedEvents(page: Page): Locator {
  return recent(page).getByRole('list', { name: 'Matching activity' }).getByRole('listitem');
}

function skippedWork(): SeededWork {
  return {
    title: 'Add the retry cap', kind: 'built', date: '2026-10-28', source: 'PR 450002', understanding: 'skipped',
    problem: 'retries had no limit', solution: 'capped the retries at five',
    concepts: [['backpressure', 'a cap keeps retries from piling up']], gaps: 'skipped on override: in a hurry',
  };
}

function recent(page: Page): Locator {
  return page.getByRole('region', { name: 'Recent' });
}

function search(page: Page): Locator {
  return page.getByRole('searchbox', { name: 'Search recent work' });
}

function workTitles(page: Page): Locator {
  return recent(page).getByRole('heading', { level: 3 });
}

function workCard(page: Page, title: string): Locator {
  return recent(page)
    .getByRole('list', { name: 'Recent work', exact: true })
    .getByRole('listitem')
    .filter({ has: page.getByRole('heading', { name: title }) });
}

function workConcept(page: Page, title: string, concept: string): Locator {
  return workCard(page, title).getByRole('list', { name: /^Concepts used in / }).getByRole('listitem').filter({ hasText: concept });
}

function statsConcepts(page: Page): Locator {
  return page.getByRole('region', { name: 'Stats' }).getByRole('list', { name: / concepts$/ }).getByRole('listitem');
}

async function expandConceptGroups(page: Page): Promise<void> {
  const closedGroups = page.getByRole('region', { name: 'Stats' }).locator('details.fold:not([open]):has([aria-label$=" concepts"]) > summary');
  while ((await closedGroups.count()) > 0) await closedGroups.first().click();
}

function projects(page: Page): Locator {
  return page.getByRole('region', { name: 'Projects' });
}

function projectTitles(page: Page): Locator {
  return projects(page).locator('.project-item .title');
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

function conceptWithExamples(name: string, examples: string[]): string {
  const exampleLines = examples.map((example, index) => {
    const number = index + 1;
    return `  - ${example} | what: what ${number} | where: where ${number} | why: why ${number}`;
  });
  return [`### ${name}`, '- status: new', '- examples:', ...exampleLines, ''].join('\n');
}
function conceptWithSnapshot(name: string): string {
  return [
    `### ${name}`,
    '- status: new',
    '- examples:',
    '  - digest (PR 101) | what: sends | where: the send then the delete | why: safe',
    '    code: services/Notifier.php:41',
    '    > $mail = $this->build($ids);',
    '    > $this->sender->send($mail);',
    '    >> $this->messages->deleteClaimed($ids);',
    '',
  ].join('\n');
}
function conceptWithMixedLanguageExamples(): string {
  return [
    '### retry-safety',
    '- status: learning',
    '- applied in PHP: a dispatched-at column',
    '- applied in TypeScript: an idempotency key',
    '- examples:',
    '  - php sender | what: sends | where: Sender::send | why: skips sent rows',
    '    lang: PHP',
    '    code: src/Sender.inc:10',
    '    >> $this->skipSent($rows);',
    '  - typescript sender | what: sends | where: sendOnce | why: keyed by message id',
    '    lang: typescript',
    '    code: src/sender.ts:3',
    '    >> const key = messageId;',
    '',
  ].join('\n');
}
function conceptBlock(name: string, status: string, applied: Record<string, string> = {}, example = 'something'): string {
  const appliedLines = Object.entries(applied).map(([language, note]) => `- applied in ${language}: ${note}`);
  return [
    `### ${name}`,
    `- status: ${status}`,
    '- last verified: 2026-10-24',
    `- in the learner's words: ${name} in my own words`,
    `- recall question: what is ${name}?`,
    ...appliedLines,
    '- examples:',
    `  - example one (PR 1): ${example}`,
    '',
  ].join('\n');
}

function workBlock(item: SeededWork): string {
  const concepts = item.concepts.map(([name, use]) => `  - ${name}: ${use}`);
  return [
    `### ${item.title}`,
    `- kind: ${item.kind}`,
    `- date: ${item.date}`,
    ...(item.source ? [`- source: ${item.source}`] : []),
    `- understanding: ${item.understanding}`,
    `- problem: ${item.problem}`,
    `- solution: ${item.solution}`,
    '- concepts:',
    ...concepts,
    ...(item.gaps ? [`- gaps: ${item.gaps}`] : []),
    '',
  ].join('\n');
}

function seedData(dataDir: string): void {
  const blocks = SEEDED_CONCEPTS.map(([name, status, applied]) => conceptBlock(name, status, applied)).join('\n');
  writeFileSync(join(dataDir, 'ledger.md'), `${LEDGER_HEAD}${blocks}`);
  writeFileSync(join(dataDir, 'work.md'), SEEDED_WORK.map(workBlock).join('\n'));
  writeFileSync(join(dataDir, 'events.jsonl'), SEEDED_EVENTS.map(event => JSON.stringify(event)).join('\n') + '\n');
}

function listeningPort(dataDir: string): number {
  try {
    return JSON.parse(readFileSync(join(dataDir, 'viewer.pid'), 'utf8')).port;
  } catch {
    return 0;
  }
}
