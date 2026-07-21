"""反馈收集：前端表单 → QQ 邮箱 SMTP → 631315411@qq.com。"""
import smtplib
from email.mime.text import MIMEText
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
SMTP_USER = "631315411@qq.com"
SMTP_TO = "631315411@qq.com"


class FeedbackRequest(BaseModel):
    content: str


@router.post("")
async def send_feedback(req: FeedbackRequest):
    from app.config import config

    password = getattr(config, "SMTP_PASSWORD", None) or __import__("os").getenv("SMTP_PASSWORD", "")
    if not password:
        raise HTTPException(500, "SMTP 未配置")

    body = req.content.strip()
    if not body or len(body) > 2000:
        raise HTTPException(400, "反馈内容为空或超过2000字")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"智学助手反馈 — {body[:30]}..."
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, password)
            server.sendmail(SMTP_USER, [SMTP_TO], msg.as_string())
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"发送失败: {e}")
