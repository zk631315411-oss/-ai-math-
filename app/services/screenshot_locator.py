import math
import re
from difflib import SequenceMatcher
from typing import Optional

from app.services.pdf_cropper import extract_pdf_text_near_crop


TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z]+|\\[A-Za-z]+|\d+(?:\.\d+)?|[∫∬∭∑∏√∞αβγθλμσφωΩΣΔ∂±×÷≤≥≈≠]")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def _chunks(full_context: str, max_len: int = 900, overlap: int = 120) -> list[str]:
    text = (full_context or "").strip()
    if not text:
        return []

    pieces = re.split(r"(?=\n#{1,6}\s+|\n(?:例|定义|定理|性质|证明|解) ?\d*[\.:：])", text)
    chunks: list[str] = []
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if len(piece) <= max_len:
            chunks.append(piece)
            continue
        start = 0
        while start < len(piece):
            chunks.append(piece[start:start + max_len])
            start += max_len - overlap
    return chunks


def _score(query_tokens: list[str], query_text: str, chunk: str) -> float:
    if not query_tokens or not chunk:
        return 0.0

    chunk_tokens = set(_tokens(chunk))
    if not chunk_tokens:
        return 0.0

    query_set = set(query_tokens)
    keyword_score = len(query_set & chunk_tokens) / max(1, len(query_set))

    formula_tokens = {t for t in query_set if t.startswith("\\") or len(t) == 1 and not t.isalnum()}
    formula_score = len(formula_tokens & chunk_tokens) / max(1, len(formula_tokens)) if formula_tokens else 0.0

    number_tokens = {t for t in query_set if any(ch.isdigit() for ch in t)}
    number_score = len(number_tokens & chunk_tokens) / max(1, len(number_tokens)) if number_tokens else 0.0

    short_query = re.sub(r"\s+", "", query_text)[:500]
    short_chunk = re.sub(r"\s+", "", chunk)[:900]
    fuzzy_score = SequenceMatcher(None, short_query, short_chunk).ratio() if short_query and short_chunk else 0.0

    return (
        keyword_score * 0.45
        + formula_score * 0.25
        + number_score * 0.15
        + fuzzy_score * 0.15
    )


def locate_screenshot_context(
    *,
    textbook_id: str,
    page_number: int,
    crop_bbox: Optional[dict],
    full_context: str,
) -> dict:
    pdf_text = extract_pdf_text_near_crop(textbook_id, page_number, crop_bbox)
    query_tokens = _tokens(pdf_text)
    chunks = _chunks(full_context)

    if not pdf_text or not query_tokens or not chunks:
        return {
            "status": "miss",
            "confidence": 0.0,
            "matched_text": "",
            "signals": {
                "pdf_text_near_crop": pdf_text,
                "keywords": query_tokens[:30],
                "top_candidates": [],
            },
        }

    candidates = []
    for chunk in chunks:
        score = _score(query_tokens, pdf_text, chunk)
        if score > 0:
            candidates.append({"score": score, "text": chunk[:900]})

    candidates.sort(key=lambda item: item["score"], reverse=True)
    top = candidates[0] if candidates else {"score": 0.0, "text": ""}
    second_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
    confidence = min(1.0, top["score"])

    if confidence >= 0.72 and confidence - second_score >= 0.08:
        status = "hit"
    elif confidence >= 0.45:
        status = "weak"
    else:
        status = "miss"

    return {
        "status": status,
        "confidence": round(confidence, 4),
        "matched_text": top["text"] if status != "miss" else "",
        "signals": {
            "pdf_text_near_crop": pdf_text[:1200],
            "keywords": query_tokens[:30],
            "top_candidates": [
                {
                    "score": round(c["score"], 4),
                    "text": c["text"][:240],
                }
                for c in candidates[:3]
                if math.isfinite(c["score"])
            ],
        },
    }
