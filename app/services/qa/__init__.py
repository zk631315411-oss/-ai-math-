"""QA 回答模块。"""

from app.services.qa.answer_service import answer_turn
from app.services.qa.contracts import QAAnswerResult, QAStreamEvent, QATurnContext, QATurnInput, QATurnRecord
from app.services.qa.grounding_service import ground_text_turn
from app.services.qa.prompt_builder import build_tutor_prompt
from app.services.qa.turn_store import save_turn_record
from app.services.qa.tutor_policy import decide_tutor_policy
from app.services.qa.vision_context_service import has_screenshot_context

__all__ = [
    "QAAnswerResult",
    "QAStreamEvent",
    "QATurnContext",
    "QATurnInput",
    "QATurnRecord",
    "answer_turn",
    "build_tutor_prompt",
    "decide_tutor_policy",
    "ground_text_turn",
    "has_screenshot_context",
    "save_turn_record",
]
