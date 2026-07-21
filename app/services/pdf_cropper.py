import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Optional

import fitz

from app.config import config
from app.services.textbook_assets import get_pdf_page_index, get_textbook_pdf_path


def normalize_bbox(crop_bbox: Optional[dict]) -> Optional[dict]:
    if not isinstance(crop_bbox, dict):
        return None
    try:
        x = max(0.0, min(1.0, float(crop_bbox.get("x", 0))))
        y = max(0.0, min(1.0, float(crop_bbox.get("y", 0))))
        width = max(0.0, min(1.0, float(crop_bbox.get("width", 0))))
        height = max(0.0, min(1.0, float(crop_bbox.get("height", 0))))
    except (TypeError, ValueError):
        return None

    if width <= 0 or height <= 0:
        return None

    if x + width > 1:
        width = 1 - x
    if y + height > 1:
        height = 1 - y

    return {
        "x": round(x, 6),
        "y": round(y, 6),
        "width": round(width, 6),
        "height": round(height, 6),
        "unit": "page_ratio",
    }


def hash_bbox(crop_bbox: Optional[dict]) -> str:
    normalized = normalize_bbox(crop_bbox) or {}
    raw = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def image_data_hash(image_data: Optional[str]) -> str:
    if not image_data:
        return ""
    return hashlib.sha256(image_data.encode("utf-8")).hexdigest()


def content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def _expanded_rect(page_rect: fitz.Rect, crop_bbox: dict, margin_ratio: float = 0.10) -> fitz.Rect:
    x0 = page_rect.x0 + crop_bbox["x"] * page_rect.width
    y0 = page_rect.y0 + crop_bbox["y"] * page_rect.height
    x1 = x0 + crop_bbox["width"] * page_rect.width
    y1 = y0 + crop_bbox["height"] * page_rect.height

    margin_x = (x1 - x0) * margin_ratio
    margin_y = (y1 - y0) * margin_ratio
    rect = fitz.Rect(x0 - margin_x, y0 - margin_y, x1 + margin_x, y1 + margin_y)
    return rect & page_rect


def _safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", value).strip("_") or "textbook"


def render_pdf_crop(
    textbook_id: str,
    page_number: int,
    crop_bbox: Optional[dict],
    *,
    image_hash: str = "",
    zoom: float = 2.0,
) -> Optional[dict]:
    pdf_path = get_textbook_pdf_path(textbook_id)
    normalized_bbox = normalize_bbox(crop_bbox)
    if not pdf_path or not normalized_bbox:
        return None

    page_index = get_pdf_page_index(textbook_id, page_number)
    doc = fitz.open(pdf_path)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            return None
        page = doc.load_page(page_index)
        clip = _expanded_rect(page.rect, normalized_bbox)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
        image_bytes = pix.tobytes("png")

        cache_dir = Path(config.DATA_DIR) / "screenshot_crops"
        cache_dir.mkdir(parents=True, exist_ok=True)
        name_hash = hashlib.sha256(
            f"{textbook_id}|{page_number}|{hash_bbox(normalized_bbox)}|{image_hash}".encode("utf-8")
        ).hexdigest()[:24]
        crop_path = cache_dir / f"{_safe_name(textbook_id)}_p{page_number}_{name_hash}.png"
        crop_path.write_bytes(image_bytes)

        return {
            "path": str(crop_path),
            "data_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
            "bbox": normalized_bbox,
            "width": pix.width,
            "height": pix.height,
        }
    finally:
        doc.close()


def extract_pdf_text_near_crop(
    textbook_id: str,
    page_number: int,
    crop_bbox: Optional[dict],
    *,
    margin_ratio: float = 0.25,
) -> str:
    pdf_path = get_textbook_pdf_path(textbook_id)
    normalized_bbox = normalize_bbox(crop_bbox)
    if not pdf_path or not normalized_bbox:
        return ""

    page_index = get_pdf_page_index(textbook_id, page_number)
    doc = fitz.open(pdf_path)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            return ""
        page = doc.load_page(page_index)
        clip = _expanded_rect(page.rect, normalized_bbox, margin_ratio=margin_ratio)
        return page.get_text("text", clip=clip).strip()
    finally:
        doc.close()
