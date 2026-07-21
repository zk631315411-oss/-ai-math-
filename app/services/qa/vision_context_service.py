"""截图/视觉 QA 的上下文准备。

本文件只负责把图片、PDF 裁剪、截图缓存和教材定位整理成结构化上下文。
不调用大模型，也不触发诊断。
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from app.config import config
from app.db.screenshot_context_cache_db import (
    find_screenshot_context_cache,
    get_screenshot_context_cache,
    save_screenshot_context_cache,
    update_screenshot_context_cache,
)
from app.services.pdf_cropper import (
    content_hash,
    hash_bbox,
    image_data_hash,
    normalize_bbox,
    render_pdf_crop,
)
from app.services.screenshot_locator import locate_screenshot_context
from app.services.qa.contracts import QATurnInput


def get_valid_screenshot_cache(turn_input: QATurnInput) -> dict | None:
    """读取并校验前端传来的截图上下文缓存。"""

    if not turn_input.screenshot_context_id:
        return None
    cached = get_screenshot_context_cache(turn_input.screenshot_context_id)
    if not cached:
        return None
    if turn_input.textbook_id and cached.get("textbook_id") != turn_input.textbook_id:
        return None
    if turn_input.page_number and int(cached.get("page_number") or 0) != int(turn_input.page_number):
        return None
    return cached


def has_screenshot_context(turn_input: QATurnInput) -> bool:
    """判断本轮请求是否应该走截图/视觉 QA。"""

    if turn_input.image_data:
        return True
    if turn_input.crop_bbox and turn_input.page_number:
        return True
    cached = get_valid_screenshot_cache(turn_input)
    return bool(cached and (cached.get("pdf_crop_path") or (cached.get("crop_bbox") and cached.get("page_number"))))


def prepare_screenshot_context(turn_input: QATurnInput, textbook_id: str, page_context: dict) -> dict[str, Any]:
    """准备视觉模型输入所需的截图上下文。"""

    full_context = page_context.get("content", "") if page_context and "error" not in page_context else ""
    full_context_hash = content_hash(full_context)
    normalized_bbox = normalize_bbox(turn_input.crop_bbox)
    img_hash = image_data_hash(turn_input.image_data)
    page_number = turn_input.page_number or 0

    cached = None
    if turn_input.screenshot_context_id:
        cached = get_valid_screenshot_cache(turn_input)
        if cached:
            page_number = turn_input.page_number or int(cached.get("page_number") or 0)
            if not normalized_bbox and cached.get("crop_bbox"):
                try:
                    normalized_bbox = normalize_bbox(json.loads(cached.get("crop_bbox") or "{}"))
                except Exception:
                    normalized_bbox = None
        if cached and (
            cached.get("textbook_id") != textbook_id
            or int(cached.get("page_number") or 0) != int(page_number or 0)
            or cached.get("full_context_hash") != full_context_hash
        ):
            cached = None

    bbox_hash = hash_bbox(normalized_bbox)

    if not cached and page_number:
        cached = find_screenshot_context_cache(
            img_hash,
            textbook_id,
            page_number,
            bbox_hash,
            full_context_hash,
        )

    if cached:
        locator_result = _locator_result_from_cache(cached)
        pdf_crop = _load_cached_pdf_crop(cached, normalized_bbox)
        if not pdf_crop and page_number and normalized_bbox:
            pdf_crop = render_pdf_crop(
                textbook_id,
                page_number,
                normalized_bbox,
                image_hash=img_hash or cached.get("image_hash") or "",
            )
            if pdf_crop and cached.get("id"):
                update_screenshot_context_cache(cached["id"], pdf_crop_path=pdf_crop.get("path"))

        return {
            "cache_id": cached["id"],
            "pdf_crop": pdf_crop,
            "locator_result": locator_result,
            "reused_cache": True,
            "image_hash": img_hash or cached.get("image_hash") or "",
            "crop_bbox": normalized_bbox,
            "crop_bbox_hash": bbox_hash or cached.get("crop_bbox_hash"),
            "full_context_hash": full_context_hash,
            "pdf_crop_path": (pdf_crop or {}).get("path") or cached.get("pdf_crop_path"),
            "page_context_excerpt": full_context[:2000],
        }

    pdf_crop = (
        render_pdf_crop(
            textbook_id,
            page_number,
            normalized_bbox,
            image_hash=img_hash,
        )
        if page_number and normalized_bbox
        else None
    )

    locator_result = (
        locate_screenshot_context(
            textbook_id=textbook_id,
            page_number=page_number,
            crop_bbox=normalized_bbox,
            full_context=full_context,
        )
        if page_number and normalized_bbox
        else {
            "status": "miss",
            "confidence": 0.0,
            "matched_text": "",
            "signals": {"reason": "missing page_number or crop_bbox"},
        }
    )

    cache_id = save_screenshot_context_cache(
        image_hash=img_hash,
        textbook_id=textbook_id,
        page_number=page_number,
        crop_bbox=normalized_bbox,
        crop_bbox_hash=bbox_hash,
        full_context_hash=full_context_hash,
        pdf_crop_path=pdf_crop.get("path") if pdf_crop else None,
        md_match_status=locator_result.get("status"),
        md_match_confidence=locator_result.get("confidence"),
        md_match_text=locator_result.get("matched_text"),
        locator_signals=locator_result.get("signals"),
        vision_model=config.QA_VL_MODEL,
    )

    return {
        "cache_id": cache_id,
        "pdf_crop": pdf_crop,
        "locator_result": locator_result,
        "reused_cache": False,
        "image_hash": img_hash,
        "crop_bbox": normalized_bbox,
        "crop_bbox_hash": bbox_hash,
        "full_context_hash": full_context_hash,
        "pdf_crop_path": (pdf_crop or {}).get("path"),
        "page_context_excerpt": full_context[:2000],
    }


def build_screenshot_locator_prompt(locator_result: dict, reused_cache: bool) -> str:
    """构造给 VL prompt 使用的截图定位说明。"""

    status = locator_result.get("status") or "miss"
    confidence = locator_result.get("confidence", 0)
    matched_text = locator_result.get("matched_text") or ""
    source = "cache" if reused_cache else "fresh"

    if status == "hit":
        return f"""【截图定位结果】
来源：{source}
md_match_status: hit
confidence: {confidence}
定位片段：
{matched_text[:1800]}

注意：该片段仅用于辅助定位。最终仍需以随附 PDF 高清裁剪图为准，并结合完整教材上下文回答。"""

    if status == "weak":
        return f"""【截图定位结果】
来源：{source}
md_match_status: weak
confidence: {confidence}
可能相关片段：
{matched_text[:1200]}

注意：定位不够可靠，请优先观察随附 PDF 高清裁剪图，并结合完整教材上下文回答。"""

    return f"""【截图定位结果】
来源：{source}
md_match_status: miss
confidence: {confidence}
说明：教材 md 中未找到可靠对应片段。请以随附 PDF 高清裁剪图为准，并结合完整教材上下文回答。"""


def _locator_result_from_cache(cached: dict) -> dict:
    try:
        locator_signals = json.loads(cached.get("locator_signals") or "{}")
    except Exception:
        locator_signals = {}
    return {
        "status": cached.get("md_match_status") or "miss",
        "confidence": cached.get("md_match_confidence") or 0.0,
        "matched_text": cached.get("md_match_text") or "",
        "signals": locator_signals,
    }


def _load_cached_pdf_crop(cached: dict, normalized_bbox: dict | None) -> dict | None:
    crop_path = cached.get("pdf_crop_path")
    if not crop_path:
        return None
    try:
        image_bytes = Path(crop_path).read_bytes()
        return {
            "path": crop_path,
            "data_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
            "bbox": normalized_bbox,
        }
    except Exception:
        return None
