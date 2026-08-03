import { expect, test } from '@playwright/test';

async function mockAnonymousAuth(page: import('@playwright/test').Page) {
  await page.addInitScript(() => localStorage.clear());
  await page.route('**/api/auth/anonymous?*', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ access_token: 'formula-token', token_type: 'bearer', user_id: 'formula-user', username: 'anonymous' }),
  }));
}

test('chat converts, edits, serializes and renders an inline formula', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop');
  await mockAnonymousAuth(page);
  let sentQuestion = '';

  await page.route('**/api/formula/convert', async route => {
    expect(route.request().headers().authorization).toBe('Bearer formula-token');
    expect((await route.request().postDataJSON()).description).toBe('x趋于0时sin x除以x的极限');
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ latex: '\\lim_{x \\to 0} \\frac{\\sin x}{x}', display_mode: 'inline' }),
    });
  });
  await page.route('**/api/qa/solve-stream', async route => {
    sentQuestion = (await route.request().postDataJSON()).question;
    const body = [
      'event: content', `data: ${JSON.stringify({ text: '已收到公式。' })}`, '',
      'event: done', `data: ${JSON.stringify({ full_text: '已收到公式。', sources: [] })}`, '', '',
    ].join('\n');
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body });
  });

  await page.goto('/');
  const editor = page.getByRole('textbox', { name: '输入问题…' });
  await editor.fill('请解释');
  await page.getByRole('button', { name: '插入公式' }).click();
  const dialog = page.getByRole('dialog', { name: '公式编辑器' });
  await dialog.getByPlaceholder('例如：x趋于0时sin x除以x的极限').fill('x趋于0时sin x除以x的极限');
  await dialog.getByRole('button', { name: '转换' }).click();
  await expect(dialog.locator('math-field')).toHaveJSProperty('value', '\\lim_{x \\to 0} \\frac{\\sin x}{x}');
  await dialog.getByRole('button', { name: '插入', exact: true }).click();

  const formula = page.locator('[data-type="inline-math"]');
  await expect(formula).toBeVisible();
  await formula.click();
  await expect(dialog.getByRole('heading', { name: '编辑公式' })).toBeVisible();
  await dialog.locator('math-field').evaluate((field: Element) => {
    const mathField = field as HTMLElement & { value: string };
    mathField.value = 'x^2+y^2=1';
    mathField.dispatchEvent(new InputEvent('input', { bubbles: true }));
  });
  await dialog.getByRole('button', { name: '更新' }).click();
  await expect(page.locator('[data-type="inline-math"][data-latex="x^2+y^2=1"]')).toBeVisible();

  await page.locator('[data-type="inline-math"][data-latex="x^2+y^2=1"]').click();
  await dialog.getByRole('button', { name: '独立' }).click();
  await dialog.getByRole('button', { name: '更新' }).click();
  await expect(page.locator('[data-type="block-math"][data-latex="x^2+y^2=1"]')).toBeVisible();
  await page.locator('[data-type="block-math"][data-latex="x^2+y^2=1"]').click();
  await dialog.getByRole('button', { name: '行内' }).click();
  await dialog.getByRole('button', { name: '更新' }).click();
  await expect(page.locator('[data-type="inline-math"][data-latex="x^2+y^2=1"]')).toBeVisible();

  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.getByText('已收到公式。')).toBeVisible();
  expect(sentQuestion).toContain('$x^2+y^2=1$');
  await expect(page.locator('.chat-message').filter({ hasText: '请解释' }).locator('.katex')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('formula-chat-desktop.png'), fullPage: true });
});

test('conversion failure preserves description and allows manual matrix insertion', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop');
  await mockAnonymousAuth(page);
  await page.route('**/api/formula/convert', route => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ detail: '公式转换服务暂时不可用' }),
  }));

  await page.goto('/');
  await page.getByRole('button', { name: '插入公式' }).click();
  const dialog = page.getByRole('dialog', { name: '公式编辑器' });
  const description = dialog.getByPlaceholder('例如：x趋于0时sin x除以x的极限');
  await description.fill('二乘二单位矩阵');
  await dialog.getByRole('button', { name: '转换' }).click();
  await expect(dialog.getByRole('alert')).toBeVisible();
  await expect(description).toHaveValue('二乘二单位矩阵');

  await dialog.getByRole('button', { name: '矩阵' }).click();
  const cells = dialog.locator('.matrix-row input');
  await cells.nth(0).fill('1');
  await cells.nth(3).fill('1');
  await dialog.getByRole('button', { name: '插入矩阵' }).click();
  await dialog.getByRole('button', { name: '插入', exact: true }).click();
  await expect(page.locator('[data-type="block-math"]')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('formula-matrix-desktop.png'), fullPage: true });
});

test('mobile formula dialog stays inside the 390 by 844 viewport', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-mobile');
  await mockAnonymousAuth(page);
  await page.goto('/');
  await page.locator('header select').first().selectOption({ index: 1 });
  await page.getByTitle('打开聊天').click();
  await page.getByRole('button', { name: '插入公式' }).click();

  const dialog = page.getByRole('dialog', { name: '公式编辑器' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: '更多符号' }).click();
  const bounds = await dialog.evaluate(element => {
    const rect = element.getBoundingClientRect();
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width };
  });
  expect(bounds.left).toBeGreaterThanOrEqual(0);
  expect(bounds.right).toBeLessThanOrEqual(390);
  expect(bounds.top).toBeGreaterThanOrEqual(0);
  expect(bounds.bottom).toBeLessThanOrEqual(844);
  expect(bounds.width).toBeLessThanOrEqual(390);

  const toolbar = dialog.locator('.formula-toolbar');
  await expect.poll(() => toolbar.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('formula-mobile.png'), fullPage: true });
});
