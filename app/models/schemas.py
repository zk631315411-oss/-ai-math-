from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class Section(BaseModel):
    id: str
    title: str
    content: str


class Chapter(BaseModel):
    id: str
    title: str
    sections: List[Section]


class Textbook(BaseModel):
    id: str
    name: str
    subject: str
    grade: str
    chapters: List[Chapter]
    created_at: datetime


class TextbookCreate(BaseModel):
    name: str
    subject: str
    grade: str


class TextbookResponse(BaseModel):
    id: str
    name: str
    subject: str
    grade: str
    chapter_count: int
    created_at: datetime


class QARequest(BaseModel):
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    token: Optional[str] = None  # JWT token（优先使用）
    question: str
    image_data: Optional[str] = None
    teaching_mode: Optional[str] = "socratic"  # "socratic" 或 "direct"
    socratic_submode: Optional[str] = "unclassified"  # "preview"|"exam_review"|"connected_review"|"unclassified"
    chat_id: Optional[str] = None  # Phase 2: 关联 chat_history 记录（标记更新用）
    marker_id: Optional[str] = None  # 前端页码徽标/对话线程 ID（只读上下文绑定）
    page_id: Optional[str] = None  # 兼容前端可能传入的页码徽标 ID 命名
    textbook_id: Optional[str] = "高代上-丘维声"  # 教材ID，默认上册
    page_number: Optional[int] = None  # PDF物理页码（用于获取章节上下文）
    history: Optional[List[dict]] = None  # 对话历史 [{"user": "...", "assistant": "..."}]
    crop_bbox: Optional[dict] = None  # 截图区域在 PDF 页面中的相对坐标
    screenshot_context_id: Optional[str] = None  # 已缓存的截图上下文 ID


class QAResponse(BaseModel):
    steps: List[str]
    knowledge_points: List[str]
    related_exercises: List[str]


# === 用户认证相关模型 ===

class UserRegister(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_一-鿿]+$')
    password: str = Field(..., min_length=1, max_length=128)
    device_id: str


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserProfileUpdate(BaseModel):
    grade: Optional[str] = None
    weak_points: Optional[List[str]] = None
    strong_points: Optional[List[str]] = None
    learning_preferences: Optional[dict] = None


class UserProfileResponse(BaseModel):
    id: str
    username: str
    grade: Optional[str] = ""
    weak_points: List[str] = []
    strong_points: List[str] = []
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


# === 数学素养画像模型（多维度评价体系）===


class MathProfileUpdate(BaseModel):
    """数学素养画像更新"""
    grade: Optional[str] = None
    # 维度1：数学思考与抽象思维
    mt_coverage: Optional[int] = Field(None, ge=0, le=3)
    mt_radius: Optional[int] = Field(None, ge=0, le=3)
    mt_technical: Optional[int] = Field(None, ge=0, le=3)
    # 维度2：逻辑推理与论证
    lr_coverage: Optional[int] = Field(None, ge=0, le=3)
    lr_radius: Optional[int] = Field(None, ge=0, le=3)
    lr_technical: Optional[int] = Field(None, ge=0, le=3)
    # 维度3：符号形式化与算子运算
    so_coverage: Optional[int] = Field(None, ge=0, le=3)
    so_radius: Optional[int] = Field(None, ge=0, le=3)
    so_technical: Optional[int] = Field(None, ge=0, le=3)
    # 维度4：多重表征与直观映射
    mr_coverage: Optional[int] = Field(None, ge=0, le=3)
    mr_radius: Optional[int] = Field(None, ge=0, le=3)
    mr_technical: Optional[int] = Field(None, ge=0, le=3)
    # 维度5：跨域建模与问题解决
    ps_coverage: Optional[int] = Field(None, ge=0, le=3)
    ps_radius: Optional[int] = Field(None, ge=0, le=3)
    ps_technical: Optional[int] = Field(None, ge=0, le=3)
    # 薄弱知识点
    weak_points: Optional[List[str]] = None


class MathProfileResponse(BaseModel):
    """数学素养画像响应"""
    user_id: str
    username: str
    grade: str = ""
    dimensions: dict = {}
    weak_points: List[str] = []
    latest_diagnostic_report: dict = {}
    last_diagnosed_at: Optional[str] = None
    overall_average: float = 0.0
    created_at: Optional[datetime] = None


# === LLM结构化诊断相关模型 ===

class KnowledgeStatsItem(BaseModel):
    """知识点统计项"""
    topic: str
    consecutive_turns: int = 0
    total_asks: int = 0
    updated_at: Optional[str] = None


class KnowledgeStatsResponse(BaseModel):
    """知识点统计响应"""
    user_id: str
    stats: List[KnowledgeStatsItem]


class DiagnosticHistoryItem(BaseModel):
    """诊断历史记录项"""
    assessment_id: str
    sequence_id: str
    dimension_deltas: List[dict]
    weak_concepts: List[str]
    summary: str
    created_at: Optional[str] = None


class DiagnosticHistoryResponse(BaseModel):
    """诊断历史响应"""
    user_id: str
    history: List[DiagnosticHistoryItem]


# === Phase 2: 智能出题相关模型 ===

class ExerciseGenerateRequest(BaseModel):
    user_id: str
    token: Optional[str] = None
    topic: Optional[str] = None
    textbook_id: Optional[str] = None
    page_number: Optional[int] = None


class ExerciseSubmitRequest(BaseModel):
    student_answer: str


class ExerciseSubmitResponse(BaseModel):
    is_correct: bool
    grading_feedback: str
    grading_status: str = "completed"
    already_submitted: bool = False
    error_analysis: Optional[dict] = None


class ExerciseHintResponse(BaseModel):
    hint: str
    hint_level: int
    exhausted: bool = False
