import type { TokenResponse, UserProfileUpdate, UserProfile } from '../types';
import { request, get, post, put, patch, del } from './request';
import type { AnimationJob, MathVisualizationArtifact } from '../types';

// === 用户认证相关API ===

const anonymousRequests = new Map<string, Promise<TokenResponse>>();

export async function login(username: string, password: string): Promise<TokenResponse> {
  return post<TokenResponse>('/auth/login', { username, password });
}

export async function register(username: string, password: string, deviceId: string): Promise<TokenResponse> {
  return post<TokenResponse>('/auth/register', { username, password, device_id: deviceId });
}

export function anonymousAccess(deviceId: string): Promise<TokenResponse> {
  const pending = anonymousRequests.get(deviceId);
  if (pending) return pending;

  const request = post<TokenResponse>(`/auth/anonymous?device_id=${encodeURIComponent(deviceId)}`);
  const shared = request.finally(() => {
    if (anonymousRequests.get(deviceId) === shared) {
      anonymousRequests.delete(deviceId);
    }
  });
  anonymousRequests.set(deviceId, shared);
  return shared;
}

export async function getCurrentUser(token: string): Promise<UserProfile> {
  return get<UserProfile>('/auth/me', token);
}

export async function updateProfile(token: string, profile: UserProfileUpdate): Promise<UserProfile> {
  return put<UserProfile>('/auth/profile', profile, token);
}

// SSE 流式问答 —— 需要手动处理 Response 流，使用 rawResponse 模式
type CropBBoxPayload = {
  x: number;
  y: number;
  width: number;
  height: number;
  unit?: 'page_ratio';
};

export interface ChatTreeTurn {
  turn_id: string;
  created: boolean;
  tree_id: string;
  node_id: string;
  parent_node_id: string | null;
  fork_message_id: string | null;
  title: string;
  node_revision: number;
  user_message: ChatTreeMessage;
  assistant_message: ChatTreeMessage;
}

export async function fetchWithStage(
  userId: string,
  question: string,
  onStage: (stage: string, text: string) => void,
  imageData?: string,
  teachingMode: string = 'socratic',
  _onThinking?: (text: string) => void,
  textbookId?: string,
  history?: Array<{user: string, assistant: string}>,
  _onIsThinkingChange?: (v: boolean) => void,
  onContent?: (text: string) => void,
  token?: string,
  pageNumber?: number,
  socraticSubmode?: string,
  chatId?: string,
  markerId?: string,
  cropBBox?: CropBBoxPayload | null,
  screenshotContextId?: string | null,
  treeId?: string,
  nodeId?: string,
  forkMessageId?: string,
  clientTurnId?: string,
  onTreeTurnStarted?: (turn: ChatTreeTurn) => void,
  onVisualization?: (artifact: MathVisualizationArtifact) => void,
): Promise<{ answer: string; sources: any[]; thinking: string; screenshot_context_id?: string | null; tree_turn?: ChatTreeTurn; visualizations: MathVisualizationArtifact[]; degraded: boolean; degradation_code?: string }> {
  const payload: any = {
    user_id: userId,
    question,
    image_data: imageData,
    teaching_mode: teachingMode,
  };
  if (socraticSubmode) payload.socratic_submode = socraticSubmode;
  if (chatId) payload.chat_id = chatId;
  if (history) payload.history = history;
  if (token) payload.token = token;
  if (textbookId) payload.textbook_id = textbookId;
  if (pageNumber) payload.page_number = pageNumber;
  if (markerId) payload.marker_id = markerId;
  if (cropBBox) payload.crop_bbox = cropBBox;
  if (screenshotContextId) payload.screenshot_context_id = screenshotContextId;
  if (treeId) payload.tree_id = treeId;
  if (nodeId) payload.node_id = nodeId;
  if (forkMessageId) payload.fork_message_id = forkMessageId;
  if (clientTurnId) payload.client_turn_id = clientTurnId;

  // SSE 流使用 rawResponse 模式，不自动解析响应
  const res = await request<Response>({
    url: '/qa/solve-stream',
    method: 'POST',
    body: payload,
    token,
    rawResponse: true,
    headers: { Accept: 'text/event-stream' },
  });

  const reader = res.body?.getReader();
  if (!reader) throw new Error('无法读取响应流');

  const decoder = new TextDecoder();
  let buffer = '';
  let fullContent = '';
  let sources: any[] = [];
  let thinking = '';
  let screenshotContextIdResult: string | null = null;
  let treeTurn: ChatTreeTurn | undefined;
  let visualizations: MathVisualizationArtifact[] = [];
  let degraded = false;
  let degradationCode: string | undefined;
  let currentEventType: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();

      // 空行代表一个事件结束（按SSE协议）
      if (!trimmed) {
        currentEventType = null;
        continue;
      }

      // 事件类型行
      if (trimmed.startsWith('event:')) {
        currentEventType = trimmed.slice(6).trim();
        continue;
      }

      // 数据行
      if (trimmed.startsWith('data:')) {
        const dataStr = trimmed.slice(5).trim();
        if (!dataStr) continue;

        let data: any;
        try {
          data = JSON.parse(dataStr);
        } catch {
          // SSE 数据行解析失败时跳过该行，不中断流处理
          continue;
        }

        if (data.error && currentEventType === 'error') {
          throw new Error(data.error);
        }

        if (currentEventType === 'tree_turn_started' && data.turn_id) {
          treeTurn = data as ChatTreeTurn;
          onTreeTurnStarted?.(treeTurn);
        }
        // stage事件
        else if (currentEventType === 'stage' && data.stage && data.text) {
          onStage(data.stage, data.text);
        }
        // thinking events are intentionally ignored in the user-facing UI.
        else if (currentEventType === 'thinking' && data.text) {
          continue;
        }
        // content事件 - 流式输出内容
        else if (currentEventType === 'content' && data.text) {
          fullContent += data.text;
          if (onContent) onContent(data.text);
        }
        // 工具状态独立展示，不污染回答正文。
        else if (currentEventType === 'tool_call' && data.name) {
          onStage('tool', data.status_text || `正在${_getToolLabel(data.name)}...`);
        }
        else if (currentEventType === 'tool_result' && data.name) {
          if (data.status === 'error' || data.status === 'skipped' || data.error) {
            onStage('tool', `${_getToolLabel(data.name)}失败，继续组织回答...`);
          } else {
            onStage('tool', `${_getToolLabel(data.name)}完成`);
          }
        }
        else if (currentEventType === 'visualization' && data.id) {
          const artifact = data as MathVisualizationArtifact;
          visualizations = [...visualizations.filter((item) => item.id !== artifact.id), artifact];
          onVisualization?.(artifact);
        }
        // done事件 - 提取sources和thinking
        else if (currentEventType === 'done') {
          if (!fullContent && data.full_text) fullContent = data.full_text;
          if (data.sources) sources = data.sources;
          if (data.screenshot_context_id) screenshotContextIdResult = data.screenshot_context_id;
          if (data.tree_turn) treeTurn = data.tree_turn as ChatTreeTurn;
          if (Array.isArray(data.visualizations)) visualizations = data.visualizations;
          degraded = Boolean(data.degraded);
          if (data.degradation_code) degradationCode = String(data.degradation_code);
        }
      }
    }
  }

  return { answer: fullContent, sources, thinking, screenshot_context_id: screenshotContextIdResult, tree_turn: treeTurn, visualizations, degraded, degradation_code: degradationCode };
}

function _getToolLabel(name: string): string {
  const labels: Record<string, string> = {
    'search_textbook': '查教材',
    'lookup_kg_node': '查知识图谱',
    'verify_math': '验算',
    'create_math_visualization': '生成数学示意图',
  };
  return labels[name] || name;
}


// === 教材偏好API ===

export async function getTextbookPreference(token: string): Promise<{textbook_id: string | null, page_number: number | null}> {
  try {
    return await get<{textbook_id: string | null, page_number: number | null}>('/profile/textbook-preference', token);
  } catch {
    // 获取失败返回默认值，不阻断流程
    return { textbook_id: null, page_number: null };
  }
}

export async function saveTextbookPreference(
  token: string,
  textbookId: string,
  pageNumber: number
): Promise<void> {
  await post('/profile/textbook-preference', { textbook_id: textbookId, page_number: pageNumber }, token);
}

// === 数学画像API ===

export interface MathProfile {
  user_id: string;
  username: string;
  grade: string;
  dimensions: {
    [key: string]: { coverage: number; radius: number; technical: number };
  };
  weak_points: string[];
  latest_diagnostic_report: Record<string, any>;
  last_diagnosed_at: string | null;
  overall_average: number;
}

export interface KnowledgeStats {
  user_id: string;
  stats: Array<{
    topic: string;
    consecutive_turns: number;
    total_asks: number;
    updated_at: string | null;
  }>;
}

export interface DiagnosticHistory {
  user_id: string;
  history: Array<{
    assessment_id: string;
    sequence_id: string;
    dimension_deltas: Array<{ dimension: string; delta: { coverage: number; radius: number; technical: number }; evidence: string }>;
    weak_concepts: string[];
    summary: string;
    created_at: string | null;
  }>;
}

export async function getMathProfile(token: string): Promise<MathProfile> {
  return get<MathProfile>('/auth/math-profile', token);
}

export async function updateMathProfile(token: string, data: Record<string, any>): Promise<MathProfile> {
  return put<MathProfile>('/auth/math-profile', data, token);
}

export async function getKnowledgeStats(token: string): Promise<KnowledgeStats> {
  return get<KnowledgeStats>('/auth/knowledge-stats', token);
}

export async function getDiagnosticHistory(token: string): Promise<DiagnosticHistory> {
  return get<DiagnosticHistory>('/auth/diagnostic-history', token);
}

// === 聊天历史API ===

export async function getChatHistoryByUser(userId: string, page: number, limit: number): Promise<any[]> {
  return get<any[]>(`/chat/history/${encodeURIComponent(userId)}?page=${page}&limit=${limit}`);
}

export async function deleteChatHistory(chatId: string): Promise<void> {
  await del(`/chat/history/${chatId}`);
}

export async function createChatHistory(data: {
  user_id: string;
  question: string;
  answer: string | null;
  page_number: number;
  marker_y_ratio: number;
  marker_type: string;
  thumbnail?: string;
  crop_bbox?: string;
}): Promise<any> {
  return post('/chat/history', data);
}

export async function updateChatHistory(chatId: string, data: Record<string, any>): Promise<void> {
  await patch(`/chat/history/${chatId}`, data);
}

// === 追问历史树 API ===
export interface ChatTreeMessage {
  id: string;
  node_id: string;
  sequence_no: number;
  role: 'user' | 'assistant' | 'tool' | 'system_event';
  content: string;
  status: 'streaming' | 'completed' | 'interrupted' | 'failed';
  visualizations?: MathVisualizationArtifact[];
}

export async function createVisualizationAnimation(
  visualizationId: string,
  userId: string,
  token: string,
): Promise<AnimationJob> {
  return post<AnimationJob>(`/visualizations/${encodeURIComponent(visualizationId)}/animations`, { user_id: userId }, token);
}

export async function getVisualizationAnimation(
  jobId: string,
  userId: string,
  token: string,
): Promise<AnimationJob> {
  return get<AnimationJob>(`/visualizations/animations/${encodeURIComponent(jobId)}?user_id=${encodeURIComponent(userId)}`, token);
}

export async function getVisualization(
  visualizationId: string,
  userId: string,
  token: string,
): Promise<MathVisualizationArtifact> {
  return get<MathVisualizationArtifact>(`/visualizations/${encodeURIComponent(visualizationId)}?user_id=${encodeURIComponent(userId)}`, token);
}
export interface ChatTreeNode {
  id: string;
  tree_id: string;
  parent_node_id: string | null;
  fork_message_id: string | null;
  title: string;
  revision: number;
  archived_at: string | null;
  messages: ChatTreeMessage[];
}
export interface ChatTree {
  id: string;
  user_id: string;
  root_chat_history_id: string | null;
  last_active_node_id: string | null;
  revision: number;
  nodes: ChatTreeNode[];
}
export async function getChatTreeByHistory(historyId: string, userId: string, token?: string): Promise<ChatTree | null> {
  const tree = await get<ChatTree | Record<string, never>>(`/chat/trees/by-history/${encodeURIComponent(historyId)}?user_id=${encodeURIComponent(userId)}`, token);
  return 'id' in tree ? tree as ChatTree : null;
}
export async function ensureChatTreeByHistory(historyId: string, userId: string, token?: string): Promise<ChatTree> {
  return post<ChatTree>(`/chat/trees/from-history/${encodeURIComponent(historyId)}`, { user_id: userId }, token);
}
export async function getChatNodeContext(nodeId: string, userId: string, token?: string): Promise<ChatTreeMessage[]> {
  return get<ChatTreeMessage[]>(`/chat/nodes/${encodeURIComponent(nodeId)}/context?user_id=${encodeURIComponent(userId)}`, token);
}
export async function createChatTree(data: { user_id: string; root_chat_history_id?: string; question: string; answer?: string | null; title?: string }, token?: string): Promise<ChatTree> {
  return post<ChatTree>('/chat/trees', data, token);
}
export async function createChatFork(nodeId: string, data: { user_id: string; fork_message_id: string; question: string; title?: string; expected_revision?: number }, token?: string): Promise<ChatTreeNode> {
  return post<ChatTreeNode>(`/chat/nodes/${encodeURIComponent(nodeId)}/fork`, data, token);
}
export async function appendChatNodeMessage(nodeId: string, data: { user_id: string; role: 'user' | 'assistant' | 'tool' | 'system_event'; content: string; status?: 'streaming' | 'completed' | 'interrupted' | 'failed'; expected_revision?: number }, token?: string): Promise<ChatTreeMessage> {
  return post<ChatTreeMessage>(`/chat/nodes/${encodeURIComponent(nodeId)}/messages`, data, token);
}
export async function activateChatNode(treeId: string, data: { user_id: string; node_id: string; expected_revision?: number }, token?: string): Promise<ChatTree> {
  return patch<ChatTree>(`/chat/trees/${encodeURIComponent(treeId)}/active-node`, data, token);
}

// === 练习API ===

export async function getExercisesByPage(pageNumber: number, userId: string, textbookId: string, token: string): Promise<any[]> {
  const data = await get<{ exercises?: any[] }>(`/exercise/by-page?page_number=${pageNumber}&user_id=${encodeURIComponent(userId)}&textbook_id=${encodeURIComponent(textbookId)}`, token);
  return data.exercises || [];
}

export async function generateExercise(data: {
  user_id: string;
  token?: string;
  textbook_id?: string;
  page_number: number;
}): Promise<Response> {
  // 练习生成是 SSE 流，需要 rawResponse
  return request<Response>({
    url: '/exercise/generate',
    method: 'POST',
    body: data,
    token: data.token,
    rawResponse: true,
  });
}

export async function getExerciseList(userId: string, limit: number, token: string): Promise<any[]> {
  const data = await get<{ exercises?: any[] }>(`/exercise/list?user_id=${encodeURIComponent(userId)}&limit=${limit}`, token);
  return data.exercises || [];
}

export async function getExerciseHint(exerciseId: string, token: string): Promise<{ text: string; level: number; exhausted: boolean }> {
  const data = await post<{ hint: string; hint_level: number; exhausted: boolean }>(`/exercise/${exerciseId}/hint`, undefined, token);
  return { text: data.hint, level: data.hint_level, exhausted: data.exhausted };
}

export async function submitExercise(exerciseId: string, data: { student_answer: string }, token: string): Promise<any> {
  return post(`/exercise/${exerciseId}/submit`, data, token);
}

export interface FormulaConversion {
  latex: string;
  display_mode: 'inline' | 'block';
}

export async function convertFormula(
  description: string,
  preferredDisplay: 'auto' | 'inline' | 'block',
  token: string,
): Promise<FormulaConversion> {
  return post<FormulaConversion>(
    '/formula/convert',
    { description, preferred_display: preferredDisplay },
    token,
    { timeout: 8_000, maxRetries: 0 },
  );
}

export async function reportExerciseError(exerciseId: string, token: string): Promise<void> {
  await post(`/exercise/${exerciseId}/report-error`, undefined, token);
}

// === 反馈API ===

export async function submitFeedback(data: { content: string }): Promise<void> {
  await post('/feedback', data);
}

// === 知识图谱API ===

export async function getKnowledgeGraph(token: string): Promise<any> {
  return get('/auth/knowledge-graph', token);
}

export async function getDiagnosticCards(token: string): Promise<any[]> {
  const data = await get<{ cards?: any[] }>('/auth/diagnostic-cards?limit=20', token);
  return data.cards || [];
}

// === 洞察API ===

export async function getInsight(token: string): Promise<any> {
  return get('/auth/insight', token);
}

export async function regenerateInsight(token: string): Promise<void> {
  await post('/auth/insight/regenerate', undefined, token);
}

// === 徽标迁移API ===

export async function migrateMarkers(oldUserId: string, newUserId: string): Promise<void> {
  await post(`/chat/migrate?old_user_id=${encodeURIComponent(oldUserId)}&new_user_id=${encodeURIComponent(newUserId)}`);
}

// 重新导出 error 模块，方便外部使用
export { ApiError, ErrorType } from './error';
