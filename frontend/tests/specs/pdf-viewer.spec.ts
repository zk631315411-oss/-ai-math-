import { expect, test } from '@playwright/test';

const books = [
  { index: 1, pages: 421, renderer: 'canvas' },
  { index: 2, pages: 685, renderer: 'canvas' },
  { index: 3, pages: 284, renderer: 'img' },
  { index: 4, pages: 274, renderer: 'img' },
] as const;

test('desktop loads one anonymous session and renders all textbooks', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop');

  const consoleErrors: string[] = [];
  const badResponses: string[] = [];
  const anonymousStatuses: number[] = [];

  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', error => consoleErrors.push(error.message));
  page.on('response', response => {
    if (response.url().includes('/api/auth/anonymous')) {
      anonymousStatuses.push(response.status());
    }
    if (response.status() >= 400) {
      badResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto('/');
  const textbookSelect = page.locator('header select').first();
  await expect(textbookSelect).toBeVisible();
  await expect.poll(() => anonymousStatuses).toEqual([200]);

  for (const book of books) {
    await textbookSelect.selectOption({ index: book.index });
    const renderedPage = page.locator('.react-pdf__Page');
    await expect(renderedPage).toBeVisible({ timeout: 90_000 });
    await expect(page.getByText(new RegExp(`1\\s*/\\s*${book.pages}`)).first()).toBeVisible();
    await expect(renderedPage.locator(book.renderer)).toBeVisible({ timeout: 90_000 });
  }

  expect(consoleErrors).toEqual([]);
  expect(badResponses).toEqual([]);
});

test('mobile fits the page and keeps zoomed content reachable', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-mobile');

  await page.goto('/');
  await page.locator('header select').first().selectOption({ index: 1 });
  const renderedPage = page.locator('.react-pdf__Page');
  await expect(renderedPage.locator('canvas')).toBeVisible({ timeout: 90_000 });

  const fitMetrics = await renderedPage.evaluate(element => {
    const scroller = element.closest('[data-testid="pdf-scroll-container"]');
    if (!scroller) throw new Error('PDF scroll container not found');
    const pageRect = element.getBoundingClientRect();
    const scrollRect = scroller.getBoundingClientRect();
    return {
      pageLeft: pageRect.left,
      pageRight: pageRect.right,
      scrollLeft: scrollRect.left,
      scrollRight: scrollRect.right,
    };
  });
  expect(fitMetrics.pageLeft).toBeGreaterThanOrEqual(fitMetrics.scrollLeft);
  expect(fitMetrics.pageRight).toBeLessThanOrEqual(fitMetrics.scrollRight);

  const scroller = page.getByTestId('pdf-scroll-container');
  await page.getByTestId('pdf-mobile-toolbar').locator('select').selectOption('1');
  await expect.poll(() => scroller.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);

  const zoomMetrics = await renderedPage.evaluate(element => {
    const scroller = element.closest('[data-testid="pdf-scroll-container"]');
    if (!scroller) throw new Error('PDF scroll container not found');
    const pageRect = element.getBoundingClientRect();
    const scrollRect = scroller.getBoundingClientRect();
    return { pageLeft: pageRect.left, scrollLeft: scrollRect.left };
  });
  expect(zoomMetrics.pageLeft).toBeGreaterThanOrEqual(zoomMetrics.scrollLeft);
});

test('narrow desktop keeps the mobile PDF toolbar pinned while scrolling', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop');
  await page.setViewportSize({ width: 958, height: 1031 });

  await page.goto('/');
  await page.locator('header select').first().selectOption({ index: 1 });
  await expect(page.locator('.react-pdf__Page canvas')).toBeVisible({ timeout: 90_000 });

  const scroller = page.getByTestId('pdf-scroll-container');
  const toolbar = page.getByTestId('pdf-mobile-toolbar');
  await toolbar.locator('select').selectOption('1');
  await expect.poll(() => scroller.evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true);

  const bottomOffset = async () => page.evaluate(() => {
    const scrollElement = document.querySelector('[data-testid="pdf-scroll-container"]');
    const toolbarElement = document.querySelector('[data-testid="pdf-mobile-toolbar"]');
    if (!scrollElement || !toolbarElement) throw new Error('PDF viewport elements are missing');
    const scrollRect = scrollElement.getBoundingClientRect();
    const toolbarRect = toolbarElement.getBoundingClientRect();
    return {
      offset: Math.abs(scrollRect.bottom - toolbarRect.bottom),
      toolbarTop: toolbarRect.top,
      viewportTop: scrollRect.top,
    };
  });

  const before = await bottomOffset();
  expect(before.offset).toBeLessThanOrEqual(1);

  await scroller.evaluate(element => { element.scrollTop = element.scrollHeight / 2; });
  await expect.poll(() => scroller.evaluate(element => element.scrollTop)).toBeGreaterThan(0);

  const after = await bottomOffset();
  expect(after.offset).toBeLessThanOrEqual(1);
  expect(after.toolbarTop).toBeGreaterThan(after.viewportTop);
});

test('exercise feedback and diagnostic cards use authenticated per-user APIs', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop');

  let diagnosticRequest: { url: string; authorization: string } | null = null;
  await page.route('**/api/exercise/by-page?*', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      chapter_name: '线性方程组',
      exercises: [{
        id: 'ui-exercise',
        topic: '线性方程组',
        difficulty: 'basic',
        question: '求线性方程组的通解。',
        hints: ['先确定自由变量。'],
        hint_level: 0,
        is_answered: false,
        grading_status: 'not_submitted',
      }],
    }),
  }));
  await page.route('**/api/exercise/ui-exercise/hint', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ hint: '先确定自由变量。', hint_level: 1, exhausted: false }),
  }));
  await page.route('**/api/exercise/ui-exercise/submit', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      is_correct: false,
      grading_feedback: '批改服务暂时不可用，请重试',
      grading_status: 'failed',
    }),
  }));
  await page.route('**/api/auth/diagnostic-cards?*', route => {
    diagnosticRequest = {
      url: route.request().url(),
      authorization: route.request().headers().authorization || '',
    };
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ cards: [] }),
    });
  });

  await page.goto('/');
  await expect(page.getByRole('button', { name: '画像', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '智能出题' })).toBeVisible();
  await page.getByRole('button', { name: '智能出题' }).click();
  await expect(page.getByText('求线性方程组的通解。')).toBeVisible();

  await page.getByRole('button', { name: '请求提示' }).click();
  await expect(page.getByText('先确定自由变量。', { exact: true })).toBeVisible();

  await page.getByRole('textbox', { name: '输入你的答案…' }).fill('x_1=t+2');
  await page.getByRole('button', { name: '提交答案' }).click();
  await expect(page.getByText('批改失败', { exact: true })).toBeVisible();
  await expect(page.getByText('回答不正确', { exact: true })).toHaveCount(0);

  await page.getByText('智能练习', { exact: true }).locator('..').locator('..').getByRole('button', { name: '×' }).click();
  await page.getByRole('button', { name: '画像', exact: true }).click();
  await page.getByRole('button', { name: '诊断卡片', exact: true }).click();
  await expect(page.getByText('暂无诊断卡片')).toBeVisible();
  expect(diagnosticRequest).not.toBeNull();
  expect(diagnosticRequest!.url).not.toContain('user_id=');
  expect(diagnosticRequest!.authorization).toMatch(/^Bearer /);
});
