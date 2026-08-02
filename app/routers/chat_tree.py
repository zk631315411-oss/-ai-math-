"""Normalized follow-up tree API.

The legacy chat-history endpoints remain available; these endpoints expose the
tree model for new clients and can be adopted incrementally by the frontend.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel, Field

from app.db.chat_tree_db import (
    InvalidFork,
    RevisionConflict,
    TreeForbidden,
    TreeNotFound,
    append_message,
    archive_node,
    create_fork,
    create_tree,
    create_summary_tree,
    ensure_tree_from_history,
    get_authorized_context,
    get_messages,
    get_tree,
    get_tree_by_history,
    migrate_legacy_followups,
    get_latest_summary_tree,
    update_summary_node,
    restore_node,
    set_active_node,
    set_references,
    update_node,
)
from app.auth.jwt_handler import decode_token

router = APIRouter(prefix="/api/chat", tags=["对话追问树"])


class UserRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


class CreateTreeRequest(UserRequest):
    root_chat_history_id: Optional[str] = None
    question: str = Field(..., min_length=1)
    answer: Optional[str] = None
    title: Optional[str] = None


class CreateForkRequest(UserRequest):
    fork_message_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    title: Optional[str] = None
    expected_revision: Optional[int] = Field(None, ge=0)


class AppendMessageRequest(UserRequest):
    role: str = "user"
    content: str = ""
    status: str = "completed"
    expected_revision: Optional[int] = Field(None, ge=0)
    message_id: Optional[str] = None


class UpdateNodeRequest(UserRequest):
    title: Optional[str] = None
    exclude_from_summary: Optional[bool] = None
    is_adopted: Optional[bool] = None
    expected_revision: Optional[int] = Field(None, ge=0)


class ActiveNodeRequest(UserRequest):
    node_id: str
    expected_revision: Optional[int] = Field(None, ge=0)


class ReferencesRequest(UserRequest):
    target_node_ids: list[str] = Field(default_factory=list)
    selected_message_ids: dict[str, list[str]] = Field(default_factory=dict)


class SummaryNodeInput(BaseModel):
    id: Optional[str] = None
    parent_summary_node_id: Optional[str] = None
    node_type: str = "conclusion"
    learning_status: str = "explained"
    title: str = ""
    content: str = ""
    source_message_ids: list[str] = Field(default_factory=list)
    edited_by_user: bool = False
    locked: bool = False


class SummaryCreateRequest(UserRequest):
    nodes: list[SummaryNodeInput] = Field(default_factory=list)
    created_by: str = "user"


class SummaryNodePatchRequest(UserRequest):
    title: Optional[str] = None
    content: Optional[str] = None
    learning_status: Optional[str] = None
    expected_revision: Optional[int] = Field(None, ge=0)
    lock: Optional[bool] = None


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, TreeForbidden):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, TreeNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RevisionConflict):
        return HTTPException(status_code=409, detail={"code": "revision_conflict", "message": str(exc)})
    if isinstance(exc, InvalidFork):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


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
        raise HTTPException(status_code=403, detail="不能访问其他用户的对话树")
    return token_user_id


@router.get("/trees/by-history/{chat_history_id}")
def tree_by_history(chat_history_id: str, user_id: str, authorization: Optional[str] = Header(None)):
    try:
        return get_tree_by_history(chat_history_id, _validated_user_id(user_id, authorization)) or {}
    except Exception as exc:
        raise _error(exc)


@router.get("/trees/{tree_id}")
def tree_detail(tree_id: str, user_id: str, include_archived: bool = False, authorization: Optional[str] = Header(None)):
    try:
        return get_tree(tree_id, _validated_user_id(user_id, authorization), include_archived=include_archived)
    except Exception as exc:
        raise _error(exc)


@router.patch("/trees/{tree_id}/active-node")
def activate_node(tree_id: str, req: ActiveNodeRequest, authorization: Optional[str] = Header(None)):
    try:
        return set_active_node(tree_id, _validated_user_id(req.user_id, authorization), req.node_id, req.expected_revision)
    except Exception as exc:
        raise _error(exc)


@router.post("/trees")
def create_chat_tree(req: CreateTreeRequest, authorization: Optional[str] = Header(None)):
    try:
        return create_tree(_validated_user_id(req.user_id, authorization), req.root_chat_history_id, req.question, req.answer, req.title)
    except Exception as exc:
        raise _error(exc)


@router.post("/trees/from-history/{chat_history_id}")
def materialize_history_tree(
    chat_history_id: str,
    req: UserRequest,
    authorization: Optional[str] = Header(None),
):
    try:
        user_id = _validated_user_id(req.user_id, authorization)
        return ensure_tree_from_history(chat_history_id, user_id)
    except Exception as exc:
        raise _error(exc)


@router.post("/nodes/{node_id}/fork")
def fork_node(node_id: str, req: CreateForkRequest, authorization: Optional[str] = Header(None)):
    try:
        return create_fork(node_id, _validated_user_id(req.user_id, authorization), req.fork_message_id, req.question, req.title, req.expected_revision)
    except Exception as exc:
        raise _error(exc)


@router.patch("/nodes/{node_id}")
def patch_node(node_id: str, req: UpdateNodeRequest, authorization: Optional[str] = Header(None)):
    try:
        return update_node(node_id, _validated_user_id(req.user_id, authorization), title=req.title, exclude_from_summary=req.exclude_from_summary, is_adopted=req.is_adopted, expected_revision=req.expected_revision)
    except Exception as exc:
        raise _error(exc)


@router.post("/nodes/{node_id}/archive")
def archive(node_id: str, req: UserRequest, expected_revision: Optional[int] = None, authorization: Optional[str] = Header(None)):
    try:
        return archive_node(node_id, _validated_user_id(req.user_id, authorization), expected_revision)
    except Exception as exc:
        raise _error(exc)


@router.post("/nodes/{node_id}/restore")
def restore(node_id: str, req: UserRequest, expected_revision: Optional[int] = None, authorization: Optional[str] = Header(None)):
    try:
        return restore_node(node_id, _validated_user_id(req.user_id, authorization), expected_revision)
    except Exception as exc:
        raise _error(exc)


@router.post("/nodes/{node_id}/messages")
def add_message(node_id: str, req: AppendMessageRequest, authorization: Optional[str] = Header(None)):
    try:
        return append_message(node_id, _validated_user_id(req.user_id, authorization), req.role, req.content, req.status, req.expected_revision, req.message_id)
    except Exception as exc:
        raise _error(exc)


@router.get("/nodes/{node_id}/messages")
def node_messages(node_id: str, user_id: str, include_archived: bool = False, authorization: Optional[str] = Header(None)):
    try:
        return get_messages(node_id, _validated_user_id(user_id, authorization), include_archived=include_archived)
    except Exception as exc:
        raise _error(exc)


@router.put("/nodes/{node_id}/references")
def node_references(node_id: str, req: ReferencesRequest, authorization: Optional[str] = Header(None)):
    try:
        return set_references(node_id, _validated_user_id(req.user_id, authorization), req.target_node_ids, req.selected_message_ids)
    except Exception as exc:
        raise _error(exc)


@router.get("/nodes/{node_id}/context")
def node_context(
    node_id: str,
    user_id: str,
    referenced_node_ids: list[str] = Query(default=[]),
    terminal_message_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    try:
        return get_authorized_context(
            node_id,
            _validated_user_id(user_id, authorization),
            referenced_node_ids,
            terminal_message_id,
        )
    except Exception as exc:
        raise _error(exc)


@router.post("/trees/{tree_id}/summaries")
def create_summary(tree_id: str, req: SummaryCreateRequest, authorization: Optional[str] = Header(None)):
    try:
        user_id = _validated_user_id(req.user_id, authorization)
        return create_summary_tree(tree_id, user_id, [item.model_dump() for item in req.nodes], req.created_by)
    except Exception as exc:
        raise _error(exc)


@router.get("/trees/{tree_id}/summaries/latest")
def latest_summary(tree_id: str, user_id: str, authorization: Optional[str] = Header(None)):
    try:
        return get_latest_summary_tree(tree_id, _validated_user_id(user_id, authorization)) or {}
    except Exception as exc:
        raise _error(exc)


@router.patch("/summary-nodes/{summary_node_id}")
def patch_summary_node(summary_node_id: str, req: SummaryNodePatchRequest, authorization: Optional[str] = Header(None)):
    try:
        user_id = _validated_user_id(req.user_id, authorization)
        return update_summary_node(summary_node_id, user_id, title=req.title, content=req.content, learning_status=req.learning_status, expected_revision=req.expected_revision, lock=req.lock)
    except Exception as exc:
        raise _error(exc)


@router.post("/trees/migrate-legacy")
def migrate_legacy(user_id: str, authorization: Optional[str] = Header(None)):
    try:
        validated = _validated_user_id(user_id, authorization)
        return {"created": migrate_legacy_followups(validated)}
    except Exception as exc:
        raise _error(exc)
