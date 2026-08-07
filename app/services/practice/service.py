"""Textbook-first adaptive practice service.

The service owns the hard boundaries of model-assisted selection.  The model
may choose only from a server-built candidate set; it cannot invent an item,
unlock a successor concept, or declare mastery without matching evidence.
"""

from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.config import config
from app.services.llm_service import llm_service
from app.services.practice import repository as repo
from app.services.practice.quality import parse_json_object
from app.services.practice.worker import practice_worker


SELECTION_USES = {
    "diagnostic", "diagnose", "remedial", "remediation", "verify",
    "validation", "mastery_validation", "advance", "advancement",
}


def _run_sync(coro):
    """Run an async selector for both sync legacy callers and HTTP handlers."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class PracticeService:
    def create_explicit_draft(
        self, *, user_id: str, turn_id: str, node_id: str = "",
        target_concept: str = "", intervention_goal: str = "",
        evidence_quote: str = "",
    ) -> dict:
        context = self._load_turn_context(turn_id, user_id)
        if not context:
            raise ValueError("practice source turn is unavailable")
        return self.create_explicit_draft_from_context(
            user_id=user_id, context=context, node_id=node_id,
            target_concept=target_concept, intervention_goal=intervention_goal,
            evidence_quote=evidence_quote,
        )

    def create_explicit_draft_from_context(
        self, *, user_id: str, context: dict, node_id: str = "",
        target_concept: str = "", intervention_goal: str = "",
        evidence_quote: str = "",
    ) -> dict:
        context = dict(context)
        if node_id and context.get("node_id") and node_id != context["node_id"]:
            raise PermissionError("conversation node mismatch")
        allowed = set(context.get("concept_ids") or []) | set(context.get("concept_names") or [])
        if target_concept:
            if allowed and target_concept not in allowed:
                raise ValueError("target concept is outside the grounded knowledge boundary")
            context["concept_ids"] = [target_concept]
            context["concept_names"] = [target_concept]
        quote = evidence_quote or str(context.get("question") or "")[:160]
        if quote and quote not in str(context.get("question") or ""):
            raise ValueError("evidence quote must quote the student text")
        goal = intervention_goal or "select textbook practice for the current evidence"
        context["intervention_goal"] = goal
        context["evidence_quote"] = quote
        context.setdefault("prompt_version", "practice-textbook-v1")
        draft = repo.create_draft(
            user_id=user_id, context=context, trigger_kind="explicit_request",
            intervention_goal=goal, evidence_quote=quote, auto_prepared=False,
        )
        practice_worker.enqueue(draft["id"])
        return self._public_draft(draft, include_items=False)

    def create_from_intervention(
        self, *, user_id: str, turn_id: str, intervention_action_id: str,
        target_concepts: list[str], intervention_goal: str, evidence_quote: str,
    ) -> dict:
        context = self._load_turn_context(turn_id, user_id)
        if not context:
            raise ValueError("intervention source turn is unavailable")
        allowed = set(context.get("concept_ids") or []) | set(context.get("concept_names") or [])
        selected = [concept for concept in target_concepts if not allowed or concept in allowed]
        if not selected:
            selected = list(context.get("concept_ids") or context.get("concept_names") or [])[:3]
        context["concept_ids"] = selected
        context["concept_names"] = selected
        context["intervention_action_id"] = intervention_action_id
        return self._create_intervention_draft(
            user_id=user_id, context=context, intervention_goal=intervention_goal,
            evidence_quote=evidence_quote,
        )

    def _create_intervention_draft(
        self, *, user_id: str, context: dict, intervention_goal: str,
        evidence_quote: str,
    ) -> dict:
        if evidence_quote and evidence_quote not in str(context.get("question") or ""):
            raise ValueError("evidence quote must quote the student text")
        context = dict(context)
        context["intervention_goal"] = intervention_goal
        context["evidence_quote"] = evidence_quote
        repo.mark_stale_for_context(
            user_id=user_id, tree_id=context.get("tree_id", ""),
            node_id=context.get("node_id", ""),
            concept_ids=context.get("concept_ids", []),
        )
        draft = repo.create_draft(
            user_id=user_id, context=context, trigger_kind="agent_recommended",
            intervention_goal=intervention_goal, evidence_quote=evidence_quote,
            auto_prepared=True,
        )
        practice_worker.enqueue(draft["id"])
        return self._public_draft(draft, include_items=False)

    def get_draft(self, draft_id: str, user_id: str) -> dict | None:
        draft = repo.get_draft(draft_id, user_id)
        return self._public_draft(draft, include_items=True) if draft else None

    def start_session(self, draft_id: str, user_id: str) -> dict:
        return _run_sync(self._start_session_async(draft_id, user_id))

    async def _start_session_async(self, draft_id: str, user_id: str) -> dict:
        draft = repo.get_draft(draft_id, user_id)
        if not draft or draft["status"] not in {"ready", "partial"}:
            raise ValueError("practice draft is not ready")
        items = self._candidate_items(draft, session=None, allow_successors=False)
        if not items:
            raise ValueError("practice draft has no exercise items")
        context = draft.get("context_snapshot") or {}
        selected = await self._model_select(
            phase="initial", candidates=items, context=context, grade=None,
            hint_level=0, current_decision={}, allow_successors=False,
        )
        if selected is None:
            decision = {
                "action": "end_inconclusive", "recommend_end": True,
                "reason": "Selection model failed three times; mastery is inconclusive.",
                "failure_phase": "initial",
            }
            session = repo.create_session(
                draft_id, user_id, None, decision,
                status="inconclusive", outcome_status="inconclusive",
            )
            return {"session": session, "item": None,
                    "selection_reason": decision["reason"],
                    "selection_decision": decision}
        first, decision = selected
        session = repo.create_session(draft_id, user_id, first["id"], decision)
        return {"session": session, "item": self._public_item(first),
                "selection_reason": decision["reason"],
                "selection_decision": decision}

    def request_hint(self, session_id: str, user_id: str) -> dict:
        session = repo.get_session(session_id, user_id)
        if not session or session["status"] != "active" or not session.get("current_item_id"):
            raise ValueError("no active practice item")
        item = repo.get_item(session["current_item_id"])
        if not item:
            raise ValueError("practice item does not exist")
        level = min(3, repo.get_hint_level(session_id, item["id"], user_id) + 1)
        repo.record_hint(session, item, level)
        hints = item.get("hints") or []
        text = hints[min(level, len(hints)) - 1] if hints else "No more hints are available."
        worked_example = None
        if level >= 3:
            item_concepts = set(item.get("concept_ids") or [])
            examples = [
                candidate for candidate in repo.list_draft_items(session["draft_id"], user_id)
                if candidate.get("item_kind") == "worked_example"
                and item_concepts & set(candidate.get("concept_ids") or [])
            ]
            if examples:
                example = examples[0]
                worked_example = {
                    "id": example["id"],
                    "question": example.get("question", ""),
                    "explanation": (example.get("answer_spec") or {}).get("reference", ""),
                    "source_page": example.get("source_page"),
                    "source_problem_no": example.get("source_problem_no"),
                    "source_locator": example.get("source_locator", ""),
                    "review_status": example.get("trust_status", ""),
                }
        return {
            "hint": text,
            "hint_level": level,
            "exhausted": level >= min(3, len(hints) or 3),
            "worked_example": worked_example,
        }

    async def submit_attempt(self, session_id: str, user_id: str, item_id: str, answer: str) -> dict:
        session = repo.get_session(session_id, user_id)
        if not session or session["status"] != "active":
            raise ValueError("practice session is missing or finished")
        if session.get("current_item_id") != item_id:
            raise ValueError("only the current item can be submitted")
        item = repo.get_item(item_id)
        if not item:
            raise ValueError("item does not exist")
        hint_level = repo.get_hint_level(session_id, item_id, user_id)
        grade = await self._grade(item, answer, hint_level)

        if grade["verdict"] == "ungradable":
            retries = int(session.get("ungradable_retries") or 0) + 1
            if retries <= 2:
                reason = "The answer is not gradable; add steps and retry."
                saved = repo.save_attempt(
                    session=session, item=item, answer=answer, grade=grade,
                    hint_level=hint_level, next_item_id=item["id"], next_reason=reason,
                    selection_decision={"action": "retry_same_item", "reason": reason},
                    counts_toward_limit=False, ungradable_retries=retries,
                )
                return {**grade, "hint_level": hint_level, "next_reason": reason,
                        "next_item": self._public_item(item), "session_status": saved["status"],
                        "completed_count": saved["completed_count"], "summary": saved.get("summary", {}),
                        "mastery_note": "This attempt was not gradable and did not consume a question."}
            reason = "Two ungradable attempts; mastery is inconclusive."
            saved = repo.save_attempt(
                session=session, item=item, answer=answer, grade=grade, hint_level=hint_level,
                next_item_id=None, next_reason=reason,
                selection_decision={"action": "end_inconclusive", "reason": reason},
                counts_toward_limit=False, outcome_status="inconclusive",
                ungradable_retries=retries,
            )
            return {**grade, "hint_level": hint_level, "next_reason": reason,
                    "next_item": None, "session_status": "inconclusive",
                    "completed_count": saved["completed_count"], "summary": saved.get("summary", {}),
                    "mastery_note": "This round could not produce a reliable mastery judgment."}

        next_item, next_reason, decision, mastery_verified, outcome_status = (
            await self._select_next_dynamic(session, grade, hint_level)
        )
        saved = repo.save_attempt(
            session=session, item=item, answer=answer, grade=grade, hint_level=hint_level,
            next_item_id=next_item["id"] if next_item else None, next_reason=next_reason,
            selection_decision=decision, mastery_verified=mastery_verified,
            outcome_status=outcome_status,
        )
        asyncio.create_task(self._record_diagnostic(user_id))
        return {**grade, "hint_level": hint_level, "next_reason": next_reason,
                "next_item": self._public_item(next_item) if next_item else None,
                "session_status": saved["status"], "completed_count": saved["completed_count"],
                "summary": saved.get("summary", {}), "selection_decision": decision,
                "mastery_note": self._mastery_note(
                    grade["verdict"], hint_level, saved["status"], mastery_verified,
                )}

    async def _record_diagnostic(self, user_id: str) -> None:
        try:
            from app.services.diagnostic_worker import run_diagnostic_for_user
            await run_diagnostic_for_user(user_id)
        except Exception:
            return

    def regenerate(self, draft_id: str, user_id: str) -> dict:
        draft = repo.get_draft(draft_id, user_id)
        if not draft:
            raise ValueError("practice draft does not exist")
        context = dict(draft["context_snapshot"])
        context["regeneration_nonce"] = int(draft.get("version") or 1) + 1
        replacement = repo.create_draft(
            user_id=user_id, context=context, trigger_kind="explicit_request",
            intervention_goal=draft["intervention_goal"], evidence_quote=draft["evidence_quote"],
            auto_prepared=False, parent_draft_id=draft_id,
        )
        practice_worker.enqueue(replacement["id"])
        return self._public_draft(replacement, include_items=False)

    async def _grade(self, item: dict, answer: str, hint_level: int) -> dict:
        reference = (item.get("answer_spec") or {}).get("reference", "")
        if not llm_service.qa_async:
            return self._fallback_grade(item, answer)
        prompt = ("Grade only demonstrated work. Return JSON with verdict, evidence_quotes, "
                  "rubric_findings, feedback and error_analysis.\n" + json.dumps({
                      "question_type": item.get("question_type"), "question": item.get("question"),
                      "reference": reference, "rubric": item.get("rubric", []),
                      "student_answer": answer, "hint_level": hint_level,
                  }, ensure_ascii=False))
        try:
            raw = await llm_service.chat_qa_async(
                [{"role": "system", "content": "You are an independent university mathematics grader."},
                 {"role": "user", "content": prompt}],
                model=config.EXERCISE_GRADER_MODEL, temperature=0.1,
                response_format={"type": "json_object"},
            )
            value = parse_json_object(raw)
            verdict = value.get("verdict")
            if verdict not in {"correct", "partial", "incorrect", "ungradable"}:
                raise ValueError("invalid verdict")
            return {
                "verdict": verdict,
                "evidence_quotes": [q for q in value.get("evidence_quotes", [])
                                    if isinstance(q, str) and q in answer],
                "rubric_findings": value.get("rubric_findings", [])
                if isinstance(value.get("rubric_findings"), list) else [],
                "feedback": str(value.get("feedback") or ""),
                "error_analysis": value.get("error_analysis", {})
                if isinstance(value.get("error_analysis"), dict) else {},
            }
        except Exception:
            return {"verdict": "ungradable", "evidence_quotes": [answer[:160]] if answer else [],
                    "rubric_findings": [], "feedback": "The grader output was not reliable.",
                    "error_analysis": {"category": "invalid_grader_output"}}

    async def _select_next_dynamic(self, session: dict, grade: dict, hint_level: int):
        draft = repo.get_draft(session["draft_id"], session["user_id"])
        allow_successors = grade.get("verdict") == "correct" and hint_level == 0
        candidates = self._candidate_items(draft, session=session, allow_successors=allow_successors)
        current = session.get("selection_decision") or {}
        current_mastery = self._is_legal_mastery(current, grade, hint_level, draft)
        if current_mastery:
            decision = {**current, "action": "end", "recommend_end": True,
                        "reason": "Independent work on the planned validation item verified the target."}
            return None, decision["reason"], decision, True, "mastery_verified"
        if not candidates or int(session.get("completed_count") or 0) + 1 >= 3:
            decision = {"action": "end", "item_id": current.get("item_id"),
                        "purpose": current.get("purpose", "diagnostic"),
                        "target_concept": current.get("target_concept", ""),
                        "evidence_refs": current.get("evidence_refs", []),
                        "reason": "The round reached its limit or has no legal candidate remaining.",
                        "recommend_end": True}
            return None, decision["reason"], decision, current_mastery, (
                "mastery_verified" if current_mastery else "undetermined"
            )
        selected = await self._model_select(
            phase="rolling", candidates=candidates,
            context=draft.get("context_snapshot") or {}, grade=grade,
            hint_level=hint_level, current_decision=current,
            allow_successors=allow_successors,
        )
        if selected is None:
            decision = {"action": "end_inconclusive", "recommend_end": True,
                        "reason": "Selection model failed three times; mastery is inconclusive."}
            return None, decision["reason"], decision, False, "inconclusive"
        next_item, decision = selected
        if next_item is None:
            return None, decision["reason"], decision, current_mastery, (
                "mastery_verified" if current_mastery else "undetermined"
            )
        decision["mastery_verified"] = False
        return next_item, decision["reason"], decision, current_mastery, "undetermined"

    async def _model_select(
        self, *, phase: str, candidates: list[dict], context: dict,
        grade: dict | None, hint_level: int, current_decision: dict,
        allow_successors: bool,
    ) -> tuple[dict | None, dict] | None:
        metadata = [self._selection_metadata(item) for item in candidates]
        payload = {
            "phase": phase, "student_evidence": context.get("evidence_quote", ""),
            "student_question": context.get("question", ""),
            "intervention_goal": context.get("intervention_goal", ""),
            "student_stage": context.get("student_stage"),
            "target_concepts": context.get("concept_ids", []),
            "prerequisite_concepts": context.get("prerequisite_concept_ids", []),
            "allow_successors": allow_successors, "grade": grade,
            "hint_level": hint_level, "current_decision": current_decision,
            "candidates": metadata,
        }
        messages = [
            {"role": "system", "content": (
                "You select textbook items only from candidates. Return one JSON object with "
                "item_id, purpose, target_concept, evidence_refs, reason, recommend_end, action. "
                "purpose must be diagnostic, remedial, verify, or advance. "
                "action is continue or end. Do not invent IDs or claim mastery."
            )},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        for _ in range(3):
            if not llm_service.qa_async:
                continue
            try:
                raw = await llm_service.chat_qa_async(
                    messages, model=config.EXERCISE_GRADER_MODEL, temperature=0.1,
                    response_format={"type": "json_object"},
                )
                choice = parse_json_object(raw)
                if phase == "rolling" and choice.get("action") == "end":
                    ending = self._validate_end_selection(choice, current_decision)
                    if ending:
                        return None, ending
                normalized = self._validate_selection(
                    choice, candidates, context, phase=phase,
                    allow_successors=allow_successors,
                )
                if normalized:
                    return normalized
            except Exception:
                continue
        return self._deterministic_select(
            candidates, context=context, phase=phase, grade=grade,
            hint_level=hint_level, current_decision=current_decision,
        )

    @staticmethod
    def _validate_end_selection(choice: dict, current_decision: dict) -> dict | None:
        reason = choice.get("reason")
        evidence = choice.get("evidence_refs")
        if not isinstance(reason, str) or not reason.strip():
            return None
        if not isinstance(evidence, list) or any(not isinstance(value, str) for value in evidence):
            return None
        return {
            "action": "end", "item_id": current_decision.get("item_id"),
            "purpose": current_decision.get("purpose", "diagnostic"),
            "target_concept": current_decision.get("target_concept", ""),
            "evidence_refs": evidence, "reason": reason.strip(), "recommend_end": True,
        }

    @staticmethod
    def _selection_metadata(item: dict) -> dict:
        return {
            "id": item["id"], "primary_concept_id": item.get("primary_concept_id", ""),
            "primary_concept_name": item.get("primary_concept_name", ""),
            "concept_ids": item.get("concept_ids", []),
            "prerequisite_concepts": item.get("prerequisite_concept_ids", []),
            "diagnostic_goal": item.get("diagnostic_goal", "application"),
            "difficulty": item.get("difficulty", "basic"), "question_type": item.get("question_type"),
            "source_locator": item.get("source_locator", ""),
        }

    def _validate_selection(self, choice: dict, candidates: list[dict], context: dict,
                            *, phase: str, allow_successors: bool) -> tuple[dict, dict] | None:
        if not isinstance(choice, dict) or choice.get("action") not in {"continue", "end"}:
            return None
        item = next((row for row in candidates if row["id"] == choice.get("item_id")), None)
        if not item or choice.get("action") != "continue":
            return None
        use = str(choice.get("purpose") or choice.get("temporary_use") or choice.get("branch_role") or "").lower()
        if use not in SELECTION_USES:
            return None
        target = choice.get("target_concept")
        item_concepts = set(item.get("concept_ids") or []) | set(item.get("concept_names") or [])
        item_concepts |= {item.get("primary_concept_id", ""), item.get("primary_concept_name", "")}
        if not target or target not in item_concepts:
            return None
        evidence = choice.get("evidence_refs")
        if not isinstance(evidence, list) or any(not isinstance(value, str) for value in evidence):
            return None
        reason = choice.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return None
        decision = {
            "item_id": item["id"], "action": "continue", "purpose": use,
            "target_concept": target,
            "evidence_refs": evidence, "reason": reason.strip(),
            "recommend_end": bool(choice.get("recommend_end", False)),
        }
        return item, decision

    @staticmethod
    def _deterministic_select(candidates: list[dict], *, context: dict, phase: str,
                              grade: dict | None, hint_level: int,
                              current_decision: dict) -> tuple[dict, dict] | None:
        if not candidates:
            return None
        verdict = (grade or {}).get("verdict")
        inferred_goal = PracticeService._infer_diagnostic_goal(context)
        if phase == "initial":
            preferred = [inferred_goal, "definition", "application", "proof", "counterexample", "transfer"]
            reason = "模型选题不可用，已从可信候选中确定性选择诊断题。"
        elif verdict == "incorrect":
            preferred = ["remedial", "definition", "application", "proof"]
            reason = "根据错误作答，已回退到同一知识点的补救题。"
        elif verdict == "partial":
            preferred = ["remedial", "application", "definition", "proof"]
            reason = "根据部分正确作答，已回退到同级巩固题。"
        elif verdict == "correct" and hint_level == 0:
            preferred = ["verify", "advance", "proof", "transfer", "application"]
            reason = "独立答对后，已回退到验证或进阶题。"
        else:
            preferred = ["verify", "application", "definition", "proof"]
            reason = "答案需要提示或证据不足，已回退到同级验证题。"
        rank: dict[str, int] = {}
        for index, goal in enumerate(preferred):
            rank.setdefault(goal, index)
        target = set(context.get("concept_ids") or []) | set(context.get("concept_names") or [])
        item = sorted(
            candidates,
            key=lambda row: (
                0 if target & (set(row.get("concept_ids") or []) | set(row.get("concept_names") or [])) else 1,
                rank.get(row.get("diagnostic_goal", "application"), len(preferred)),
                row.get("source_locator", ""), row.get("id", ""),
            ),
        )[0]
        purpose = "verify" if verdict == "correct" and hint_level == 0 else (
            "remedial" if verdict in {"incorrect", "partial"} else "diagnostic"
        )
        concepts = list(item.get("concept_ids") or item.get("concept_names") or [])
        decision = {
            "item_id": item["id"], "action": "continue", "purpose": purpose,
            "target_concept": concepts[0] if concepts else "",
            "evidence_refs": [context.get("evidence_quote", "")],
            "reason": reason, "recommend_end": False, "fallback": True,
        }
        return item, decision

    @staticmethod
    def _infer_diagnostic_goal(context: dict) -> str:
        text = " ".join(str(context.get(key) or "") for key in (
            "question", "evidence_quote", "intervention_goal",
        ))
        if any(token in text for token in ("反例", "误用", "不一定", "条件")):
            return "counterexample"
        if any(token in text for token in ("证明", "论证", "为什么成立")):
            return "proof"
        if any(token in text for token in ("定义", "概念", "什么意思", "不理解")):
            return "definition"
        if any(token in text for token in ("迁移", "推广", "变式")):
            return "transfer"
        return "application"

    def _candidate_items(self, draft: dict, session: dict | None, *, allow_successors: bool) -> list[dict]:
        user_id = draft["user_id"]
        items = [item for item in repo.list_draft_items(draft["id"], user_id)
                 if item.get("item_kind", "exercise_item") == "exercise_item"
                 and item.get("source", "textbook") == "textbook"
                 and item.get("kg_mapping_status") == "verified"
                 and item.get("review_status") == "approved"
                 and item.get("solution_review_status") in {"reviewed", "teacher_approved"}
                 and item.get("trust_status") in {"teacher_approved", "machine_verified", "machine_reviewed"}
                 and (item.get("trust_status") != "machine_reviewed" or item.get("owner_user_id") == user_id)]
        attempted: set[str] = set()
        if session:
            attempted = repo.get_attempted_item_ids(session["id"], user_id)
            if session.get("current_item_id"):
                attempted.add(session["current_item_id"])
        context = draft.get("context_snapshot") or {}
        current = set(context.get("concept_ids") or []) | set(context.get("concept_names") or [])
        prereqs = set(context.get("prerequisite_concept_ids") or []) | set(context.get("prerequisite_concept_names") or [])
        neighbors = self._kg_neighbor_ids(context, current)
        if not current:
            return [item for item in items if item["id"] not in attempted]
        result = []
        for item in items:
            if item["id"] in attempted:
                continue
            concepts = set(item.get("concept_ids") or []) | set(item.get("concept_names") or [])
            concepts |= {item.get("primary_concept_id", ""), item.get("primary_concept_name", "")}
            if concepts & current or concepts & prereqs:
                result.append(item)
            elif allow_successors and concepts & neighbors:
                result.append(item)
        return result

    @staticmethod
    def _kg_neighbor_ids(context: dict, current: set[str]) -> set[str]:
        explicit = set(context.get("kg_neighbor_ids") or []) | set(context.get("kg_neighbor_names") or [])
        if explicit:
            return explicit
        kg_context = context.get("kg_context") or {}
        relations = kg_context.get("relations", []) if isinstance(kg_context, dict) else []
        if relations:
            neighbors: set[str] = set()
            for relation in relations:
                if not isinstance(relation, dict):
                    continue
                source = relation.get("source_node_id") or relation.get("source_id")
                target = relation.get("target_node_id") or relation.get("target_id")
                if source in current and target:
                    neighbors.add(target)
                if target in current and source:
                    neighbors.add(source)
            if neighbors:
                return neighbors
        try:
            from app.db.kg_v44 import relation_neighbors_for_nodes
            book = context.get("textbook_id", "")
            rows = relation_neighbors_for_nodes(list(current), book, limit=32)
            return {row.get("node_id") for row in rows if row.get("node_id")}
        except Exception:
            return set()

    @staticmethod
    def _is_legal_mastery(decision: dict, grade: dict, hint_level: int, draft: dict) -> bool:
        context = draft.get("context_snapshot") or {}
        main = set(context.get("concept_ids") or []) | set(context.get("concept_names") or [])
        return (
            str(decision.get("purpose", decision.get("temporary_use", ""))).lower() in {"verify", "validation", "mastery_validation"}
            and grade.get("verdict") == "correct" and hint_level == 0
            and bool(main & {decision.get("target_concept", "")})
        )

    @staticmethod
    def _fallback_grade(item: dict, answer: str) -> dict:
        reference = (item.get("answer_spec") or {}).get("reference", "")
        normalized = re.sub(r"\s+", "", answer).lower()
        ref = re.sub(r"\s+", "", reference).lower()
        keywords = [str(value).lower() for value in (item.get("answer_spec") or {}).get("accepted_keywords", []) if str(value).strip()]
        hits = [value for value in keywords if value in answer.lower()]
        if not normalized:
            verdict = "ungradable"
        elif normalized == ref or (len(normalized) >= 8 and normalized in ref):
            verdict = "correct"
        elif keywords and len(hits) == len(keywords):
            verdict = "correct"
        elif hits:
            verdict = "partial"
        else:
            verdict = "incorrect"
        return {"verdict": verdict, "evidence_quotes": [answer[:160]] if answer else [],
                "rubric_findings": [{"keyword": hit, "matched": True} for hit in hits],
                "feedback": "本地演示批改：根据参考答案关键词和量规给出结果。",
                "error_analysis": {"category": "deterministic_fallback", "matched_keywords": hits}}

    def _load_turn_context(self, turn_id: str, user_id: str) -> dict | None:
        from app.db.connection import get_conn
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM qa_turn_records WHERE id=? AND user_id=?", (turn_id, user_id)).fetchone()
            if not row:
                return None
            context = json.loads(row["context_snapshot"] or "{}")
            grounding = context.get("grounding", {})
            related = grounding.get("related_concepts", [])
            return {
                "turn_id": row["id"], "tree_id": context.get("input_context", {}).get("tree_id") or "",
                "node_id": context.get("input_context", {}).get("node_id") or "",
                "textbook_id": row["textbook_id"] or "", "page_number": row["page_number"],
                "sequence_id": row["sequence_id"] or "", "chapter_name": row["chapter_name"] or "",
                "question": row["question"], "history": context.get("history", [])[-3:],
                "concept_ids": [item.get("node_id") or item.get("name") for item in related[:8]],
                "concept_names": [item.get("name") for item in related[:8]],
                "prerequisite_concept_ids": [item.get("node_id") or item.get("name") for item in grounding.get("prerequisite_concepts", [])[:8]],
                "prerequisite_concept_names": [item.get("name") for item in grounding.get("prerequisite_concepts", [])[:8]],
                "page_excerpt": grounding.get("content_excerpt", ""),
                "sources": json.loads(row["sources"] or "[]"),
                "student_stage": context.get("student_state_summary", {}).get("current_section_stage"),
            }
        finally:
            conn.close()

    def _public_draft(self, draft: dict, include_items: bool) -> dict:
        result = {key: draft.get(key) for key in (
            "id", "turn_id", "node_id", "textbook_id", "sequence_id", "concept_ids",
            "trigger_kind", "intervention_goal", "evidence_quote", "selection_reason",
            "status", "auto_prepared", "version", "error",
        )}
        context = draft.get("context_snapshot") or {}
        result["concept_names"] = context.get("concept_names") or []
        result["items"] = []
        if include_items and draft.get("status") in {"ready", "partial"}:
            result["items"] = [self._public_item(item, summary=True)
                                for item in repo.list_draft_items(draft["id"], draft["user_id"])]
        return result

    @staticmethod
    def _public_item(item: dict | None, summary: bool = False) -> dict | None:
        if not item:
            return None
        result = {key: item.get(key) for key in (
            "id", "item_kind", "textbook_id", "source_locator", "sequence_id", "concept_ids", "concept_names",
            "prerequisite_concept_ids", "prerequisite_concept_names", "primary_concept_id", "primary_concept_name",
            "secondary_concept_ids", "question_type", "diagnostic_goal", "difficulty",
            "question", "hints", "source", "trust_status", "stem_source", "solution_source", "solution_review_status",
            "kg_mapping_status", "source_page", "source_problem_no", "source_subitem_no", "branch_role", "reason",
        )}
        if summary:
            result.pop("hints", None)
        return result

    @staticmethod
    def _mastery_note(verdict: str, hint_level: int, status: str, mastery_verified: bool = False) -> str:
        if mastery_verified:
            return "Mastery was verified on an explicitly selected validation item. Long-term Stage still requires accumulated evidence."
        if status != "completed":
            return "This attempt is recorded as evidence; the current round has not confirmed mastery."
        if verdict == "correct" and hint_level == 0:
            return "Independent work was correct, but this round did not explicitly confirm mastery."
        if verdict == "correct":
            return "The answer was correct after a hint; mastery remains unconfirmed."
        return "The current evidence still shows a learning gap; long-term Stage is updated only by Diagnosis V2."


# Compatibility alias retained for older internal tests; it uses the new
# strict selector and therefore never applies the old branch-role fallback.
PracticeService._select_next = PracticeService._select_next_dynamic
practice_service = PracticeService()
