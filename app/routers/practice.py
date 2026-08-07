"""Conversation-driven adaptive practice API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.auth.jwt_handler import decode_token
from app.models.schemas import PracticeAttemptRequest, PracticeDraftCreateRequest
from app.services.practice.service import practice_service
from app.services.intervention.service import intervention_service

router = APIRouter(prefix="/api/practice", tags=["practice-v2"])


def _user_id(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(401, "未登录或 token 无效")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "未登录或 token 无效")
    try:
        user_id = decode_token(parts[1]).get("user_id")
    except Exception as exc:
        raise HTTPException(401, "未登录或 token 无效") from exc
    if not user_id:
        raise HTTPException(401, "未登录或 token 无效")
    return user_id


@router.post("/drafts", status_code=202)
def create_draft(request: PracticeDraftCreateRequest, authorization: Optional[str] = Header(None)):
    try:
        return intervention_service.request_explicit_practice(
            user_id=_user_id(authorization), **request.model_dump()
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, authorization: Optional[str] = Header(None)):
    draft = practice_service.get_draft(draft_id, _user_id(authorization))
    if not draft:
        raise HTTPException(404, "练习草稿不存在")
    return draft


@router.post("/drafts/{draft_id}/start")
def start_draft(draft_id: str, authorization: Optional[str] = Header(None)):
    try:
        return practice_service.start_session(draft_id, _user_id(authorization))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/drafts/{draft_id}/regenerate", status_code=202)
def regenerate_draft(draft_id: str, authorization: Optional[str] = Header(None)):
    try:
        return practice_service.regenerate(draft_id, _user_id(authorization))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/sessions/{session_id}/attempts")
async def submit_attempt(session_id: str, request: PracticeAttemptRequest,
                         authorization: Optional[str] = Header(None)):
    try:
        return await practice_service.submit_attempt(
            session_id, _user_id(authorization), request.item_id, request.student_answer,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/sessions/{session_id}/hints")
def request_hint(session_id: str, authorization: Optional[str] = Header(None)):
    try:
        return practice_service.request_hint(session_id, _user_id(authorization))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
