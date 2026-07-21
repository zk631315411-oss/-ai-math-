// === 通用 API 响应类型 ===

// 标准响应包装 —— 所有 API 返回统一格式
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

// 分页响应 —— 列表查询使用
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
}

// === 知识源引用 ===

export interface Source {
  textbook_id: string;
  textbook_name: string;
  chapter: string;
  snippet: string;
  sequence_id?: string;
  section_node_id?: string;
  kg_used?: boolean;
  kg_concepts?: string[];
  kg_support_concepts?: string[];
  kg_lookahead_concepts?: string[];
  kg_rule_cases_count?: number;
}

// === 聊天消息 ===

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  image?: string; // base64 图片数据
  sources?: Source[];
  knowledge_points?: string[];
  thinking?: string; // AI 思考过程
}

// === 截图裁剪框 ===

export interface CropBBox {
  x: number;
  y: number;
  width: number;
  height: number;
  unit?: 'page_ratio';
}

// === 用户认证 ===

export interface User {
  userId: string;
  username: string;
  token: string | null;
  deviceId: string;
  profile: UserProfile | null;
}

export interface UserProfile {
  id: string;
  username: string;
  grade: string;
  weak_points: string[];
  strong_points: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
}

export interface UserProfileUpdate {
  grade?: string;
  weak_points?: string[];
  strong_points?: string[];
  learning_preferences?: Record<string, any>;
}

// === API 请求类型（补充） ===

// 登录请求
export interface LoginRequest {
  username: string;
  password: string;
}

// 注册请求
export interface RegisterRequest {
  username: string;
  password: string;
  device_id: string;
}

// 教材偏好更新请求
export interface TextbookPreferenceRequest {
  textbook_id: string;
  page_number: number;
}

// 反馈提交请求
export interface FeedbackRequest {
  content: string;
}

// 聊天历史创建请求
export interface ChatHistoryCreateRequest {
  user_id: string;
  question: string;
  answer: string | null;
  page_number: number;
  marker_y_ratio: number;
  marker_type: string;
  thumbnail?: string;
  crop_bbox?: string;
}

// 练习生成请求
export interface ExerciseGenerateRequest {
  user_id: string;
  token?: string;
  textbook_id?: string;
  page_number: number;
}

// 答案提交请求
export interface ExerciseSubmitRequest {
  student_answer: string;
}

// QA 流式问答请求
export interface QASolveStreamRequest {
  user_id: string;
  question: string;
  image_data?: string;
  teaching_mode: string;
  socratic_submode?: string;
  chat_id?: string;
  history?: Array<{ user: string; assistant: string }>;
  token?: string;
  textbook_id?: string;
  page_number?: number;
  marker_id?: string;
  crop_bbox?: CropBBox;
  screenshot_context_id?: string;
}