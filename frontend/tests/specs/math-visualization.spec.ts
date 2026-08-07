import { expect, test } from '@playwright/test';

test('renders a streamed math visualization and requests its animation', async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.clear());

  const isMobile = testInfo.project.name === 'chromium-mobile';
  const functionArtifact = {
    id: 'viz-sin', version: 1, kind: 'function_2d', title: '正弦函数',
    animation_available: true, animation_status: 'not_requested',
    spec: {
      domain: { min: -3.14, max: 3.14 },
      series: [{
        id: 'curve-1', label: 'y = sin(x)', color: '#2563eb', expression: 'sin(x)',
        points: [
          { x: -3.14, y: 0 }, { x: -1.57, y: -1 }, { x: 0, y: 0 },
          { x: 1.57, y: 1 }, { x: 3.14, y: 0 },
        ],
      }],
    },
  };
  const linearArtifact = {
    id: 'viz-linear', version: 1, kind: 'linear_transform_2d', title: '剪切矩阵变换',
    animation_available: true, animation_status: 'not_requested',
    spec: {
      matrix: [[1, 1], [0, 1]],
      vectors: [{ id: 'vector-1', label: 'v', color: '#2563eb', x: 1, y: 2, transformed: { x: 3, y: 2 } }],
    },
  };
  const artifact = isMobile ? linearArtifact : functionArtifact;

  const rootMessages = [
    { id: 'm-user', node_id: 'node-root', sequence_no: 0, role: 'user', content: '画出正弦函数', status: 'completed' },
    { id: 'm-answer', node_id: 'node-root', sequence_no: 1, role: 'assistant', content: '', status: 'streaming' },
  ];
  const tree = {
    id: 'tree-viz', user_id: 'ui-user', root_chat_history_id: 'marker-viz', last_active_node_id: 'node-root', revision: 1,
    nodes: [{ id: 'node-root', tree_id: 'tree-viz', parent_node_id: null, fork_message_id: null, title: '正弦函数', revision: 1, archived_at: null, messages: rootMessages }],
  };

  await page.route('**/api/auth/anonymous?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ access_token: 'ui-token', token_type: 'bearer', user_id: 'ui-user', username: 'anonymous' }) }));
  await page.route('**/api/chat/history/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }));
  await page.route('**/api/chat/history', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'marker-viz' }) }));
  await page.route('**/api/chat/trees', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(tree) }));
  await page.route('**/api/chat/history/marker-viz', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) }));
  await page.route('**/api/qa/solve-stream', async route => {
    const request = await route.request().postDataJSON();
    const turn = {
      turn_id: request.client_turn_id, created: true, tree_id: 'tree-viz', node_id: 'node-root', parent_node_id: null,
      fork_message_id: null, title: '正弦函数', node_revision: 2,
      user_message: { ...rootMessages[0], turn_id: request.client_turn_id },
      assistant_message: { ...rootMessages[1], turn_id: request.client_turn_id, status: 'completed', content: '正弦函数呈周期变化。', visualizations: [artifact] },
    };
    const body = [
      'event: tree_turn_started', `data: ${JSON.stringify(turn)}`, '',
      'event: tool_call', `data: ${JSON.stringify({ name: 'create_math_visualization' })}`, '',
      'event: visualization', `data: ${JSON.stringify(artifact)}`, '',
      'event: content', `data: ${JSON.stringify({ text: '正弦函数呈周期变化。' })}`, '',
      'event: done', `data: ${JSON.stringify({ full_text: '正弦函数呈周期变化。', sources: [], tree_turn: turn, visualizations: [artifact] })}`, '', '',
    ].join('\n');
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body });
  });

  await page.route(`**/api/visualizations/${artifact.id}/animations`, route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ id: 'job-1', visualization_id: artifact.id, status: 'queued' }),
  }));
  await page.route('**/api/visualizations/animations/job-1?*', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ id: 'job-1', visualization_id: artifact.id, status: 'completed', video_url: '/test-animation.mp4', poster_url: null }),
  }));

  await page.goto('/');
  if (isMobile) {
    await page.locator('header select').first().selectOption({ index: 1 });
    await page.getByTitle('打开聊天').click();
  }
  await page.getByPlaceholder('输入问题... (Enter 发送)').fill(isMobile ? '画出剪切矩阵变换' : '请画出 y=sin(x)');
  await page.getByRole('button', { name: '发送' }).click();

  await expect(page.getByText('正弦函数呈周期变化。')).toBeVisible();
  await expect(page.getByRole('heading', { name: artifact.title })).toBeVisible();
  await expect(page.locator('.js-plotly-plot .main-svg').first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole('button', { name: '生成动画' }).click();
  await expect(page.locator('video')).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: testInfo.outputPath(`math-visualization-${testInfo.project.name}.png`), fullPage: true });
});
