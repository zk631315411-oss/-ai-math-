import { expect, test } from '@playwright/test';

const draft = {
  id: 'draft-mvp-1',
  turn_id: 'turn-mvp-1',
  node_id: 'node-mvp-1',
  textbook_id: 'gaodai_shang',
  concept_ids: ['matrix-rank'],
  concept_names: ['矩阵的秩'],
  status: 'ready',
  trigger_kind: 'automatic',
  intervention_goal: '辨析秩与子矩阵之间的关系',
  evidence_quote: '我不明白为什么秩等于 r 就一定有 r 阶非零子式',
  selection_reason: '检测到对子矩阵证明条件的混淆，推荐用教材原题验证。',
  auto_prepared: true,
  version: 1,
};

const items = [
  {
    id: 'mvp-rank-1', item_kind: 'exercise_item', textbook_id: 'gaodai_shang',
    source_page: 112, source_problem_no: '4.2-6', source_subitem_no: '1',
    source_locator: '第112页 习题4.2-6(1)', concept_ids: ['matrix-rank'], concept_names: ['矩阵的秩'],
    primary_concept_id: 'matrix-rank', primary_concept_name: '矩阵的秩', diagnostic_goal: 'proof',
    difficulty: 'medium', question_type: 'proof', question: '设矩阵 A 的秩为 r，说明 A 至少有一个 r 阶子式不为零。',
    hints: ['从矩阵秩的定义出发。', '寻找最高阶非零子式。', '把定义中的“最高阶”与 r 对应。'],
    source: 'textbook', trust_status: 'teacher_approved', solution_review_status: 'teacher_approved', kg_mapping_status: 'verified',
  },
  {
    id: 'mvp-rank-2', item_kind: 'exercise_item', textbook_id: 'gaodai_shang',
    source_page: 113, source_problem_no: '4.2-7', source_locator: '第113页 习题4.2-7',
    concept_ids: ['matrix-rank'], concept_names: ['矩阵的秩'], primary_concept_id: 'matrix-rank', primary_concept_name: '矩阵的秩',
    diagnostic_goal: 'application', difficulty: 'medium', question_type: 'calculation', question: '求给定矩阵的秩，并写出判断过程。',
    hints: ['先做初等行变换。', '化为阶梯形。', '非零行数就是秩。'], source: 'textbook', trust_status: 'teacher_approved',
    solution_review_status: 'teacher_approved', kg_mapping_status: 'verified',
  },
  {
    id: 'mvp-rank-3', item_kind: 'exercise_item', textbook_id: 'gaodai_shang',
    source_page: 114, source_problem_no: '4.2-9', source_locator: '第114页 习题4.2-9',
    concept_ids: ['matrix-rank'], concept_names: ['矩阵的秩'], primary_concept_id: 'matrix-rank', primary_concept_name: '矩阵的秩',
    diagnostic_goal: 'proof', difficulty: 'medium', question_type: 'proof', question: '证明初等行变换不改变矩阵的秩。',
    hints: ['比较变换前后的行空间。', '初等矩阵是可逆的。', '利用可逆左乘保持秩。'], source: 'textbook',
    trust_status: 'teacher_approved', solution_review_status: 'teacher_approved', kg_mapping_status: 'verified',
  },
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
    sessionStorage.clear();
    localStorage.setItem('auth_token', 'mvp-ui-token');
    localStorage.setItem('textbook_preference', JSON.stringify({ textbookId: 'gaodai_shang' }));
  });

  await page.route('**/api/auth/me', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ id: 'mvp-user', username: '演示学生', grade: '大学一年级', weak_points: [], strong_points: [] }),
  }));
  await page.route('**/api/profile/textbook-preference', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: route.request().method() === 'GET' ? JSON.stringify({ textbook_id: 'gaodai_shang', page_number: 1 }) : '{}',
  }));
  await page.route('**/api/interventions/preferences', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ auto_prepare_practice: true }),
  }));
  await page.route('**/api/interventions/turns/**', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ terminal: true, actions: [] }),
  }));
  await page.route('**/api/chat/history/**', route => route.fulfill({
    status: 200, contentType: 'application/json', body: '[]',
  }));
  await page.route('**/api/chat/history', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'history-mvp-1' }),
  }));
  await page.route('**/api/chat/trees', async route => {
    const body = await route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      id: 'tree-mvp-1', user_id: 'mvp-user', root_chat_history_id: 'history-mvp-1',
      last_active_node_id: 'node-mvp-1', revision: 1,
      nodes: [{
        id: 'node-mvp-1', tree_id: 'tree-mvp-1', parent_node_id: null, fork_message_id: null,
        title: body.question, revision: 1, archived_at: null,
        messages: [{ id: 'tree-user-1', node_id: 'node-mvp-1', sequence_no: 0, role: 'user', content: body.question, status: 'completed' }],
      }],
    }) });
  });
  await page.route('**/api/qa/solve-stream', route => {
    const sse = [
      'event: content', `data: ${JSON.stringify({ text: '关键是区分“存在一个非零子式”和“所有子式都非零”。' })}`, '',
      'event: practice_draft', `data: ${JSON.stringify(draft)}`, '',
      'event: done', `data: ${JSON.stringify({ full_text: '关键是区分“存在一个非零子式”和“所有子式都非零”。', sources: [], qa_turn_id: 'turn-mvp-1' })}`, '', '',
    ].join('\n');
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body: sse });
  });
  await page.route('**/api/practice/drafts/draft-mvp-1', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(draft),
  }));
  await page.route('**/api/practice/drafts/draft-mvp-1/start', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({
      session: { id: 'session-mvp-1', status: 'active', completed_count: 0 }, item: items[0],
      selection_decision: { purpose: 'diagnostic', reason: '验证学生能否正确使用秩的定义。' },
    }),
  }));
  await page.route('**/api/practice/sessions/session-mvp-1/hints', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ hint_level: 1, hint: items[0].hints[0], exhausted: false }),
  }));

  let attempt = 0;
  await page.route('**/api/practice/sessions/session-mvp-1/attempts', route => {
    attempt += 1;
    const responses = [
      {
        verdict: 'partial', feedback: '已经指出秩与非零子式有关，但还缺少“最高阶”的论证。',
        evidence_quotes: ['秩为 r，所以有非零子式'], error_analysis: { category: '定义条件不完整' },
        next_reason: '先用计算题巩固最高阶非零子式与秩的对应。', next_item: items[1], session_status: 'active', completed_count: 1,
        selection_decision: { purpose: 'remedial', reason: '部分正确后选择同知识点的方法应用题。' },
      },
      {
        verdict: 'incorrect', feedback: '行变换过程遗漏了主元，秩的判断不成立。',
        evidence_quotes: ['秩等于 1'], error_analysis: { category: '行变换错误' },
        next_reason: '用证明题检查能否解释行变换为何保持秩。', next_item: items[2], session_status: 'active', completed_count: 2,
        selection_decision: { purpose: 'verify', reason: '错误后回到同一知识点验证核心关系。' },
      },
      {
        verdict: 'correct', feedback: '证明完整，能够用可逆变换说明秩保持不变。', evidence_quotes: ['初等矩阵可逆'], error_analysis: {},
        next_reason: '三题训练结束。', next_item: null, session_status: 'completed', completed_count: 3,
        mastery_note: '本轮包含提示依赖，掌握尚未确认；作答证据已回流诊断系统。',
        summary: { verdict_counts: { correct: 1, partial: 1, incorrect: 1 }, hints_used: 1 },
      },
    ];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(responses[attempt - 1]) });
  });
});

test('MVP recommendation and three-question training fit desktop and mobile', async ({ page }, testInfo) => {
  await page.goto('/');
  if (testInfo.project.name === 'chromium-mobile') {
    await page.getByTitle('打开聊天').click();
  }

  await page.getByRole('textbox', { name: '输入问题…' }).fill('为什么秩为 r 就有 r 阶非零子式？');
  await page.getByRole('button', { name: '发送' }).click();

  await expect(page.getByText('检测到对子矩阵证明条件的混淆')).toBeVisible();
  await expect(page.getByText('已审核')).toBeVisible();
  await page.getByRole('button', { name: '开始练习' }).click();
  await expect(page.getByText('第 1 / 3 题')).toBeVisible();
  await expect(page.getByText(/教材第 112 页/)).toBeVisible();

  await page.getByRole('button', { name: '查看提示' }).click();
  await expect(page.getByText('提示 1/3')).toBeVisible();
  await page.getByPlaceholder('写下答案、计算过程或证明步骤').fill('秩为 r，所以有非零子式。');
  await page.getByRole('button', { name: '提交答案' }).click();
  await expect(page.getByText('上题结果：部分正确')).toBeVisible();

  await page.getByPlaceholder('写下答案、计算过程或证明步骤').fill('我算得秩等于 1。');
  await page.getByRole('button', { name: '提交答案' }).click();
  await expect(page.getByText('上题结果：错误')).toBeVisible();

  await page.getByPlaceholder('写下答案、计算过程或证明步骤').fill('初等行变换等于左乘可逆初等矩阵，因此秩不变。');
  await page.getByRole('button', { name: '提交答案' }).click();
  await expect(page.getByText('本轮练习完成')).toBeVisible();
  await expect(page.getByText('掌握尚未确认')).toBeVisible();
  const summary = page.getByText('本轮练习完成').locator('..');
  await expect(summary).toContainText('正确');
  await expect(summary).toContainText('部分正确');
  await expect(summary).toContainText('错误');
  await expect(summary).toContainText('使用提示');

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath(`practice-mvp-${testInfo.project.name}.png`), fullPage: true });
});
