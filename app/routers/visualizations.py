"""Math visualization and on-demand animation API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.auth.jwt_handler import decode_token
from app.db.visualization_db import (
    create_animation_job,
    get_animation_job,
    get_visualization,
)
from app.services.visualization.queue import enqueue_animation, reconcile_animation_job
from app.services.visualization.storage import presign_get


router = APIRouter(prefix="/api/visualizations", tags=["数学可视化"])


class AnimationRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


def _validated_user_id(requested_user_id: str, authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少认证令牌")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="无效的认证令牌")
    try:
        token_user_id = decode_token(parts[1]).get("user_id")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="无效的认证令牌") from exc
    if not token_user_id or token_user_id != requested_user_id:
        raise HTTPException(status_code=403, detail="不能访问其他用户的可视化")
    return token_user_id


def _job_response(job: dict) -> dict:
    result = {
        "id": job["id"],
        "visualization_id": job["visualization_id"],
        "status": job["status"],
        "error": job.get("error") or "",
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }
    if job["status"] == "completed":
        try:
            result["video_url"] = presign_get(job.get("video_key"))
            result["poster_url"] = presign_get(job.get("poster_key"))
        except Exception:
            result["status"] = "failed"
            result["error"] = "动画文件暂时无法访问"
    return result


@router.get("/animations/{job_id}")
def animation_status(job_id: str, user_id: str, authorization: Optional[str] = Header(None)):
    validated = _validated_user_id(user_id, authorization)
    try:
        return _job_response(reconcile_animation_job(get_animation_job(job_id, validated)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{visualization_id}/animations")
def create_animation(
    visualization_id: str,
    req: AnimationRequest,
    authorization: Optional[str] = Header(None),
):
    validated = _validated_user_id(req.user_id, authorization)
    try:
        job, created = create_animation_job(visualization_id, validated)
        if created:
            enqueue_animation(job["id"])
            job = get_animation_job(job["id"], validated)
        job = reconcile_animation_job(job)
        return _job_response(job)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{visualization_id}")
def visualization_detail(
    visualization_id: str,
    user_id: str,
    authorization: Optional[str] = Header(None),
):
    validated = _validated_user_id(user_id, authorization)
    try:
        artifact = get_visualization(visualization_id, validated)
        job_id = artifact.get("animation_job_id")
        if job_id:
            animation = _job_response(
                reconcile_animation_job(get_animation_job(job_id, validated))
            )
            artifact["animation"] = animation
            artifact["animation_status"] = animation["status"]
        return artifact
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
