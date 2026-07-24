from typing import List, Optional

from app.db.connection import get_conn


GAOSHU_SECTION_PAGE_OFFSET = 11


def parse_source_code(source_code: str) -> dict:
    """将 KG source_code 解析为人类可读的教材定位信息。
    
    输入格式: "gaodai_shang:C03:S05:U01"
    输出: {"textbook_name": "高等代数·上册", "chapter": "第3章", "section": "第5节", "unit": "第1单元", "display": "高等代数·上册 > 第3章 > 第5节 > 第1单元"}
    """
    if not source_code:
        return {}
    
    parts = source_code.split(":")
    if len(parts) < 2:
        return {"display": source_code}
    
    book_code = parts[0]
    
    # 教材名称映射
    book_names = {
        "gaodai_shang": "高等代数·上册",
        "gaodai_xia": "高等代数·下册",
        "gaoshu_shang": "高等数学·上册",
        "gaoshu_xia": "高等数学·下册",
    }
    textbook_name = book_names.get(book_code, book_code)
    
    result = {"textbook_name": textbook_name}
    display_parts = [textbook_name]
    
    for part in parts[1:]:
        if part.startswith("C"):
            num = part[1:].lstrip("0")
            result["chapter"] = f"第{num}章"
            display_parts.append(result["chapter"])
        elif part.startswith("S"):
            num = part[1:].lstrip("0")
            result["section"] = f"第{num}节"
            display_parts.append(result["section"])
        elif part.startswith("U"):
            num = part[1:].lstrip("0")
            result["unit"] = f"第{num}单元"
            display_parts.append(result["unit"])
        elif part.startswith("T"):
            num = part[1:].lstrip("0")
            result["topic"] = f"主题{num}"
            display_parts.append(result["topic"])
    
    result["display"] = " > ".join(display_parts)
    return result


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
