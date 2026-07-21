"""认知诊断模块。

这里放运行时代码。`app/modules/cognitive_diagnosis` 只作为兼容桥接层逐步保留。
"""

from app.services.diagnosis.diagnosis_service import (
    extract_dimension_scores,
    get_concepts_by_sequence_id,
    get_prerequisite_chain,
    get_user_recent_chats,
    run_diagnostic_pipeline,
    should_trigger_diagnostic,
    trigger_diagnostic_if_needed,
)

__all__ = [
    "extract_dimension_scores",
    "get_concepts_by_sequence_id",
    "get_prerequisite_chain",
    "get_user_recent_chats",
    "run_diagnostic_pipeline",
    "should_trigger_diagnostic",
    "trigger_diagnostic_if_needed",
]
