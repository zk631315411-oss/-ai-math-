"""
构建教材页码映射词典（支持上下册）
================================
功能：
  1. 解析PDF书签 → 生成节级锚点 + 页码区间
  2. 解析MD正文 → 提取节级标题 + 内容
  3. 按章节编号匹配 → 打包入库 SQLite

用法：
  # 入库上册
  python scripts/build_page_map.py --volume 1

  # 入库下册
  python scripts/build_page_map.py --volume 2

  # 入库两册
  python scripts/build_page_map.py

验证：
  python -c "from app.db.textbook_section_db import get_section_by_page; print(get_section_by_page('高代上-丘维声', 50))"
"""
import io
import re
import sys
import uuid
import argparse
from pathlib import Path

# 设置stdout编码为utf-8（解决Windows GBK问题）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 确保app模块可导入
sys.path.insert(0, str(Path(__file__).parent.parent))

import fitz  # PyMuPDF
from tqdm import tqdm


# ============================================================
# 上册配置
# ============================================================
VOLUME_1 = {
    "textbook_id": "高代上-丘维声",
    "pdf_path": "d:/ai math/高等代数创新教材 上 丘维声_outlined.pdf",
    "md_path": "d:/ai math/structured_高代上.md",
    # 书签页码区间映射：(章节号, 书签页, 结束页)
    # 结束页 = 下一章书签页 - 1
    "section_pages": {
        "1.1": (26, 37), "1.2": (38, 44), "1.3": (45, 51),
        "2.1": (52, 55), "2.2": (56, 60), "2.3": (61, 69),
        "2.4": (70, 84), "2.5": (85, 89), "2.6": (90, 101),
        "3.1": (102, 108), "3.2": (109, 118), "3.3": (119, 126),
        "3.4": (127, 130), "3.5": (131, 140), "3.6": (141, 144),
        "3.7": (145, 151), "3.8": (152, 162),
        "4.1": (163, 177), "4.2": (178, 187), "4.3": (188, 201),
        "4.4": (202, 215), "4.5": (216, 235), "4.6": (236, 250),
        "4.7": (251, 265),
        "5.1": (266, 269), "5.2": (270, 276), "5.3": (277, 285),
        "5.4": (286, 290), "5.5": (291, 303), "5.6": (304, 314),
        "5.7": (315, 336),
        "6.1": (337, 353), "6.2": (354, 361), "6.3": (362, 387),
    },
    "answer_page": 388,  # 答案区起始页
    "answer_end_page": 421,
}

# ============================================================
# 下册配置
# ============================================================
VOLUME_2 = {
    "textbook_id": "高代下-丘维声",
    "pdf_path": "d:/ai math/高等代数创新教材 下 丘维声_outlined.pdf",
    "md_path": "d:/ai math/structured_高代下.md",
    # 从PDF书签提取的节级页码
    "section_pages": {
        # Chapter 7
        "7.1": (15, 25), "7.2": (26, 35), "7.3": (36, 48),
        "7.4": (49, 53), "7.5": (54, 55), "7.6": (60, 74),
        "7.7": (75, 85), "7.8": (86, 99), "7.9": (100, 111),
        "7.10": (112, 124), "7.11": (125, 136), "7.12": (137, 164),
        # Chapter 8
        "8.1": (165, 192), "8.2": (193, 215), "8.3": (216, 227), "8.4": (228, 239),
        # Chapter 9
        "9.1": (240, 251), "9.2": (252, 261), "9.3": (262, 281),
        "9.4": (282, 296), "9.5": (297, 316), "9.6": (317, 340),
        "9.7": (341, 353), "9.8": (354, 381), "9.9": (382, 410), "9.10": (411, 431),
        # Chapter 10
        "10.1": (432, 463), "10.2": (464, 478), "10.3": (479, 489),
        "10.4": (490, 512), "10.5": (513, 553), "10.6": (554, 571), "10.7": (572, 594),
        # Chapter 11
        "11.1": (595, 600), "11.2": (601, 618), "11.3": (619, 624), "11.4": (625, 637),
    },
    "answer_page": 643,  # 答案区起始页
    "answer_end_page": 649,
}


def make_sequence_id(chapter_num: str, version_prefix: str = "V1") -> str:
    """V1-C01-S01 格式"""
    parts = chapter_num.split('.')
    c, s = int(parts[0]), int(parts[1])
    if len(parts) > 2:
        return f"{version_prefix}-C{c:02d}-S{int(parts[1]):02d}"
    return f"{version_prefix}-C{c:02d}-S{s:02d}"


def parse_pdf_sections(pdf_path: str, max_page: int = 999):
    """解析PDF书签，提取节级锚点"""
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()

    sections = []  # [(chapter_num, title, start_page), ...]
    for item in toc:
        level, title, page = item
        if re.match(r'^\d+\.\d+\s+', title) and page < max_page:
            match = re.match(r'^(\d+\.\d+)\s+(.+)', title)
            if match:
                section_num = match.group(1)
                section_title = match.group(2).strip()
                sections.append((section_num, section_title, page))

    doc.close()
    return sections


def parse_md_sections(md_path: str):
    """解析MD正文，提取节级标题 + 内容边界"""
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    chapters = {}  # {chapter_num: (start_line, end_line, title)}

    current_chapter = None
    content_start = None

    for i, line in enumerate(lines):
        if line.startswith('## '):
            title = line[2:].strip()
            # 过滤掉目录条目
            if '..' in title or '……' in title or re.search(r'\([0-9]+\)$', title):
                continue
            # 匹配正文章节：## 7.1 标题
            match = re.match(r'^(\d+\.\d+)\s+(.+)', title)
            if match:
                chapter_num = match.group(1)
                chapter_title = match.group(2).strip()
                # 保存上一个章节的结束行
                if current_chapter and content_start is not None:
                    chapters[current_chapter] = (content_start, i - 1, chapters.get(current_chapter, (None, None, None))[2])
                current_chapter = chapter_num
                content_start = i + 1
                if chapter_num not in chapters:
                    chapters[chapter_num] = (None, None, chapter_title)
                else:
                    chapters[chapter_num] = (chapters[chapter_num][0], chapters[chapter_num][1], chapter_title)

    # 最后一个章节
    if current_chapter and content_start is not None:
        chapters[current_chapter] = (content_start, len(lines) - 1, chapters[current_chapter][2])

    # 清理临时条目
    chapters = {k: v for k, v in chapters.items() if v[0] is not None}

    # 找答案区开始行
    answer_line = None
    answer_title = None
    for i, line in enumerate(lines):
        if line.strip().startswith('# 习题答案') and '提示' in line:
            answer_line = i + 1
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith('# '):
                    answer_title = next_line[2:].strip()
            break

    return chapters, answer_line, len(lines)


def build_page_map_for_volume(volume_config: dict, version_prefix: str = "V1"):
    """为单个分册构建页码映射并入库"""
    textbook_id = volume_config["textbook_id"]
    pdf_path = volume_config["pdf_path"]
    md_path = volume_config["md_path"]
    section_pages = volume_config["section_pages"]
    answer_page = volume_config["answer_page"]
    answer_end_page = volume_config["answer_end_page"]

    print(f"\n{'='*50}")
    print(f"📖 处理教材: {textbook_id}")
    print(f"   PDF: {pdf_path}")
    print(f"   MD: {md_path}")
    print(f"{'='*50}")

    # 1. 解析PDF书签（用于识别节级标题名称）
    pdf_sections = parse_pdf_sections(pdf_path)
    print(f"✅ PDF书签解析完成：{len(pdf_sections)} 个节级锚点")

    # 2. 解析MD章节
    md_chapters, answer_start_line, total_lines = parse_md_sections(md_path)
    print(f"✅ MD正文解析完成：{len(md_chapters)} 个正文章节")

    # 3. 入库
    from app.db.connection import init_db
    from app.db.textbook_section_db import save_textbook_section
    init_db()

    sections_to_save = []

    # 遍历section_pages配置
    for chapter_num, (start_page, end_page) in tqdm(section_pages.items(), desc=f"入库 {textbook_id}"):
        # 查找PDF中的标题
        pdf_title = chapter_num
        for sec_num, title, _ in pdf_sections:
            if sec_num == chapter_num:
                pdf_title = title
                break

        # 查找MD内容
        if chapter_num in md_chapters:
            md_start_line, md_end_line, md_title = md_chapters[chapter_num]
        else:
            print(f"⚠️ 章节 {chapter_num} 在MD中未找到")
            continue

        # 提取MD内容
        with open(md_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        content_lines = all_lines[md_start_line:md_end_line + 1]
        content = "".join(content_lines)

        # 生成sequence_id
        sequence_id = make_sequence_id(chapter_num, version_prefix)

        section_data = {
            "id": str(uuid.uuid4()),
            "textbook_id": textbook_id,
            "sequence_id": sequence_id,
            "chapter_num": chapter_num,
            "chapter_name": pdf_title,
            "content": content,
            "start_page": start_page,
            "end_page": end_page,
        }
        sections_to_save.append(section_data)

    # 答案区
    with open(md_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    answer_content = "".join(all_lines[answer_start_line:])

    answer_section = {
        "id": str(uuid.uuid4()),
        "textbook_id": textbook_id,
        "sequence_id": f"{version_prefix}-C00-S00",
        "chapter_num": "答案区",
        "chapter_name": "习题答案与提示",
        "content": answer_content,
        "start_page": answer_page,
        "end_page": answer_end_page,
    }
    sections_to_save.append(answer_section)

    # 批量入库
    print(f"\n💾 正在入库 {len(sections_to_save)} 条记录...")
    for section in tqdm(sections_to_save, desc="入库"):
        save_textbook_section(section)

    print(f"✅ {textbook_id} 入库完成：{len(sections_to_save)} 条记录")
    return sections_to_save


def verify_volume(textbook_id: str, version_prefix: str = "V1"):
    """验证某分册的入库结果"""
    print(f"\n🔍 验证 {textbook_id}...")

    from app.db.textbook_section_db import get_section_by_page, get_sections_by_textbook

    sections = get_sections_by_textbook(textbook_id)
    print(f"  数据库中共 {len(sections)} 条记录")

    # 随机测试几个页码
    test_cases = {
        "高代上-丘维声": [
            (15, "V1-C01-S01", "第1章第1节"),
            (50, "V1-C01-S03", "第1章第3节"),
            (100, "V1-C02-S06", "第2章第6节"),
            (200, "V1-C04-S03", "第4章第3节"),
            (300, "V1-C05-S05", "第5章第5节"),
            (388, "V1-C00-S00", "答案区"),
        ],
        "高代下-丘维声": [
            (15, "V1-C07-S01", "第7章第1节"),
            (100, "V1-C07-S09", "第7章第9节"),
            (200, "V1-C08-S01", "第8章第1节"),
            (300, "V1-C09-S05", "第9章第5节"),
            (450, "V1-C10-S01", "第10章第1节"),
            (643, "V1-C00-S00", "答案区"),
        ],
    }

    test_pages = test_cases.get(textbook_id, [])
    all_ok = True
    for page, expected_seq, desc in test_pages:
        section = get_section_by_page(textbook_id, page)
        if section:
            if section['sequence_id'] == expected_seq:
                print(f"  ✅ 页码 {page} → {section['sequence_id']} ({desc})")
            else:
                print(f"  ❌ 页码 {page} → {section['sequence_id']} (期望: {expected_seq})")
                all_ok = False
        else:
            print(f"  ❌ 页码 {page} → 未找到")
            all_ok = False

    if all_ok:
        print(f"  🎉 {textbook_id} 验证通过！")
    else:
        print(f"  ⚠️ {textbook_id} 部分验证失败")

    return all_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="构建教材页码映射词典")
    parser.add_argument("--volume", type=int, choices=[1, 2], default=None,
                        help="指定入库哪个分册（1=上册，2=下册），默认入库两册")
    args = parser.parse_args()

    if args.volume == 1:
        build_page_map_for_volume(VOLUME_1, "V1")
        verify_volume("高代上-丘维声", "V1")
    elif args.volume == 2:
        build_page_map_for_volume(VOLUME_2, "V2")
        verify_volume("高代下-丘维声", "V2")
    else:
        # 入库两册
        build_page_map_for_volume(VOLUME_1, "V1")
        verify_volume("高代上-丘维声", "V1")
        print()
        build_page_map_for_volume(VOLUME_2, "V2")
        verify_volume("高代下-丘维声", "V2")