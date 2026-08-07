"""Compatibility entry point for the legacy prompt assembly API.

New QA flows construct typed tutoring prompts in ``app.services.qa``.  Older
callers still pass the pre-contract keyword arguments, so keep one adapter
instead of maintaining a second prompt implementation.
"""

from app.services.qa.prompt_builder import build_vision_prompt


def build_prompt(
    *,
    question: str,
    page_context: dict | None,
    whitelist: dict | None,
    profile: dict | None,
    teaching_mode: str = "socratic",
    socratic_submode: str = "unclassified",
    history: list[dict] | None = None,
    student_stage: int | None = None,
    prereq_gaps: list[dict] | None = None,
    student_level=None,
    apprenticeship_level=None,
    user_message_for_struggle: str = "",
) -> str:
    """Build a prompt using the current implementation and legacy inputs."""

    prompt = build_vision_prompt(
        question=question,
        page_context=page_context,
        whitelist=whitelist,
        profile=profile,
        teaching_mode=teaching_mode,
        socratic_submode=socratic_submode,
        history=history,
        student_stage=student_stage,
        prereq_gaps=prereq_gaps,
        student_level=student_level,
        apprenticeship_level=apprenticeship_level,
        user_message_for_struggle=user_message_for_struggle,
    )
    if any(gap.get("is_gap") for gap in (prereq_gaps or [])) and "前置知识提醒" not in prompt:
        prompt = "【前置知识提醒】\n" + prompt
    return prompt
