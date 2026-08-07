"""Student-visible discovery endpoints for background teaching decisions."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.auth.jwt_handler import decode_token
from app.models.schemas import LearningPreferenceUpdate
from app.services.intervention.service import intervention_service


router = APIRouter(prefix="/api/interventions", tags=["teaching-controller"])


def _user_id(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(401, "authentication required")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "invalid bearer token")
    try:
        user_id = decode_token(parts[1]).get("user_id")
    except Exception as exc:
        raise HTTPException(401, "invalid bearer token") from exc
    if not user_id:
        raise HTTPException(401, "invalid bearer token")
    return user_id


@router.get("/turns/{turn_id}")
def get_turn_interventions(turn_id: str, authorization: Optional[str] = Header(None)):
    return intervention_service.get_turn_result(user_id=_user_id(authorization), turn_id=turn_id)


@router.get("/preferences")
def get_preferences(authorization: Optional[str] = Header(None)):
    return intervention_service.get_preferences(_user_id(authorization))


@router.patch("/preferences")
def update_preferences(request: LearningPreferenceUpdate,
                       authorization: Optional[str] = Header(None)):
    return intervention_service.update_preferences(
        _user_id(authorization), auto_prepare_practice=request.auto_prepare_practice,
    )
