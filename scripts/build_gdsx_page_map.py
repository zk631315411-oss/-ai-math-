"""
高等数学 页码→章节映射生成器
=============================
MD 标题中内嵌了每节的起始页码（格式：## 第X节 Title PAGE）。直接提取入库。

用法：python scripts/build_gdsx_page_map.py --volume 1
"""
import io, re, sys, uuid, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import fitz
except ImportError:
    fitz = None

CN_NUM = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
          '十一':11,'十二':12,'十三':13}
NUM_CN = {v: k for k, v in CN_NUM.items()}

VOLUME_1 = {
    "textbook_id": "高数上-黄立宏",
    "pdf_path": "d:/ai-math/frontend/public/高等数学第二版上册黄立宏主编.pdf",
    "md_path": "D:/ai-math/比赛相关文件与文件夹/揭榜挂帅/教材库/高等数学/高等数学上册_structured.md",
    "total_pages": 284,
    "answer_page": 274,
}

VOLUME_2 = {
    "textbook_id": "高数下-黄立宏",
    "pdf_path": "d:/ai-math/frontend/public/高等数学第二版下册黄立宏主编.pdf",
    "md_path": "D:/ai-math/比赛相关文件与文件夹/揭榜挂帅/教材库/高等数学/高等数学下册_structured.md",
    "total_pages": 274,
    "answer_page": 264,
}


def parse_md_with_pages(md_path: str):
    """从目录页解析每节的页码和标题。"""
    with open(md_path, encoding='utf-8') as f:
        lines = f.readlines()

    sections = []
    ch = 0
    current = None

    for i, line in enumerate(lines):
        line_s = line.strip()

        # 正文区的章标题形如 "# 第一章"，从这里开始后不再解析目录。
        if re.match(r'^#\s*第[一二三四五六七八九十]+章\s*$', line_s):
            if current:
                sections.append(current)
            break

        # 章标题：# 第一章 xxx
        m = re.match(r'^#\s*第([一二三四五六七八九十]+)章\s+(.+)', line_s)
        if m:
            if current:
                sections.append(current)
            ch = CN_NUM.get(m.group(1), 0)
            current = None
            continue

        # 节标题：## 第X节 Title PAGE / ## *第X节 Title PAGE
        m = re.match(r'^##\s*\*?\s*第([一二三四五六七八九十]+)节\s+(.+?)\s*(\d+)\s*$', line_s)
        if m and ch:
            if current:
                current['end_line'] = i
                sections.append(current)
            sec = CN_NUM.get(m.group(1), 0)
            title = m.group(2).strip()
            page = int(m.group(3))
            current = {
                'chapter_num': f'{ch}.{sec}',
                'title': title,
                'start_page': page,
            }

    if current:
        sections.append(current)

    deduped = []
    seen = set()
    for s in sections:
        key = (s['chapter_num'], s['start_page'], s['title'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)
    sections = deduped

    # 计算结束页 = 下一节起始页 - 1
    for i, s in enumerate(sections):
        if i < len(sections) - 1:
            s['end_page'] = sections[i + 1]['start_page'] - 1
        else:
            # 最后一节：取 PDF 总页数
            s['end_page'] = s['start_page'] + 30  # 临时值，后面用 PDF 实际页数覆盖

    return sections


def parse_md_body_sections(md_path: str):
    """从正文区解析每节的完整内容。

    高数 MD 前半段是目录，目录节标题含页码；正文区的小节通常是两行：
      ## 第一节
      ## 变量与函数
    因此正文内容不能直接从目录标题切分。
    """
    with open(md_path, encoding='utf-8') as f:
        lines = f.readlines()

    sections = []
    current_chapter = 0
    current = None
    in_body = False
    answer_start_line = None
    seen_chapters = set()

    def finish(end_line: int):
        if current:
            current['end_line'] = end_line
            sections.append(current.copy())

    for i, line in enumerate(lines):
        line_s = line.strip()

        if in_body and re.match(r'^#{1,3}\s*习题参考答案与提示', line_s):
            answer_start_line = i
            finish(i)
            current = None
            break

        m_ch = re.match(r'^#\s*第([一二三四五六七八九十]+)章(?:\s*.*)?$', line_s)
        if m_ch:
            chapter_num = CN_NUM.get(m_ch.group(1), 0)
            if chapter_num not in seen_chapters:
                seen_chapters.add(chapter_num)
                continue

            in_body = True
            finish(i)
            current = None
            current_chapter = chapter_num
            continue

        if not in_body or not current_chapter:
            continue

        m_sec = re.match(r'^#{2,3}\s*\*?\s*第([一二三四五六七八九十]+)节\s*$', line_s)
        if not m_sec:
            continue

        sec = CN_NUM.get(m_sec.group(1), 0)
        if not sec:
            continue

        # 正文节标题下一条非空二级标题是小节名。
        title = ""
        title_idx = None
        for j in range(i + 1, min(i + 8, len(lines))):
            candidate = lines[j].strip()
            if not candidate:
                continue
            m_title = re.match(r'^#{2,3}\s+(.+?)\s*$', candidate)
            if m_title and not re.match(r'^\*?\s*第[一二三四五六七八九十]+节', m_title.group(1)):
                title = m_title.group(1).strip()
                title_idx = j
            break

        if not title or title_idx is None:
            continue

        finish(i)
        current = {
            'chapter_num': f'{current_chapter}.{sec}',
            'title': title,
            'start_line': i,
        }

    if current:
        finish(len(lines))

    body_sections = {}
    for s in sections:
        content = ''.join(lines[s['start_line']:s['end_line']]).strip()
        body_sections[s['chapter_num']] = {
            'title': s['title'],
            'content': content,
            'start_line': s['start_line'] + 1,
            'end_line': s['end_line'],
        }

    answer_content = ""
    if answer_start_line is not None:
        answer_content = ''.join(lines[answer_start_line:]).strip()

    return body_sections, answer_content


def get_pdf_page_count(pdf_path: str) -> int:
    if fitz is None:
        raise RuntimeError("PyMuPDF 未安装，无法读取 PDF 总页数")
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--volume', type=int, choices=[1, 2], required=True)
    args = parser.parse_args()

    cfg = VOLUME_1 if args.volume == 1 else VOLUME_2

    print(f'=== {cfg["textbook_id"]} ===')

    # 1. 从 MD 提取节信息（含页码）
    sections = parse_md_with_pages(cfg['md_path'])
    print(f'节数: {len(sections)}')

    # 1b. 从正文区提取完整小节内容
    body_sections, answer_content = parse_md_body_sections(cfg['md_path'])
    print(f'正文节数: {len(body_sections)}')

    # 2. PDF 总页数
    try:
        total_pages = get_pdf_page_count(cfg['pdf_path'])
    except Exception as e:
        total_pages = cfg.get('total_pages')
        if not total_pages:
            raise
        print(f'PDF 总页数读取失败，使用配置值 {total_pages}: {e}')
    print(f'PDF 总页数: {total_pages}')

    # 3. 修正最后几节的 end_page
    for i, s in enumerate(sections):
        if s['end_page'] > total_pages:
            s['end_page'] = total_pages

    answer_page = cfg['answer_page']
    answer_end_page = total_pages
    if sections:
        sections[-1]['end_page'] = min(sections[-1]['end_page'], answer_page - 1)

    # 4. 入库
    from app.db.connection import init_db
    from app.db.textbook_section_db import save_textbook_section

    init_db()

    # 先删旧数据
    from app.db.connection import get_conn
    db = get_conn()
    db.execute("DELETE FROM textbook_sections WHERE textbook_id = ?", (cfg['textbook_id'],))
    db.commit()

    for s in sections:
        parts = s['chapter_num'].split('.')
        sequence_id = f'V1-C{int(parts[0]):02d}-S{int(parts[1]):02d}'
        body = body_sections.get(s['chapter_num'])
        if not body:
            print(f'  WARN 正文缺失: {s["chapter_num"]} {s["title"]}')
            content = ''
            title = s['title']
        else:
            content = body['content']
            title = body['title']

        section_data = {
            'id': str(uuid.uuid4()),
            'textbook_id': cfg['textbook_id'],
            'sequence_id': sequence_id,
            'chapter_num': s['chapter_num'],
            'chapter_name': title,
            'content': content,
            'start_page': s['start_page'],
            'end_page': s['end_page'],
        }
        save_textbook_section(section_data)
        print(f'  {s["chapter_num"]:6s} p.{s["start_page"]:3d}-{s["end_page"]:3d}  {title}  len={len(content)}')

    if answer_content:
        save_textbook_section({
            'id': str(uuid.uuid4()),
            'textbook_id': cfg['textbook_id'],
            'sequence_id': 'V1-C00-S00',
            'chapter_num': '答案区',
            'chapter_name': '习题参考答案与提示',
            'content': answer_content,
            'start_page': answer_page,
            'end_page': answer_end_page,
        })
        print(f'  {"答案区":6s} p.{answer_page:3d}-{answer_end_page:3d}  习题参考答案与提示  len={len(answer_content)}')

    print(f'\n=== {cfg["textbook_id"]} 入库完成: {len(sections) + (1 if answer_content else 0)} 条记录 ===')


if __name__ == '__main__':
    main()
