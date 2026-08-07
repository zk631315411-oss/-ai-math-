"""Build a practice draft from the reviewed textbook pool only."""

from __future__ import annotations

from app.services.practice.repository import (
    attach_draft_item,
    list_items,
    update_draft,
    update_job,
)


async def build_draft(draft: dict) -> None:
    context = draft["context_snapshot"]
    draft_id = draft["id"]
    concept_ids = [*(context.get("concept_ids") or []), *(context.get("concept_names") or [])]
    items = list_items(
        textbook_id=context.get("textbook_id", ""),
        sequence_id=context.get("sequence_id", ""),
        concept_ids=concept_ids,
        user_id=draft["user_id"],
        include_machine=False,
        limit=12,
    )
    if not items:
        fallback_concepts = [
            *concept_ids,
            *(context.get("prerequisite_concept_ids") or []),
            *(context.get("prerequisite_concept_names") or []),
        ]
        items = list_items(
            textbook_id=context.get("textbook_id", ""),
            sequence_id="",
            concept_ids=fallback_concepts,
            user_id=draft["user_id"],
            include_machine=False,
            limit=12,
        )

    examples = list_items(
        textbook_id=context.get("textbook_id", ""),
        sequence_id=context.get("sequence_id", ""),
        concept_ids=concept_ids,
        user_id=draft["user_id"],
        include_machine=True,
        limit=1,
        item_kind="worked_example",
    )
    if not examples:
        examples = list_items(
            textbook_id=context.get("textbook_id", ""),
            sequence_id="",
            concept_ids=concept_ids,
            user_id=draft["user_id"],
            include_machine=True,
            limit=1,
            item_kind="worked_example",
        )

    for rank, candidate in enumerate(items):
        attach_draft_item(
            draft_id,
            candidate["id"],
            "diagnostic",
            rank,
            "候选题来自已审核教材题池，具体用途由本轮受控选题决定。",
        )
    for rank, example in enumerate(examples, start=len(items)):
        attach_draft_item(
            draft_id,
            example["id"],
            "remedial",
            rank,
            "教材例题仅用于第三级提示后的补救讲解，不计入作答或掌握证据。",
        )
    update_job(
        draft_id,
        "plan",
        status="running",
        result={
            "existing_count": len(items),
            "worked_example_count": len(examples),
            "ai_generation": "disabled_for_mvp",
        },
    )

    from app.services.practice.repository import get_draft_internal

    current = get_draft_internal(draft_id)
    if current and current.get("status") in {"stale", "cancelled"}:
        return
    if items:
        update_draft(
            draft_id,
            status="ready",
            selection_reason=_draft_reason(context, len(items)),
        )
        return
    update_draft(
        draft_id,
        status="failed",
        selection_reason="当前知识点暂时没有已审核的教材题。",
        error="no_qualified_items",
    )


def _draft_reason(context: dict, count: int) -> str:
    concept = (context.get("concept_names") or context.get("concept_ids") or ["当前知识点"])[0]
    return f"根据你在“{concept}”上的学习证据，已匹配 {count} 道教材练习。"
