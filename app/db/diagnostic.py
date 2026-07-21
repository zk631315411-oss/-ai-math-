"""Compatibility bridge for diagnosis V2.

Legacy callers keep their imports, but all execution is routed through source-specific
V2 scorers and deterministic projectors.
"""

from __future__ import annotations

from app.db.math_profile_db import get_math_profile
from app.services.diagnosis.diagnosis_service import (
    get_concepts_by_sequence_id,
    get_prerequisite_chain,
    get_user_recent_chats,
    parse_diagnostic_json,
)


async def run_diagnostic_pipeline(
    user_id: str,
    topic: str = "",
    sequence_id: str = "",
    textbook_id: str = "",
    **_: object,
) -> bool:
    from app.services.diagnostic_worker import run_diagnostic_batch

    return await run_diagnostic_batch(user_id)


async def trigger_diagnostic_if_needed(
    user_id: str,
    topic: str = "",
    sequence_id: str = "",
    textbook_id: str = "",
) -> None:
    from app.services.diagnostic_worker import run_diagnostic_batch

    await run_diagnostic_batch(user_id)


def should_trigger_diagnostic(
    user_id: str,
    topic: str = "",
    consecutive_turns: int = 0,
    total_asks: int = 0,
) -> bool:
    from app.services.diagnostic_worker import should_trigger_diagnostic_batch

    return should_trigger_diagnostic_batch(user_id)


def save_diagnostic_result(**_: object) -> None:
    raise RuntimeError("V2 禁止直接保存混合诊断结果；请写入诊断证据并通过投影器更新画像")


def extract_dimension_scores(_: dict) -> dict:
    """Legacy compatibility: single-run dimension updates are disabled in V2."""

    return {}


__all__ = [
    "extract_dimension_scores",
    "get_concepts_by_sequence_id",
    "get_math_profile",
    "get_prerequisite_chain",
    "get_user_recent_chats",
    "parse_diagnostic_json",
    "run_diagnostic_pipeline",
    "save_diagnostic_result",
    "should_trigger_diagnostic",
    "trigger_diagnostic_if_needed",
]
