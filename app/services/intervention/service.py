"""Rules-first teaching-policy controller."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from app.config import config
from app.services.diagnosis.contracts import StudentStateSummary, TutorPolicy
from app.services.intervention import repository as repo
from app.services.intervention.state import load_student_state
from app.services.practice.quality import parse_json_object
from app.services.qa.tutor_policy import decide_tutor_policy


PROMPT_VERSION = "teaching-controller-v1"
ALLOWED_ACTIONS = {"no_action", "adjust_qa", "offer_practice_entry", "prepare_practice"}
QA_POLICY_FIELDS = {
    "should_review_prerequisites", "should_ask_guiding_question",
    "should_explain_rule_conditions", "allow_full_solution", "answer_depth",
}


class InterventionService:
    def compose_for_turn(self, *, user_id: str, grounding, tree_id: str = "",
                         node_id: str = "", teaching_mode: str = "socratic",
                         socratic_submode: str = "unclassified") -> tuple[StudentStateSummary, TutorPolicy, dict | None]:
        concept_ids = [node.node_id or node.name for node in grounding.related_concepts[:12]]
        prerequisite_ids = [node.node_id or node.name for node in grounding.prerequisite_concepts[:8]]
        state = load_student_state(
            user_id, tree_id=tree_id, node_id=node_id,
            sequence_id=grounding.sequence_id, concept_ids=concept_ids,
            prerequisite_ids=prerequisite_ids,
        )
        policy = decide_tutor_policy(state, teaching_mode, socratic_submode)
        directive = None
        if self.mode() == "active":
            directive = repo.get_active_directive(
                user_id, tree_id=tree_id, node_id=node_id,
                sequence_id=grounding.sequence_id, concept_ids=concept_ids,
            )
        if directive:
            policy = self._apply_qa_policy(policy, directive.get("qa_policy", {}))
        # Explicit user-selected direct mode always has precedence over a model directive.
        if teaching_mode == "direct" and not policy.allow_full_solution:
            policy = replace(policy, allow_full_solution=True, mode="direct")
        return state, policy, directive

    def mark_applied(self, directive_id: str | None, turn_id: str) -> None:
        if directive_id:
            repo.mark_directive_applied(directive_id, turn_id)

    def request_explicit_practice(self, *, user_id: str, turn_id: str, node_id: str = "",
                                  target_concept: str = "", intervention_goal: str = "",
                                  evidence_quote: str = "") -> dict:
        action = repo.create_action(
            user_id=user_id, turn_id=turn_id, node_id=node_id,
            action_type="prepare_practice", trigger_kind="explicit_button",
            payload={
                "target_concept": target_concept,
                "intervention_goal": intervention_goal,
                "evidence_quote": evidence_quote,
            },
        )
        if action.get("draft_id"):
            from app.services.practice.service import practice_service
            existing = practice_service.get_draft(action["draft_id"], user_id)
            if existing:
                return existing
        try:
            from app.services.practice.service import practice_service
            draft = practice_service.create_explicit_draft(
                user_id=user_id, turn_id=turn_id, node_id=node_id,
                target_concept=target_concept, intervention_goal=intervention_goal,
                evidence_quote=evidence_quote,
            )
            self._link_draft(action["id"], draft["id"])
            repo.update_action(action["id"], status="ready", draft_id=draft["id"])
            return draft
        except Exception as exc:
            repo.update_action(action["id"], status="failed", error=str(exc))
            raise

    def plan_snapshot(self, snapshot: dict) -> dict:
        signals = snapshot.get("signals", [])
        preference = repo.get_preferences(snapshot["user_id"])
        auto_prepare = preference.get("auto_prepare_practice", True) is not False
        fallback = self._deterministic_decision(snapshot, signals, auto_prepare)
        decision = self._model_decision(snapshot, signals, fallback) if signals else fallback
        decision = self._validate_decision(decision, snapshot, signals, auto_prepare, fallback)
        directive_status = "active" if self.mode() == "active" else "shadow"
        directive = repo.create_directive(
            snapshot=snapshot, action=decision["action"],
            teaching_goal=decision["teaching_goal"], qa_policy=decision["qa_policy"],
            evidence_refs=decision["evidence_refs"], confidence=decision["confidence"],
            model_name=config.INTERVENTION_PLANNER_MODEL,
            prompt_version=PROMPT_VERSION, status=directive_status,
        )
        result = {"directive": directive, "action": None}
        if self.mode() != "active" or decision["action"] not in {"offer_practice_entry", "prepare_practice"}:
            return result
        trigger = "text_request" if decision["action"] == "offer_practice_entry" else "agent_recommended"
        action = repo.create_action(
            user_id=snapshot["user_id"], turn_id=self._origin_turn(snapshot),
            node_id=snapshot.get("node_id", ""), action_type=decision["action"],
            trigger_kind=trigger, directive_id=directive["id"],
            payload={
                "concept_ids": snapshot.get("concept_ids", []),
                "intervention_goal": decision["teaching_goal"],
                "evidence_refs": decision["evidence_refs"],
                "context_version": directive["context_version"],
            },
        )
        result["action"] = action
        if decision["action"] == "prepare_practice":
            self._dispatch_auto_practice(action, snapshot, directive, signals)
            result["action"] = repo.list_actions_for_turn(snapshot["user_id"], self._origin_turn(snapshot))[-1]
        else:
            repo.update_action(action["id"], status="ready")
        return result

    def get_turn_result(self, *, user_id: str, turn_id: str) -> dict:
        actions = repo.list_actions_for_turn(user_id, turn_id)
        planning = repo.get_planning_status_for_turn(user_id, turn_id)
        public = []
        from app.services.practice.service import practice_service
        for action in actions:
            item = {key: action.get(key) for key in (
                "id", "turn_id", "node_id", "action_type", "trigger_kind", "status", "error",
            )}
            item["payload"] = action.get("payload", {})
            item["draft"] = practice_service.get_draft(action["draft_id"], user_id) if action.get("draft_id") else None
            public.append(item)
        action_terminal = all(
            item["status"] in {"ready", "failed", "stale", "cancelled"} for item in public
        ) if public else False
        planning_terminal = bool(
            planning and planning["status"] in {"ready", "failed", "cancelled"}
        )
        return {
            "turn_id": turn_id,
            "actions": public,
            "terminal": action_terminal or planning_terminal,
        }

    def get_preferences(self, user_id: str) -> dict:
        values = repo.get_preferences(user_id)
        return {"auto_prepare_practice": values.get("auto_prepare_practice", True) is not False}

    def update_preferences(self, user_id: str, *, auto_prepare_practice: bool) -> dict:
        values = repo.update_preferences(user_id, {"auto_prepare_practice": bool(auto_prepare_practice)})
        return {"auto_prepare_practice": values.get("auto_prepare_practice", True) is not False}

    @staticmethod
    def mode() -> str:
        mode = config.TEACHING_CONTROLLER_MODE
        return mode if mode in {"shadow", "active"} else "shadow"

    @staticmethod
    def _apply_qa_policy(policy: TutorPolicy, values: dict) -> TutorPolicy:
        allowed = {key: value for key, value in values.items() if key in QA_POLICY_FIELDS}
        if allowed.get("answer_depth") not in {None, "brief", "normal", "deep"}:
            allowed.pop("answer_depth", None)
        allowed["rationale"] = str(values.get("rationale") or policy.rationale)
        return replace(policy, **allowed)

    def _model_decision(self, snapshot: dict, signals: list[dict], fallback: dict) -> dict:
        from app.services.llm_service import llm_service
        if not llm_service.qa_client:
            return fallback
        prompt = {
            "task": "Choose one bounded next-step teaching action. Never address the student.",
            "allowed_actions": sorted(ALLOWED_ACTIONS),
            "snapshot": snapshot.get("state_payload", {}),
            "signals": [{key: item.get(key) for key in (
                "id", "signal_type", "concept_ids", "student_quote", "confidence", "strength", "rationale",
            )} for item in signals],
            "fallback": fallback,
            "output": {
                "action": "allowed action", "teaching_goal": "short internal goal",
                "qa_policy": {"answer_depth": "brief|normal|deep"},
                "evidence_refs": ["signal id"], "confidence": 0.0,
            },
        }
        try:
            response = llm_service.chat(
                [
                    {"role": "system", "content": "You are a background teaching policy planner. Output strict JSON only."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                model=config.INTERVENTION_PLANNER_MODEL,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            return parse_json_object(raw) or fallback
        except Exception:
            return fallback

    @staticmethod
    def _deterministic_decision(snapshot: dict, signals: list[dict], auto_prepare: bool) -> dict:
        strongest = max(signals, key=lambda item: float(item.get("confidence") or 0), default={})
        confidence = float(strongest.get("confidence") or 0)
        strength = strongest.get("strength")
        signal_type = strongest.get("signal_type")
        action = "no_action"
        if signal_type == "practice_request":
            action = "offer_practice_entry"
        elif auto_prepare and confidence >= 0.8 and strength in {"probable", "certain"}:
            action = "prepare_practice"
        elif confidence >= 0.6:
            action = "adjust_qa"
        qa_policy: dict[str, Any] = {}
        if signal_type in {"concept_confusion", "prerequisite_gap"}:
            qa_policy = {
                "should_review_prerequisites": signal_type == "prerequisite_gap",
                "should_ask_guiding_question": True,
                "answer_depth": "normal",
                "rationale": strongest.get("rationale") or "evidence-backed remediation",
            }
        elif signal_type in {"procedural_error", "hint_dependency"}:
            qa_policy = {
                "should_ask_guiding_question": True,
                "answer_depth": "brief",
                "rationale": strongest.get("rationale") or "verify independent execution",
            }
        return {
            "action": action,
            "teaching_goal": strongest.get("rationale") or "Use the latest diagnosis conservatively.",
            "qa_policy": qa_policy,
            "evidence_refs": [strongest["id"]] if strongest.get("id") else [],
            "confidence": confidence,
        }

    @staticmethod
    def _validate_decision(decision: dict, snapshot: dict, signals: list[dict],
                           auto_prepare: bool, fallback: dict) -> dict:
        action = decision.get("action")
        signal_by_id = {item["id"]: item for item in signals if item.get("id")}
        refs = decision.get("evidence_refs") if isinstance(decision.get("evidence_refs"), list) else []
        refs = [item for item in refs if item in signal_by_id]
        confidence = float(decision.get("confidence") or 0)
        confidence = max(0.0, min(1.0, confidence))
        supporting = [signal_by_id[item] for item in refs]
        if action not in ALLOWED_ACTIONS or (action != "no_action" and not supporting):
            return fallback
        strongest = max(supporting, key=lambda item: float(item.get("confidence") or 0), default={})
        evidence_confidence = float(strongest.get("confidence") or 0)
        if action == "prepare_practice" and (
            not auto_prepare or evidence_confidence < 0.8
            or strongest.get("strength") not in {"probable", "certain"}
        ):
            return fallback if fallback["action"] != "prepare_practice" else {**fallback, "action": "adjust_qa"}
        if action == "offer_practice_entry" and evidence_confidence < 0.6:
            return fallback
        qa_policy = decision.get("qa_policy") if isinstance(decision.get("qa_policy"), dict) else {}
        qa_policy = {key: value for key, value in qa_policy.items() if key in QA_POLICY_FIELDS | {"rationale"}}
        return {
            "action": action,
            "teaching_goal": str(decision.get("teaching_goal") or fallback["teaching_goal"]),
            "qa_policy": qa_policy,
            "evidence_refs": refs,
            "confidence": min(confidence, evidence_confidence) if supporting else 0.0,
        }

    def _dispatch_auto_practice(self, action: dict, snapshot: dict, directive: dict,
                                signals: list[dict]) -> None:
        try:
            from app.services.practice.service import practice_service
            strongest = max(signals, key=lambda item: float(item.get("confidence") or 0), default={})
            draft = practice_service.create_from_intervention(
                user_id=snapshot["user_id"], turn_id=self._origin_turn(snapshot),
                intervention_action_id=action["id"], target_concepts=snapshot.get("concept_ids", []),
                intervention_goal=directive.get("teaching_goal", ""),
                evidence_quote=strongest.get("student_quote", ""),
            )
            self._link_draft(action["id"], draft["id"])
            repo.update_action(action["id"], status="ready", draft_id=draft["id"])
        except Exception as exc:
            repo.update_action(action["id"], status="failed", error=str(exc))

    @staticmethod
    def _origin_turn(snapshot: dict) -> str:
        if snapshot["source_type"] == "qa_turn":
            return snapshot["source_id"]
        conn = __import__("app.db.connection", fromlist=["get_conn"]).get_conn()
        try:
            row = conn.execute(
                "SELECT turn_id FROM practice_drafts WHERE id=(SELECT draft_id FROM practice_attempts WHERE id=?)",
                (snapshot["source_id"],),
            ).fetchone()
            return row["turn_id"] if row else snapshot["source_id"]
        finally:
            conn.close()

    @staticmethod
    def _link_draft(action_id: str, draft_id: str) -> None:
        from app.db.connection import get_conn
        conn = get_conn()
        try:
            conn.execute(
                "UPDATE practice_drafts SET intervention_action_id=? WHERE id=?",
                (action_id, draft_id),
            )
            conn.commit()
        finally:
            conn.close()


intervention_service = InterventionService()
