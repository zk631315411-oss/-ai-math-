import json
import uuid
from typing import Optional

from app.db.connection import get_conn


def _uid() -> str:
    return str(uuid.uuid4())


def get_screenshot_context_cache(cache_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM screenshot_context_cache WHERE id=?",
        (cache_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def find_screenshot_context_cache(
    image_hash: str,
    textbook_id: str,
    page_number: int,
    crop_bbox_hash: str,
    full_context_hash: str,
) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT * FROM screenshot_context_cache
        WHERE image_hash=?
          AND textbook_id=?
          AND page_number=?
          AND crop_bbox_hash=?
          AND full_context_hash=?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (image_hash, textbook_id, page_number, crop_bbox_hash, full_context_hash),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_screenshot_context_cache(
    *,
    image_hash: str,
    textbook_id: str,
    page_number: int,
    crop_bbox: Optional[dict],
    crop_bbox_hash: str,
    full_context_hash: str,
    pdf_crop_path: Optional[str],
    md_match_status: Optional[str],
    md_match_confidence: Optional[float],
    md_match_text: Optional[str],
    locator_signals: Optional[dict],
    vision_model: Optional[str],
) -> str:
    cache_id = _uid()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO screenshot_context_cache (
            id, image_hash, textbook_id, page_number, crop_bbox, crop_bbox_hash,
            full_context_hash, pdf_crop_path, md_match_status, md_match_confidence,
            md_match_text, locator_signals, vision_model
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cache_id,
            image_hash,
            textbook_id,
            page_number,
            json.dumps(crop_bbox, ensure_ascii=False) if crop_bbox else None,
            crop_bbox_hash,
            full_context_hash,
            pdf_crop_path,
            md_match_status,
            md_match_confidence,
            md_match_text,
            json.dumps(locator_signals or {}, ensure_ascii=False),
            vision_model,
        ),
    )
    conn.commit()
    conn.close()
    return cache_id


def update_screenshot_context_cache(
    cache_id: str,
    *,
    vision_summary: Optional[str] = None,
    pdf_crop_path: Optional[str] = None,
) -> None:
    sets = ["updated_at=CURRENT_TIMESTAMP"]
    params = []
    if vision_summary is not None:
        sets.append("vision_summary=?")
        params.append(vision_summary)
    if pdf_crop_path is not None:
        sets.append("pdf_crop_path=?")
        params.append(pdf_crop_path)
    params.append(cache_id)

    conn = get_conn()
    conn.execute(
        f"UPDATE screenshot_context_cache SET {', '.join(sets)} WHERE id=?",
        params,
    )
    conn.commit()
    conn.close()
