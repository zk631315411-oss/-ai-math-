from app.main import app
from app.services.diagnosis.contracts import (
    KGContext,
    KGNodeRef,
    StudentStateSummary,
    TutorPolicy,
    TurnGrounding,
)
from app.services.qa.prompt_builder import build_tutor_prompt


def test_current_student_api_contract_is_registered() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/qa/solve-stream",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/insight",
        "/api/auth/insight/regenerate",
        "/api/practice/drafts",
        "/api/practice/drafts/{draft_id}",
        "/api/practice/drafts/{draft_id}/start",
        "/api/practice/drafts/{draft_id}/regenerate",
        "/api/practice/sessions/{session_id}/attempts",
        "/api/practice/sessions/{session_id}/hints",
        "/api/interventions/preferences",
    }
    assert expected <= set(paths)


def test_qa_prompt_uses_current_grounding_and_tutor_policy() -> None:
    grounding = TurnGrounding(
        textbook_id="gaodai_shang",
        page_number=12,
        sequence_id="V1-C03-S02",
        section_node_id="gaodai_shang:C03:S02",
        chapter_name="矩阵秩",
        content_excerpt="矩阵的秩是极大非零子式的阶数。",
        related_concepts=[KGNodeRef(name="矩阵的秩", node_id="rank")],
        kg_context=KGContext(book_id="gaodai_shang", allowed_until="C03"),
    )
    state = StudentStateSummary(
        user_id="student-1",
        current_section_stage=2,
        likely_breakpoint="定义条件",
    )
    policy = TutorPolicy(
        mode="socratic",
        submode="unclassified",
        should_ask_guiding_question=True,
        should_explain_rule_conditions=True,
    )

    prompt = build_tutor_prompt(
        "为什么秩不能超过矩阵的阶数？",
        grounding,
        state,
        policy,
        history=[{"user": "我不理解秩", "assistant": "先看定义"}],
    )

    assert "gaodai_shang" in prompt
    assert "矩阵的秩" in prompt
    assert "为什么秩不能超过矩阵的阶数？" in prompt
    assert "socratic" in prompt
