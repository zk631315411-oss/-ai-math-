"""四级认知学徒脚手架控制器 + 苏格拉底子模式偏移 + 防抖。

内部自动调节 Modeling → Coaching → Scaffolding → Fading，
不由学生手动选择。子模式提供倾向偏移量。
"""

from dataclasses import dataclass, field
from enum import Enum


class ApprenticeshipLevel(Enum):
    MODELING = "modeling"
    COACHING = "coaching"
    SCAFFOLDING = "scaffolding"
    FADING = "fading"


class StudentLevel(Enum):
    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


# stage → (ApprenticeshipLevel, 混合描述)
STAGE_TO_LEVEL = {
    None: ApprenticeshipLevel.MODELING,  # 未测定 → 保守示范
    0: ApprenticeshipLevel.MODELING,
    1: ApprenticeshipLevel.MODELING,     # 示范为主，1 级偏示范+辅导
    2: ApprenticeshipLevel.COACHING,
    3: ApprenticeshipLevel.SCAFFOLDING,
    4: ApprenticeshipLevel.SCAFFOLDING,  # 支架为主，4 级偏支架+撤除
    5: ApprenticeshipLevel.FADING,
}

# 子模式偏移量（负 = 向 Modeling/示范，正 = 向 Fading/撤除）
# Levels: [MODELING(0), COACHING(1), SCAFFOLDING(2), FADING(3)]
SUBMODE_OFFSET = {
    "preview": -1,           # 偏示范/辅导
    "exam_review": 0,
    "connected_review": 1,   # 偏支架/撤除
    "unclassified": 0,
}

# 层级 → Prompt 教学规则段
LEVEL_PROMPT_SEGMENT = {
    ApprenticeshipLevel.MODELING: (
        "- 给出完整解题过程，每一步都解释原理。\n"
        "- 用出声思考的方式展示你是如何想到这个解法的。"
    ),
    ApprenticeshipLevel.COACHING: (
        "- 先让学生尝试。如果学生卡住，给具体提示。\n"
        "- 如果学生犯错，先指出哪一步错了再让学生自己修正。"
    ),
    ApprenticeshipLevel.SCAFFOLDING: (
        "- 给出解题框架（步骤大纲），让学生补全中间计算。\n"
        "- 只给必要的公式提示，不给完整过程。"
    ),
    ApprenticeshipLevel.FADING: (
        "- 只提引导性问题。\n"
        "- 例如：'这个条件让你想到哪个定理？''有没有考虑过另一种做法？'\n"
        "- 不要给答案，让学生自己走到最后。"
    ),
}

# 认知感知段（基于 stage）
COGNITION_SEGMENT = {
    "stage_null_or_0_1": "\n学生对该知识点的认知处于入门阶段。请用类比和图形化方式建立直观理解，然后再进入抽象定义。",
    "stage_2_3": "\n学生已能理解和应用该知识点。请在此基础上推进到分析和多解比较。",
    "stage_4_5": "\n学生已能分析该知识点。请提供挑战性推广问题，鼓励综合运用。",
}

# 学生水平 → Prompt 角色前缀
STUDENT_LEVEL_PREFIX = {
    StudentLevel.NOVICE: "你是一位细致耐心的数学讲师。",
    StudentLevel.INTERMEDIATE: "你是一位数学讲师。",
    StudentLevel.ADVANCED: "你是一位数学讲师，请给出高效解法。",
}

# 零延迟关键词检测
STRUGGLE_KEYWORDS = [
    "我错了", "算错了", "做错了", "算不出来", "搞不懂",
    "搞不清楚", "分不清", "不对", "我怎么", "总是错",
]

STRUGGLE_HINT = (
    "\n学生表示遇到了困难，请降低引导力度并先找出问题所在。"
)


@dataclass
class SessionState:
    """每个 Session 的防抖状态。"""
    consecutive_errors: int = 0
    last_level: ApprenticeshipLevel = ApprenticeshipLevel.COACHING


@dataclass
class StudentState:
    current_stage: int | None
    prereq_gaps: list = field(default_factory=list)
    strong_dims: list = field(default_factory=list)
    weak_dims: list = field(default_factory=list)
    apprenticeship_level: ApprenticeshipLevel = ApprenticeshipLevel.COACHING
    student_level: StudentLevel = StudentLevel.INTERMEDIATE


class ScaffoldingController:
    """根据 student state + submode + session 决定学徒层级和 Prompt 段。"""

    def determine_level(
        self,
        stage: int | None,
        submode: str = "unclassified",
        session: SessionState | None = None,
    ) -> ApprenticeshipLevel:
        base = STAGE_TO_LEVEL.get(stage, ApprenticeshipLevel.MODELING)
        offset = SUBMODE_OFFSET.get(submode, 0)

        levels = list(ApprenticeshipLevel)
        idx = levels.index(base) + offset
        idx = max(0, min(len(levels) - 1, idx))
        level = levels[idx]

        # 防抖：连续两次错误才降级
        if session and session.consecutive_errors >= 2:
            prev_idx = levels.index(session.last_level)
            if idx > prev_idx:
                idx = prev_idx + 1  # 只降一级
                idx = max(0, min(len(levels) - 1, idx))
                level = levels[idx]

        if session:
            session.last_level = level

        return level

    def get_prompt_segment(self, level: ApprenticeshipLevel) -> str:
        return LEVEL_PROMPT_SEGMENT.get(level, LEVEL_PROMPT_SEGMENT[ApprenticeshipLevel.COACHING])

    def get_cognition_segment(self, stage: int | None) -> str:
        if stage is None or stage <= 1:
            return COGNITION_SEGMENT["stage_null_or_0_1"]
        elif stage <= 3:
            return COGNITION_SEGMENT["stage_2_3"]
        else:
            return COGNITION_SEGMENT["stage_4_5"]

    def classify_student_level(self, profile_average: float) -> StudentLevel:
        if profile_average < 1.0:
            return StudentLevel.NOVICE
        elif profile_average < 2.0:
            return StudentLevel.INTERMEDIATE
        else:
            return StudentLevel.ADVANCED

    def get_role_prefix(self, student_level: StudentLevel, teaching_mode: str) -> str:
        if teaching_mode == "direct":
            return STUDENT_LEVEL_PREFIX.get(student_level, STUDENT_LEVEL_PREFIX[StudentLevel.INTERMEDIATE])
        return "你是一位博学的数学家，擅长用苏格拉底式提问法引导用户思考。"

    def detect_struggle(self, user_message: str) -> bool:
        return any(kw in user_message for kw in STRUGGLE_KEYWORDS)


# 单例
scaffolding_controller = ScaffoldingController()
