import json
from datetime import datetime
from typing import List, Optional
from app.models.schemas import Textbook, Chapter, Section, TextbookResponse
from app.db.connection import get_conn


def save_textbook(textbook: Textbook) -> None:
    conn = get_conn()
    cursor = conn.cursor()

    chapters_json = json.dumps([c.model_dump() for c in textbook.chapters], ensure_ascii=False)

    cursor.execute("""
        INSERT OR REPLACE INTO textbooks (id, name, subject, grade, chapters, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (textbook.id, textbook.name, textbook.subject, textbook.grade,
          chapters_json, textbook.created_at))

    conn.commit()
    conn.close()


def get_textbook(textbook_id: str) -> Optional[Textbook]:
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM textbooks WHERE id = ?", (textbook_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    chapters_data = json.loads(row["chapters"])
    chapters = [Chapter(**c) for c in chapters_data]

    return Textbook(
        id=row["id"],
        name=row["name"],
        subject=row["subject"],
        grade=row["grade"],
        chapters=chapters,
        created_at=datetime.fromisoformat(row["created_at"])
    )


def list_textbooks() -> List[TextbookResponse]:
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM textbooks ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        chapters_data = json.loads(row["chapters"])
        result.append(TextbookResponse(
            id=row["id"],
            name=row["name"],
            subject=row["subject"],
            grade=row["grade"],
            chapter_count=len(chapters_data),
            created_at=datetime.fromisoformat(row["created_at"])
        ))

    return result


def delete_textbook(textbook_id: str) -> bool:
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM textbooks WHERE id = ?", (textbook_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted
