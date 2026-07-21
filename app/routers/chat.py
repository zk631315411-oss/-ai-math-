"""问答历史 API — Phase 2：支持页码标记、持久化、CRUD。"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.db.chat_history_db import (
    get_chat_history, save_chat_history, update_chat_answer, delete_chat_history,
    migrate_user_id,
)

router = APIRouter(prefix="/api/chat", tags=["智能问答"])


class SaveChatRequest(BaseModel):
    user_id: str
    question: str
    answer: Optional[str] = None
    page_number: Optional[int] = None
    marker_y_ratio: Optional[float] = None
    marker_type: str = "screenshot"
    thumbnail: Optional[str] = None
    crop_bbox: Optional[str] = None
    screenshot_context_id: Optional[str] = None
    sources: Optional[str] = None
    knowledge_points: Optional[str] = None


class UpdateChatRequest(BaseModel):
    answer: Optional[str] = None
    thinking: Optional[str] = None
    follow_ups: Optional[str] = None
    screenshot_context_id: Optional[str] = None
    thumbnail: Optional[str] = None
    crop_bbox: Optional[str] = None


@router.get("/history/{user_id}")
def get_history(user_id: str, limit: int = 50, page: Optional[int] = None, id: Optional[str] = None):
    return get_chat_history(user_id, limit=limit, page_number=page, chat_id=id)


@router.post("/history")
def create_history(req: SaveChatRequest):
    """截图/文字提问时前端调用，写入标记记录（answer 可为空）。"""
    chat_id = save_chat_history(
        user_id=req.user_id, question=req.question, answer=req.answer,
        page_number=req.page_number, marker_y_ratio=req.marker_y_ratio,
        marker_type=req.marker_type, thumbnail=req.thumbnail,
        crop_bbox=req.crop_bbox, screenshot_context_id=req.screenshot_context_id,
        sources=req.sources, knowledge_points=req.knowledge_points,
    )
    return {"id": chat_id}


@router.patch("/history/{chat_id}")
def update_history(chat_id: str, req: UpdateChatRequest):
    """SSE 完成后更新标记：answer / thinking / follow_ups 可分别更新。"""
    update_chat_answer(
        chat_id,
        answer=req.answer,
        thinking=req.thinking,
        follow_ups=req.follow_ups,
        screenshot_context_id=req.screenshot_context_id,
        thumbnail=req.thumbnail,
        crop_bbox=req.crop_bbox,
    )
    return {"status": "ok"}


@router.delete("/history/{chat_id}")
def delete_history(chat_id: str):
    delete_chat_history(chat_id)
    return {"status": "deleted"}


@router.post("/migrate")
def migrate_markers(old_user_id: str, new_user_id: str):
    """匿名→登录后，将旧账号的 chat_history 标记迁到新账号。"""
    count = migrate_user_id(old_user_id, new_user_id)
    return {"status": "ok", "migrated": count}
