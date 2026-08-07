"""Reviewed competition-demo practice assets."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.practice.repository import add_item


MVP_ITEMS_PATH = Path(__file__).resolve().parents[3] / "data" / "practice" / "mvp_items.json"


def seed_demo_items() -> int:
    """Idempotently install the small trusted pool used by the MVP."""

    items = json.loads(MVP_ITEMS_PATH.read_text(encoding="utf-8"))
    for item in items:
        add_item(item)
    return len(items)
