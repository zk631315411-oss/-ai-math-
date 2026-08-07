"""Canonical textbook identity and metadata registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path


class TextbookId(str, Enum):
    GAODAI_SHANG = "gaodai_shang"
    GAODAI_XIA = "gaodai_xia"
    GAOSHU_SHANG = "gaoshu_shang"
    GAOSHU_XIA = "gaoshu_xia"


@dataclass(frozen=True)
class TextbookSpec:
    id: TextbookId
    display_name: str
    subject: str
    volume: int
    pdf_path: str
    neo4j_prefix: str
    page_image_base: str = ""
    page_count: int = 0
    page_width: int = 0
    page_height: int = 0
    page_offset: int = 0


CANONICAL_TEXTBOOK_IDS = frozenset(item.value for item in TextbookId)


def _load_registry() -> dict[TextbookId, TextbookSpec]:
    path = Path(__file__).resolve().parents[1] / "shared/textbooks.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    ids = {str(row.get("id") or "") for row in rows}
    if ids != CANONICAL_TEXTBOOK_IDS:
        raise RuntimeError("shared textbook registry does not match TextbookId")
    return {
        TextbookId(row["id"]): TextbookSpec(
            id=TextbookId(row["id"]),
            display_name=row["display_name"],
            subject=row["subject"],
            volume=int(row["volume"]),
            pdf_path=row["pdf_path"],
            neo4j_prefix=row["neo4j_prefix"],
            page_image_base=row.get("page_image_base", ""),
            page_count=int(row.get("page_count", 0)),
            page_width=int(row.get("page_width", 0)),
            page_height=int(row.get("page_height", 0)),
            page_offset=int(row.get("page_offset", 0)),
        )
        for row in rows
    }


TEXTBOOKS = _load_registry()


def canonical_textbook_id(value: str | TextbookId) -> str:
    text = value.value if isinstance(value, TextbookId) else str(value or "")
    if text not in CANONICAL_TEXTBOOK_IDS:
        raise ValueError(f"unknown textbook_id: {text}")
    return text


def textbook_spec(value: str | TextbookId) -> TextbookSpec:
    return TEXTBOOKS[TextbookId(canonical_textbook_id(value))]


def section_node_id(textbook_id: str | TextbookId, sequence_id: str,
                    *, default_chapter: str = "C01", default_section: str = "S01") -> str:
    canonical = canonical_textbook_id(textbook_id)
    parts = (sequence_id or "").split("-")
    chapter = next((part for part in parts if part.startswith("C")), default_chapter)
    section = next((part for part in parts if part.startswith("S")), default_section)
    unit = next((part for part in parts if part.startswith("U")), "")
    base = f"{canonical}:{chapter}:{section}"
    return f"{base}:{unit}" if unit else base


def cumulative_textbook_ids(textbook_id: str | TextbookId) -> list[str]:
    canonical = canonical_textbook_id(textbook_id)
    if canonical == TextbookId.GAODAI_XIA.value:
        return [TextbookId.GAODAI_SHANG.value, canonical]
    if canonical == TextbookId.GAOSHU_XIA.value:
        return [TextbookId.GAOSHU_SHANG.value, canonical]
    return [canonical]


def subject_display_name(textbook_id: str | TextbookId) -> str:
    return "高等数学" if textbook_spec(textbook_id).subject == "gaoshu" else "高等代数"
