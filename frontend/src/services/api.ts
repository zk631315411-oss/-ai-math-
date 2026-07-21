import type { TokenResponse, UserProfileUpdate, UserProfile } from '../types';
import { request, get, post, put, patch, del } from './request';

// === 用户认证相关API ===

export async function login(username: string, password: string): Promise<TokenResponse> {
  return post<TokenResponse>('/auth/login', { username, password });
}

export async function register(username: string, password: string, deviceId: string): Promise<TokenResponse> {
  return post<TokenResponse>('/auth/register', { username, password, device_id: deviceId });
}

export async function anonymousAccess(deviceId: string): Promise<TokenResponse> {
  return post<TokenResponse>(`/auth/anonymous?device_id=${encodeURIComponent(deviceId)}`);
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
): Promise<{ answer: string; sources: any[]; thinking: string; screenshot_context_id?: string | null }> {
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

        if (data.error) {
          throw new Error(data.error);
        }

        // stage事件
        if (currentEventType === 'stage' && data.stage && data.text) {
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
        // done事件 - 提取sources和thinking
        else if (currentEventType === 'done') {
          if (!fullContent && data.full_text) fullContent = data.full_text;
          if (data.sources) sources = data.sources;
          if (data.screenshot_context_id) screenshotContextIdResult = data.screenshot_context_id;
        }
      }
    }
  }

  return { answer: fullContent, sources, thinking, screenshot_context_id: screenshotContextIdResult };
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

// === 练习API ===

export async function getExercisesByPage(pageNumber: number, userId: string, textbookId: string): Promise<any[]> {
  const data = await get<{ exercises?: any[] }>(`/exercise/by-page?page_number=${pageNumber}&user_id=${encodeURIComponent(userId)}&textbook_id=${encodeURIComponent(textbookId)}`);
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
    rawResponse: true,
  });
}

export async function getExerciseList(userId: string, limit: number): Promise<any[]> {
  const data = await get<{ exercises?: any[] }>(`/exercise/list?user_id=${encodeURIComponent(userId)}&limit=${limit}`);
  return data.exercises || [];
}

export async function getExerciseHint(exerciseId: string): Promise<any> {
  return post(`/exercise/${exerciseId}/hint`);
}

export async function submitExercise(exerciseId: string, data: { student_answer: string }): Promise<any> {
  return post(`/exercise/${exerciseId}/submit`, data);
}

export async function reportExerciseError(exerciseId: string): Promise<void> {
  await post(`/exercise/${exerciseId}/report-error`);
}

// === 反馈API ===

export async function submitFeedback(data: { content: string }): Promise<void> {
  await post('/feedback', data);
}

// === 知识图谱API ===

export async function getKnowledgeGraph(token: string): Promise<any> {
  return get('/auth/knowledge-graph', token);
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