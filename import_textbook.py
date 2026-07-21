"""
导入教材到SQLite（向量化已废弃，ChromaDB链路已斩断）
用法: python import_textbook.py <markdown文件路径> [--force]
"""
import sys
import re
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import config, TEXTBOOK_DIR
from app.models.schemas import Textbook, Chapter, Section
from app.db.textbook_db import save_textbook, list_textbooks, delete_textbook


def parse_markdown_content(text: str):
    """解析Markdown教材文本"""
    chapters = []
    current_chapter = None
    current_section = None
    current_content = []

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("!["):
            continue

        if line.startswith("# "):
            if current_chapter:
                if current_section:
                    if current_content:
                        current_section.content = "\n".join(current_content).strip()
                        current_chapter.sections.append(current_section)
                elif current_content:
                    default_section = Section(
                        id=str(uuid.uuid4()),
                        title="内容",
                        content="\n".join(current_content).strip()
                    )
                    current_chapter.sections.append(default_section)
                chapters.append(current_chapter)

            chapter_id = str(uuid.uuid4())
            current_chapter = Chapter(id=chapter_id, title=line[2:].strip(), sections=[])
            current_section = None
            current_content = []

        elif line.startswith("## "):
            if current_section and current_chapter:
                if current_content:
                    current_section.content = "\n".join(current_content).strip()
                    current_chapter.sections.append(current_section)
                current_content = []
            section_id = str(uuid.uuid4())
            current_section = Section(id=section_id, title=line[3:].strip(), content="")

        elif current_section:
            if line:
                current_content.append(line)
        elif current_chapter:
            if line:
                current_content.append(line)

    if current_chapter:
        if current_section and current_content:
            current_section.content = "\n".join(current_content).strip()
            current_chapter.sections.append(current_section)
        elif current_content:
            default_section = Section(id=str(uuid.uuid4()), title="内容", content="\n".join(current_content).strip())
            current_chapter.sections.append(default_section)
        chapters.append(current_chapter)

    if not chapters:
        chapters.append(Chapter(
            id=str(uuid.uuid4()),
            title="全文",
            sections=[Section(id=str(uuid.uuid4()), title="内容", content=text)]
        ))
    return chapters


def import_textbook(md_file_path: str, force: bool = False):
    """导入教材到SQLite"""
    config.ensure_dirs()

    md_path = Path(md_file_path)
    if not md_path.exists():
        print(f"文件不存在: {md_file_path}")
        return

    print(f"读取教材: {md_path.name}")
    text = md_path.read_text(encoding="utf-8")
    textbook_name = md_path.stem

    existing = [t for t in list_textbooks() if t.name == textbook_name]
    if existing and not force:
        print(f"教材 '{textbook_name}' 已存在，如需重新导入请使用 --force 参数")
        return

    if existing and force:
        old_id = existing[0].id
        print(f"删除旧教材数据: {old_id}")
        delete_textbook(old_id)

    textbook_id = str(uuid.uuid4())

    chapters = parse_markdown_content(text)
    print(f"解析到 {len(chapters)} 个章节")

    textbook = Textbook(
        id=textbook_id,
        name=textbook_name,
        subject="高等代数",
        grade="大学",
        chapters=chapters,
        created_at=datetime.now()
    )

    save_textbook(textbook)
    print("已保存到SQLite")

    print(f"\n导入完成!")
    print(f"教材ID: {textbook_id}")
    print(f"教材名称: {textbook_name}")
    print(f"章节数: {len(chapters)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 1:
        print(__doc__)
        sys.exit(1)

    import_textbook(args[0], force=force)
