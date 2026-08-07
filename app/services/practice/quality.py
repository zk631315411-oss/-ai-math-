"""Deterministic quality gates for generated practice items."""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.sympy_sandbox import WHITELIST, verify_computable

QUESTION_TYPES = {"calculation", "concept", "proof"}
BRANCH_ROLES = {"diagnostic", "remedial", "verify", "advance"}
DIAGNOSTIC_GOALS = {"definition", "application", "proof", "counterexample", "transfer"}


def validate_item(item: dict, context: dict) -> tuple[bool, str]:
    required = ("question", "question_type", "answer_spec", "hints")
    if any(not item.get(key) and key not in {"answer_spec"} for key in required):
        return False, "missing_required_item_field"
    if item.get("question_type") not in QUESTION_TYPES:
        return False, "invalid_question_type"
    answer_spec = item.get("answer_spec")
    if not isinstance(answer_spec, dict) or not str(answer_spec.get("reference") or "").strip():
        return False, "answer_spec_reference_required"
    goal = str(item.get("diagnostic_goal") or "application")
    if goal not in DIAGNOSTIC_GOALS:
        return False, "invalid_diagnostic_goal"
    hints = item.get("hints")
    if not isinstance(hints, list) or not 1 <= len(hints) <= 3:
        return False, "hints_must_have_one_to_three_items"
    concepts = set(item.get("concept_ids") or [])
    allowed = set(context.get("concept_ids") or [])
    if allowed and concepts and not concepts.issubset(allowed):
        return False, "concept_out_of_scope"
    if context.get("evidence_quote") and context["evidence_quote"] not in context.get("question", ""):
        return False, "evidence_quote_not_in_student_question"
    if len(item.get("question", "")) > 8000:
        return False, "question_too_long"
    if item.get("question_type") == "proof" and not isinstance(item.get("rubric"), list):
        return False, "proof_rubric_required"
    return True, "ok"


def verify_item_math(item: dict) -> tuple[bool, str]:
    spec = item.get("answer_spec") or {}
    if item.get("question_type") != "calculation":
        return True, "not_applicable"
    if not isinstance(spec, dict) or spec.get("type") not in WHITELIST or "expected" not in spec:
        return False, "calculation_answer_spec_must_be_verifiable"
    comp_type = spec.get("type")
    data = {key: value for key, value in spec.items() if key not in {"type", "expected"}}
    result = verify_computable(comp_type, data, spec.get("expected"))
    return bool(result.get("success")), result.get("error", "verified") if not result.get("success") else "verified"


def dedupe_signature(item: dict) -> str:
    text = re.sub(r"\s+", " ", str(item.get("question", "")).strip().lower())
    return text[:1000]


def parse_json_object(raw: str) -> dict:
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", raw or "", re.DOTALL)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
