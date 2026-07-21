from typing import List, Optional
from app.db.connection import get_conn


GAOSHU_SECTION_PAGE_OFFSET = 11


def _is_gaoshu_textbook(textbook_id: str) -> bool:
    value = textbook_id or ""
    lowered = value.lower()
    return "gaoshu" in lowered or "高数" in value or "高等数学" in value


def get_section_lookup_page(textbook_id: str, page: int) -> int:
    """Convert rendered PDF page to textbook printed page for section lookup."""
    page_num = int(page or 0)
    if _is_gaoshu_textbook(textbook_id):
        return max(1, page_num - GAOSHU_SECTION_PAGE_OFFSET)
    return page_num


def save_textbook_section(section: dict) -> None:
    """保存单个章节到textbook_sections表"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO textbook_sections
        (id, textbook_id, sequence_id, chapter_num, chapter_name, content, start_page, end_page)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        section['id'],
        section['textbook_id'],
        section['sequence_id'],
        section['chapter_num'],
        section['chapter_name'],
        section['content'],
        section['start_page'],
        section['end_page']
    ))
    conn.commit()
    conn.close()


def get_section_by_page(textbook_id: str, page: int) -> Optional[dict]:
    """根据页码查询章节"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM textbook_sections
        WHERE textbook_id = ? AND start_page <= ? AND end_page >= ?
        ORDER BY start_page DESC
        LIMIT 1
    """, (textbook_id, page, page))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_sections_by_textbook(textbook_id: str) -> List[dict]:
    """获取某教材所有章节"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM textbook_sections
        WHERE textbook_id = ?
        ORDER BY start_page
    """, (textbook_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_page_context(textbook_id: str, page: int, window: int = 0) -> dict:
    """根据页码获取章节上下文"""
    lookup_page = get_section_lookup_page(textbook_id, page)
    section = get_section_by_page(textbook_id, lookup_page)
    if not section:
        return {"error": f"未找到页码 {page} 对应的章节", "requested_page": page, "section_lookup_page": lookup_page}
    return {
        "sequence_id": section["sequence_id"],
        "chapter_num": section["chapter_num"],
        "chapter_name": section["chapter_name"],
        "content": section["content"],
        "start_page": section["start_page"],
        "end_page": section["end_page"],
        "requested_page": page,
        "section_lookup_page": lookup_page
    }
