"""
高等代数用户画像评价体系标准
==================================

本模块定义了数学素养的多维度评价标准，用于诊断用户在高等代数学习中的薄弱环节。

五维度 x 三标尺 = 15个子维度
每个子维度评分范围: 0-3
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================
# 第一部分：五维度定义
# ============================================================

class Dimension(str, Enum):
    """数学素养五维度"""
    MATHEMATICAL_THINKING = "mathematical_thinking"      # 数学思考与抽象思维
    LOGICAL_REASONING = "logical_reasoning"                # 逻辑推理与论证
    SYMBOLIC_OPERATION = "symbolic_operation"              # 符号形式化与算子运算
    MULTI_REPRESENTATION = "multi_representation"          # 多重表征与直观映射
    PROBLEM_SOLVING = "problem_solving"                    # 跨域建模与问题解决


DIMENSION_NAMES: Dict[Dimension, str] = {
    Dimension.MATHEMATICAL_THINKING: "数学思考与抽象思维",
    Dimension.LOGICAL_REASONING: "逻辑推理与论证",
    Dimension.SYMBOLIC_OPERATION: "符号形式化与算器运算",
    Dimension.MULTI_REPRESENTATION: "多重表征与直观映射",
    Dimension.PROBLEM_SOLVING: "跨域建模与问题解决",
}

DIMENSION_DESCRIPTIONS: Dict[Dimension, str] = {
    Dimension.MATHEMATICAL_THINKING: "提出一般性数学问题、区分命题类型，以及进行概念抽象和泛化的能力。例如将三维向量泛化为n维向量空间。",
    Dimension.LOGICAL_REASONING: "分析或产生论证（由推论链接的陈述链）以证明数学主张的能力。例如在线性相关/无关、矩阵秩的推导中逻辑链条是否严密。",
    Dimension.SYMBOLIC_OPERATION: "处理数学符号、符号表达式和转换，以及支配它们的规则和理论框架的能力。例如将特征值翻译为几何直观。",
    Dimension.MULTI_REPRESENTATION: "在广泛表征（语言、符号、图形等）之间进行解释、翻译和移动，并反思性地选择表征的能力。",
    Dimension.PROBLEM_SOLVING: "提出、识别、指定和解决不同种类的数学问题，并制定和实施解题策略的能力。",
}


# ============================================================
# 第二部分：三标尺定义（Rubric）
# ============================================================

class Rubric(str, Enum):
    """评价标尺类型"""
    COVERAGE = "coverage"        # 覆盖度
    RADIUS = "radius"            # 行动半径
    TECHNICAL = "technical"      # 技术层级


RUBRIC_NAMES: Dict[Rubric, str] = {
    Rubric.COVERAGE: "覆盖度",
    Rubric.RADIUS: "行动半径",
    Rubric.TECHNICAL: "技术层级",
}


# 标尺等级定义
RUBRIC_LEVELS: Dict[Rubric, Dict[int, str]] = {
    # 覆盖度 (Degree of Coverage)
    Rubric.COVERAGE: {
        0: "缺失 - 完全无法激活该素养",
        1: "单一 - 仅能执行接受性面（如只能看懂别人的证明，不能自己写）",
        2: "局部 - 能执行建构性面，但缺失对结果的反思与评估能力",
        3: "完整 - 能独立建构，并能批判性地分析自身和他人运用该素养的过程",
    },
    # 行动半径 (Radius of Action)
    Rubric.RADIUS: {
        0: "固着 - 无法在当前特定题目中激活素养",
        1: "标准情境 - 只能在课本例题或高度熟悉的标准题型中激活素养",
        2: "变式情境 - 能够在条件发生部分改变的变式题目中激活素养",
        3: "迁移情境 - 能够在跨学科、极端陌生或未见过的复杂情境中成功激活素养",
    },
    # 技术层级 (Technical Level)
    Rubric.TECHNICAL: {
        0: "基础崩溃 - 使用了错误或严重低级的概念",
        1: "初级技术 - 使用了正确但最繁琐、最基础的计算或推演方法",
        2: "中级技术 - 能熟练调用定理和一般性结构技巧进行解题",
        3: "高级技术 - 能运用高度抽象的算子思维、降维打击或最底层的公理化技巧",
    },
}


# ============================================================
# 第三部分：数据结构定义
# ============================================================

class DimensionScore(BaseModel):
    """单个维度的评分"""
    coverage: int = Field(ge=0, le=3, description="覆盖度 0-3")
    radius: int = Field(ge=0, le=3, description="行动半径 0-3")
    technical: int = Field(ge=0, le=3, description="技术层级 0-3")


class MathProfile(BaseModel):
    """完整数学画像"""
    user_id: str

    # 五维度评分
    mathematical_thinking: DimensionScore = Field(default_factory=lambda: DimensionScore(coverage=0, radius=0, technical=0))
    logical_reasoning: DimensionScore = Field(default_factory=lambda: DimensionScore(coverage=0, radius=0, technical=0))
    symbolic_operation: DimensionScore = Field(default_factory=lambda: DimensionScore(coverage=0, radius=0, technical=0))
    multi_representation: DimensionScore = Field(default_factory=lambda: DimensionScore(coverage=0, radius=0, technical=0))
    problem_solving: DimensionScore = Field(default_factory=lambda: DimensionScore(coverage=0, radius=0, technical=0))

    # 元数据
    grade: Optional[str] = None  # 年级
    weak_points: List[str] = Field(default_factory=list)  # 具体薄弱知识点列表
    updated_at: Optional[str] = None


    def get_dimension(self, dimension: Dimension) -> DimensionScore:
        """获取指定维度的评分"""
        return getattr(self, dimension.value)

    def set_dimension(self, dimension: Dimension, score: DimensionScore):
        """设置指定维度的评分"""
        setattr(self, dimension.value, score)

    def get_average_score(self, dimension: Dimension) -> float:
        """获取指定维度的平均分"""
        ds = self.get_dimension(dimension)
        return (ds.coverage + ds.radius + ds.technical) / 3.0

    def get_overall_average(self) -> float:
        """获取所有维度的总体平均分"""
        total = 0.0
        for dim in Dimension:
            total += self.get_average_score(dim)
        return total / 5.0

    def is_weak_dimension(self, dimension: Dimension, threshold: float = 1.5) -> bool:
        """判断是否为薄弱维度（平均分低于阈值）"""
        return self.get_average_score(dimension) < threshold

    def get_weak_dimensions(self, threshold: float = 1.5) -> List[Dimension]:
        """获取所有薄弱维度"""
        return [dim for dim in Dimension if self.is_weak_dimension(dim, threshold)]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "grade": self.grade,
            "weak_points": self.weak_points,
            "dimensions": {
                dim.value: {
                    "coverage": getattr(self, dim.value).coverage,
                    "radius": getattr(self, dim.value).radius,
                    "technical": getattr(self, dim.value).technical,
                    "average": self.get_average_score(dim),
                }
                for dim in Dimension
            },
            "overall_average": self.get_overall_average(),
            "weak_dimensions": [dim.value for dim in self.get_weak_dimensions()],
        }


# ============================================================
# 第四部分：LLM评估提示词模板
# ============================================================

MATH_PROFILE_SYSTEM_PROMPT = """你是一位高等代数教学专家，负责评估学生的数学素养水平。

你需要根据学生的回答，从以下五个维度进行评估，每个维度使用三个标尺打分（每项0-3分）：

【五维度定义】
1. 数学思考与抽象思维 (Mathematical Thinking & Abstraction)
   - 提出一般性数学问题、区分命题类型，以及进行概念抽象和泛化的能力
   - 例如：将三维向量泛化为n维向量空间，识别命题类型

2. 逻辑推理与论证 (Logical Reasoning & Proof)
   - 分析或产生论证（由推论链接的陈述链）以证明数学主张
   - 例如：在线性相关/无关、矩阵秩的推导中逻辑链条是否严密

3. 符号形式化与算子运算 (Symbols, Formalism & Operations)
   - 处理数学符号、符号表达式和转换，以及支配它们的规则
   - 例如：将特征值翻译为几何直观，根据文字描述写出代数矩阵

4. 多重表征与直观映射 (Multiple Representations & Intuition)
   - 在广泛表征（语言、符号、图形等）之间进行解释、翻译和移动
   - 例如：代数与几何之间的自由切换

5. 跨域建模与问题解决 (Modelling & Problem Handling)
   - 提出、识别、指定和解决不同种类的数学问题
   - 例如：面对非标准题型时的切入能力和宏观解题规划

【三标尺打分标准】（每个维度都要打3个分）

覆盖度 (Coverage) - 衡量掌握该素养各个方面的程度：
- 0分：缺失 - 完全无法激活该素养
- 1分：单一 - 仅能执行接受性面（如只能看懂别人的证明，不能自己写）
- 2分：局部 - 能执行建构性面，但缺失对结果的反思与评估能力
- 3分：完整 - 能独立建构，并能批判性地分析自身和他人运用该素养的过程

行动半径 (Radius) - 衡量能成功激活该素养的情境范围：
- 0分：固着 - 无法在当前特定题目中激活素养
- 1分：标准情境 - 只能在课本例题或高度熟悉的标准题型中激活
- 2分：变式情境 - 能够在条件发生部分改变的变式题目中激活
- 3分：迁移情境 - 能够在跨学科、极端陌生或未见过的复杂情境中激活

技术层级 (Technical) - 衡量所运用数学概念的复杂程度与精密化程度：
- 0分：基础崩溃 - 使用了错误或严重低级的概念
- 1分：初级技术 - 使用正确但最繁琐、最基础的计算或推演方法
- 2分：中级技术 - 能熟练调用定理和一般性结构技巧进行解题
- 3分：高级技术 - 能运用高度抽象的算子思维、降维打击或公理化技巧

请严格按照JSON格式输出评估结果。"""


MATH_PROFILE_OUTPUT_FORMAT = """
输出格式（必须严格遵循）：
{
    "mathematical_thinking": {"coverage": 0-3, "radius": 0-3, "technical": 0-3},
    "logical_reasoning": {"coverage": 0-3, "radius": 0-3, "technical": 0-3},
    "symbolic_operation": {"coverage": 0-3, "radius": 0-3, "technical": 0-3},
    "multi_representation": {"coverage": 0-3, "radius": 0-3, "technical": 0-3},
    "problem_solving": {"coverage": 0-3, "radius": 0-3, "technical": 0-3},
    "weak_points": ["具体指出薄弱的知识点1", "知识点2", ...],
    "reasoning": "简要说明评估理由（50字以内）"
}
"""


# ============================================================
# 第五部分：数据库Schema定义
# ============================================================

DB_SCHEMA = """
-- 数学素养画像表（替代原有的user_profiles表）
CREATE TABLE math_profiles (
    user_id TEXT PRIMARY KEY,
    grade TEXT,
    -- 维度1：数学思考与抽象思维
    mt_coverage INTEGER DEFAULT 0,
    mt_radius INTEGER DEFAULT 0,
    mt_technical INTEGER DEFAULT 0,
    -- 维度2：逻辑推理与论证
    lr_coverage INTEGER DEFAULT 0,
    lr_radius INTEGER DEFAULT 0,
    lr_technical INTEGER DEFAULT 0,
    -- 维度3：符号形式化与算子运算
    so_coverage INTEGER DEFAULT 0,
    so_radius INTEGER DEFAULT 0,
    so_technical INTEGER DEFAULT 0,
    -- 维度4：多重表征与直观映射
    mr_coverage INTEGER DEFAULT 0,
    mr_radius INTEGER DEFAULT 0,
    mr_technical INTEGER DEFAULT 0,
    -- 维度5：跨域建模与问题解决
    ps_coverage INTEGER DEFAULT 0,
    ps_radius INTEGER DEFAULT 0,
    ps_technical INTEGER DEFAULT 0,
    -- 薄弱知识点列表（JSON数组）
    weak_points TEXT DEFAULT '[]',
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 提问历史扩展表（记录每次提问的维度评分）
CREATE TABLE question_assessments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    -- 各维度评分
    mt_coverage INTEGER, mt_radius INTEGER, mt_technical INTEGER,
    lr_coverage INTEGER, lr_radius INTEGER, lr_technical INTEGER,
    so_coverage INTEGER, so_radius INTEGER, so_technical INTEGER,
    mr_coverage INTEGER, mr_radius INTEGER, mr_technical INTEGER,
    ps_coverage INTEGER, ps_radius INTEGER, ps_technical INTEGER,
    -- 总体评分
    overall_score REAL,
    -- 薄弱点列表
    weak_points TEXT,
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_qa_user ON question_assessments(user_id);
CREATE INDEX idx_qa_question ON question_assessments(question_id);
"""


# ============================================================
# 第六部分：LLM结构化诊断系统
# ============================================================

# Legacy compatibility only. Diagnosis V2 uses four source-specific prompts in
# app.services.diagnosis.scorers and never writes this mixed output to profiles.
DIAGNOSTIC_SYSTEM_PROMPT = """你是一位高等代数教学评估专家。请分析以下对话记录，判断学生在各维度的表现变化。

【输入信息】
1. 当前章节 sequence_id：{sequence_id}
2. 该章节涉及的核心概念：{concepts}
3. 最近对话记录：
{chat_history}

【五维度 Rubrics】
- lr（逻辑推理）：是否能识别证明中的充分/必要条件？能否写出规范的数学证明步骤？
- mt（数学抽象）：能否识别代数结构并抽象为一般形式？
- mr（多重表征）：能否在行列式定义与矩阵形式/几何意义之间切换表征？
- so（符号运算）：算子操作是否准确？是否跳步或符号乱飞？
- ps（问题解决）：能否将问题转化为已知模型？解题策略是否多样？

【Delta 评分规则】（每个维度输出增量变化，不是绝对分）
- delta.coverage: +1=展现了覆盖意识，0=无变化，-1=存在概念混淆
- delta.radius: +1=能举一反三，0=无变化，-1=局限在例题本身
- delta.technical: +1=证明步骤规范，0=无变化，-1=跳步或逻辑跳跃
- evidence: 必须引用对话原话，说明判断依据

【概念掌握度估计】
分析对话中实际涉及的概念，估计掌握阶段（0-5 整数）：
  0=首次接触  1=听过但不理解  2=能复述定义
  3=标准题会做  4=能分析变式  5=能综合迁移

【严格约束：概念选择规则】
1. `concept_ids` 和 `concept_stages[].name` 必须从上方的「该章节涉及的核心概念」列表中逐字复制，**一字不改**。
2. 禁止润色、简写、添加后缀、使用同义词或自行发明。
3. 错误示例：列表里有"线性无关"，你写成"线性无关定义"或"线性无关性"——**不允许**。
4. 正确示例：列表里有"线性无关"，你复制"线性无关"。
5. 如果概念不在列表中，**不要输出**。
6. 必须引用对话原文作为 evidence。
7. 信息不足的概念不要输出。

【输出格式】（严格JSON）
{{
    "dimension_deltas": [
        {{
            "dimension": "lr",
            "delta": {{"coverage": 0, "radius": -1, "technical": 0}},
            "evidence": "用户在第3轮问'为什么行列式要按某行展开'（表现：对展开定理的适用边界存在混淆）"
        }}
    ],
    "weak_concepts": ["行列式展开定理", "矩阵秩的几何意义"],
    "summary": "学生在逻辑推理维度存在轻微后退，建议加强必要条件与充分条件的区分训练",
    "concept_stages": [
        {{"name": "行列式展开定理", "stage": 1, "evidence": "连续两轮追问展开定理的适用条件，对前提假设不清晰"}}
    ]
}}
"""


DIAGNOSTIC_OUTPUT_FORMAT = """
输出格式（必须严格遵循此Schema）：
{
    "dimension_deltas": [
        {
            "dimension": "lr",
            "delta": {"coverage": 0, "radius": -1, "technical": 0},
            "evidence": "引用对话原话（必须）"
        }
    ],
    "weak_concepts": ["薄弱概念列表"],
    "summary": "总体评价（100字内）",
    "concept_stages": [
        {"name": "概念名", "stage": 2, "evidence": "对话原文依据"}
    ]
}
"""


def build_diagnostic_prompt(sequence_id: str, concepts: list, chat_history: list, recent_chats: list = None) -> str:
    """构建诊断Prompt（Evidence-based Delta 格式）"""
    history_text = "\n".join([
        f"- Q: {h.get('question', '')} | A: {h.get('answer', '')}..."
        for h in chat_history
    ]) if chat_history else "（无对话记录）"

    concepts_text = "、".join(concepts) if concepts else "（无概念信息）"

    return DIAGNOSTIC_SYSTEM_PROMPT.format(
        sequence_id=sequence_id,
        concepts=concepts_text,
        chat_history=history_text
    )
