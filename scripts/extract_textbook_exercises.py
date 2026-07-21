"""
一次性脚本：从教材 MD 提取例题/习题 → LLM 标注难度 → 入库 exercise_bank。

用法: python scripts/extract_textbook_exercises.py
"""
import sys, os, re, json, sqlite3, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "learning.db")

def parse_examples(content: str) -> list[dict]:
    """从 MD 内容中提取 ##### 例X / ##### 习题X 块。"""
    results = []
    # 匹配 ##### 例X 或 ##### 习题X 或 **例X** 开头的块
    blocks = re.split(r"\n(?=#####\s*(例|习题|例題))", content)
    for block in blocks[1:]:  # 跳过第一个（标题之前的文本）
        block = block.strip()
        if not block:
            continue
        # 题目 = 第一段（例X 标题行 + 紧跟的文本，直到"证明"/"解"/"答"）
        lines = block.split("\n")
        # 找"证明"/"解"/"答"的位置
        answer_start = None
        for i, line in enumerate(lines):
            if re.match(r"^(证明|解|答)[\s:：]", line) or line.strip() in ("证明", "解", "答"):
                answer_start = i
                break
        if answer_start is None:
            # 没有显式解答标记，尝试以空行或下一个 ##### 为界
            # 跳过这种不完整的块
            continue
        question = "\n".join(lines[:answer_start]).strip()
        # 去掉 ##### 例X 标题行
        question = re.sub(r"^#####\s*例\S*\s*\n?", "", question).strip()
        question = re.sub(r"^#####\s*习题\S*\s*\n?", "", question).strip()
        answer = "\n".join(lines[answer_start:]).strip()
        if len(question) > 20 and len(answer) > 10:
            results.append({"question": question, "answer": answer})
    return results


def label_exercise(question: str, chapter_name: str, concepts: list[str]) -> dict:
    """用 LLM 标注难度和阶段。"""
    from app.services.llm_service import llm_service

    prompt = f"""你是数学教育专家。评估以下题目的难度和适合的认知阶段。

题目: {question[:500]}
所在章节: {chapter_name}
相关概念: {", ".join(concepts[:10])}

输出 JSON:
{{
  "difficulty": "basic" | "variation" | "comprehensive",
  "target_stage": 1-5,
  "stage_reason": "简短理由（20字内）"
}}

阶段参考: 1=概念辨析 2=标准计算 3=变式应用 4=综合证明 5=拓展探究"""

    messages = [
        {"role": "system", "content": "只输出 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        resp = llm_service.chat(messages, use_profile=True, temperature=0.3,
                                response_format={"type": "json_object"})
        text = resp.choices[0].message.content
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f"  LLM error: {e}")
    return {"difficulty": "basic", "target_stage": 2, "stage_reason": "默认"}


def main():
    from app.db.connection import init_db
    init_db()

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # 获取所有 section
    c.execute("SELECT DISTINCT sequence_id, chapter_name, content FROM textbook_sections ORDER BY sequence_id")
    sections = c.fetchall()
    print(f"Found {len(sections)} sections\n")

    # Deduplicate: keep only the first section per sequence_id with content
    seen = set()
    unique_sections = []
    for seq_id, name, content in sections:
        if seq_id not in seen and content:
            seen.add(seq_id)
            unique_sections.append((seq_id, name, content))
    sections = unique_sections
    print(f"After dedup: {len(sections)} sections\n")

    # 获取 Neo4j 概念列表（可选）
    concepts_map = {}
    try:
        from neo4j import GraphDatabase
        from app.config import config
        driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        with driver.session() as session:
            for seq_id, _, _ in sections:
                r = session.run("""
                    MATCH (s:Section)<-[:TEACH_IN]-(c:Concept)
                    WHERE s.sequence_id STARTS WITH $seq
                    RETURN c.id LIMIT 20
                """, seq=seq_id)
                concepts_map[seq_id] = [rec[0] for rec in r]
        driver.close()
        print("Neo4j concepts loaded")
    except Exception as e:
        print(f"Neo4j unavailable: {e}")
        for seq_id, _, _ in sections:
            concepts_map[seq_id] = []

    # 清空旧 textbook 数据
    c.execute("DELETE FROM exercise_bank WHERE source='textbook'")
    conn.commit()

    total = 0
    counter = [0]  # mutable counter for unique IDs
    for seq_id, chapter_name, content in sections:
        examples = parse_examples(content)
        if not examples:
            continue
        concepts = concepts_map.get(seq_id, [])
        print(f"{seq_id} ({chapter_name}): {len(examples)} examples")

        for i, ex in enumerate(examples):
            label = label_exercise(ex["question"], chapter_name, concepts)
            # 构建提示（从答案中提取关键步骤）
            steps = [s.strip() for s in ex["answer"].split("\n") if len(s.strip()) > 10][:3]
            hints = steps if steps else ["仔细审题", "回顾相关定义", "尝试代入验证"]

            counter[0] += 1
            eid = f"tb_{counter[0]:04d}"
            conn.execute(
                """INSERT INTO exercise_bank
                   (id, user_id, topic, difficulty, target_stage, question, answer,
                    verification, hints, computable, source, sequence_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (eid, "__system__", chapter_name,
                 label.get("difficulty", "basic"), label.get("target_stage", 2),
                 ex["question"], ex["answer"], "",
                 json.dumps(hints, ensure_ascii=False), "{}",
                 "textbook", seq_id),
            )
            total += 1
            time.sleep(0.3)  # 限流

        conn.commit()
        print(f"  → {len(examples)} inserted")

    conn.close()
    print(f"\nDone: {total} exercises extracted")


if __name__ == "__main__":
    main()
