from fastapi import APIRouter, Header
from pydantic import BaseModel
from typing import Optional
from app.auth.jwt_handler import decode_token
from app.db.math_profile_db import save_textbook_preference as db_save_pref, get_textbook_preference as db_get_pref

router = APIRouter(prefix="/api/profile", tags=["用户偏好"])


def get_user_id_from_token(authorization: Optional[str]) -> Optional[str]:
    """从Authorization header解析user_id"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    try:
        token_data = decode_token(parts[1])
        return token_data.get("user_id")
    except Exception:
        return None


class TextbookPreferenceRequest(BaseModel):
    textbook_id: str
    page_number: int


@router.get("/textbook-preference")
def get_textbook_preference_api(authorization: Optional[str] = Header(None)):
    """获取教材和页码偏好"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        return {"textbook_id": None, "page_number": None}
    pref = db_get_pref(user_id)
    return pref or {"textbook_id": None, "page_number": None}


@router.post("/textbook-preference")
def save_textbook_preference_api(
    body: TextbookPreferenceRequest,
    authorization: Optional[str] = Header(None)
):
    """保存教材和页码偏好"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        return {"success": False, "error": "未登录"}
    db_save_pref(user_id, body.textbook_id, body.page_number)
    return {"success": True}
