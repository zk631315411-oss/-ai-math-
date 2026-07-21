from pathlib import Path
from typing import Optional

from app.config import config


TEXTBOOK_ASSETS = {
    "高代上-丘维声": {
        "pdf": "frontend/public/gaodai_vol1.pdf",
        "page_offset": 0,
    },
    "高代下-丘维声": {
        "pdf": "frontend/public/高等代数下册_丘维声.pdf",
        "page_offset": 0,
    },
    "高数上-黄立宏": {
        "pdf": "frontend/public/高等数学第二版上册黄立宏主编.pdf",
        "page_offset": 0,
    },
    "高数下-黄立宏": {
        "pdf": "frontend/public/高等数学第二版下册黄立宏主编.pdf",
        "page_offset": 0,
    },
}


def get_textbook_pdf_path(textbook_id: str) -> Optional[Path]:
    asset = TEXTBOOK_ASSETS.get(textbook_id)
    if not asset:
        return None
    path = config.BASE_DIR / asset["pdf"]
    return path if path.exists() else None


def get_pdf_page_index(textbook_id: str, page_number: int) -> int:
    asset = TEXTBOOK_ASSETS.get(textbook_id, {})
    offset = int(asset.get("page_offset", 0))
    return max(0, page_number - 1 + offset)
