import { expect, test } from '@playwright/test';

test('desktop creates a branch and restores its inherited path', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop');
  await page.addInitScript(() => localStorage.clear());

  const rootMessages = [
    { id: 'm-user', node_id: 'node-root', sequence_no: 0, role: 'user', content: '根问题：为什么需要线性无关？', status: 'completed' },
    { id: 'm-answer', node_id: 'node-root', sequence_no: 1, role: 'assistant', content: '因为线性无关保证表示的唯一性。', status: 'completed' },
  ];
  const nodes: any[] = [
    { id: 'node-root', tree_id: 'tree-1', parent_node_id: null, fork_message_id: null, title: '根问题', revision: 2, archived_at: null, messages: rootMessages },
    { id: 'node-a', tree_id: 'tree-1', parent_node_id: 'node-root', fork_message_id: 'm-answer', title: '能给一个反例吗？', revision: 1, archived_at: null, messages: [] },
    { id: 'node-b', tree_id: 'tree-1', parent_node_id: 'node-root', fork_message_id: 'm-answer', title: '和基有什么关系？', revision: 1, archived_at: null, messages: [] },
  ];
  let lastActiveNodeId = 'node-root';

  const treeBody = () => ({
    id: 'tree-1', user_id: 'ui-user', root_chat_history_id: 'marker-tree',
    last_active_node_id: lastActiveNodeId, revision: 3, nodes,
  });

  await page.route('**/api/auth/anonymous?*', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ access_token: 'ui-test-token', token_type: 'bearer', user_id: 'ui-user', username: 'anonymous' }),
  }));
  await page.route('**/api/chat/history/**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([{
      id: 'marker-tree', page_number: 1, marker_y_ratio: 24, marker_type: 'text',
      question: '根问题：为什么需要线性无关？', answer: '根回答', follow_ups: '[]',
    }]),
  }));
  await page.route('**/api/chat/trees/by-history/marker-tree**', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(treeBody()),
  }));
  await page.route('**/api/chat/trees/tree-1/active-node', async route => {
    lastActiveNodeId = (await route.request().postDataJSON()).node_id;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(treeBody()) });
  });
  await page.route('**/api/chat/nodes/*/context?*', route => {
    const match = route.request().url().match(/\/nodes\/([^/]+)\/context/);
    const nodeId = match?.[1] || 'node-root';
    const node = nodes.find(candidate => candidate.id === nodeId);
    const context = nodeId === 'node-root' ? rootMessages : [...rootMessages, ...(node?.messages || [])];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(context) });
  });
  await page.route('**/api/qa/solve-stream', async route => {
    const request = await route.request().postDataJSON();
    expect(request.node_id).toBe('node-root');
    expect(request.fork_message_id).toBe('m-answer');
    expect(request.client_turn_id).toBeTruthy();

    const child = {
      id: 'node-new', tree_id: 'tree-1', parent_node_id: 'node-root', fork_message_id: 'm-answer',
      title: request.question, revision: 2, archived_at: null,
      messages: [
        { id: 'm-child-user', node_id: 'node-new', sequence_no: 0, role: 'user', content: request.question, status: 'completed' },
        { id: 'm-child-answer', node_id: 'node-new', sequence_no: 1, role: 'assistant', content: '零向量会让表示不再唯一。', status: 'completed' },
      ],
    };
    nodes.push(child);
    lastActiveNodeId = child.id;
    const turn = {
      turn_id: request.client_turn_id, tree_id: 'tree-1', node_id: child.id,
      parent_node_id: 'node-root', fork_message_id: 'm-answer', title: child.title,
      node_revision: 2, user_message: child.messages[0], assistant_message: child.messages[1],
    };
    const body = [
      'event: tree_turn_started', `data: ${JSON.stringify(turn)}`, '',
      'event: content', `data: ${JSON.stringify({ text: '零向量会让表示不再唯一。' })}`, '',
      'event: done', `data: ${JSON.stringify({ full_text: '零向量会让表示不再唯一。', sources: [], tree_turn: turn })}`, '', '',
    ].join('\n');
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body });
  });

  const openMarker = async () => {
    await page.locator('header select').first().selectOption({ index: 1 });
    await expect(page.locator('.react-pdf__Page')).toBeVisible({ timeout: 90_000 });
    await page.locator('[title*="根问题"]').first().click();
  };

  await page.goto('/');
  await openMarker();

  const fork = page.getByRole('button', { name: '从这条回答创建独立分支' });
  await expect(fork).toBeVisible();
  await fork.click();
  await expect(page.getByText(/正在从.*创建独立分支/)).toBeVisible();
  await page.getByRole('textbox', { name: '输入问题…' }).fill('零向量为什么会破坏线性无关？');
  await page.getByRole('button', { name: '发送' }).click();

  await expect(page.getByText('零向量会让表示不再唯一。')).toBeVisible();
  await expect(page.getByText('因为线性无关保证表示的唯一性。')).toBeVisible();

  await page.reload();
  await openMarker();
  await expect(page.getByText('因为线性无关保证表示的唯一性。')).toBeVisible();
  await expect(page.getByText('零向量为什么会破坏线性无关？')).toBeVisible();
  await expect(page.getByText('零向量会让表示不再唯一。')).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath('follow-up-tree-desktop.png'), fullPage: true });
});
