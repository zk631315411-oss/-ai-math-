from pathlib import Path
from typing import Optional

from app.config import config
from app.textbooks import textbook_spec


def get_textbook_pdf_path(textbook_id: str) -> Optional[Path]:
    try:
        asset = textbook_spec(textbook_id)
    except ValueError:
        return None
    path = config.BASE_DIR / asset.pdf_path
    return path if path.exists() else None


def get_pdf_page_index(textbook_id: str, page_number: int) -> int:
    try:
        offset = textbook_spec(textbook_id).page_offset
    except ValueError:
        offset = 0
    return max(0, page_number - 1 + offset)
