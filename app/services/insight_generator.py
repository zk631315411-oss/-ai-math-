"""画像洞察生成器：定期用 LLM 生成自然语言学习报告。

缓存策略：24h 内 + 诊断无更新 → 直接返回缓存。否则重新生成。
"""

import json
import re
from datetime import datetime, timedelta


async def generate(user_id: str) -> dict:
    """生成学习洞察报告。返回 { overall_assessment, strengths, weaknesses,
    learning_trend, recommended_focus, recommended_strategy, motivation_message }。"""
    from app.db.math_profile_db import get_math_profile, save_math_profile
    from app.db.knowledge_stages_db import get_stages_summary
    from app.db.question_assessment_db import get_question_assessments
    from app.services.llm_service import llm_service

    profile = get_math_profile(user_id)
    if not profile:
        return _empty_report()

    stages = get_stages_summary(user_id)
    history = get_question_assessments(user_id, limit=5)

    dims = profile.get("dimensions", {})
    dim_summary = ""
    for name, scores in dims.items():
        avg = (scores.get("coverage", 0) + scores.get("radius", 0) + scores.get("technical", 0)) / 3
        dim_summary += f"- {name}: coverage={scores.get('coverage',0)}, radius={scores.get('radius',0)}, technical={scores.get('technical',0)} (avg={avg:.1f})\n"

    history_text = ""
    for h in history:
        dim_deltas = h.get("dimension_deltas", [])
        created = h.get("created_at", "")
        history_text += f"[{created}] {json.dumps(dim_deltas, ensure_ascii=False)}\n"

    prompt = f"""你是一位教育数据分析师。请根据以下学生的学习数据，生成一份学习洞察报告。

## 15 维数学素养画像
{dim_summary}

## 知识阶段分布
{json.dumps(stages, ensure_ascii=False)}

## 诊断历史（最近5条）
{history_text or "暂无"}

## 输出格式（严格 JSON）
{{
  "overall_assessment": "总体评价（100字内）",
  "strengths": [{{"dimension": "维度名", "evidence": "证据（50字内）"}}],
  "weaknesses": [{{"dimension": "维度名", "root_cause": "根因（50字内）", "suggestion": "建议（50字内）"}}],
  "learning_trend": "rising | stable | fluctuating",
  "recommended_focus": ["知识点1", "知识点2"],
  "recommended_strategy": "教学策略建议（50字内）",
  "motivation_message": "鼓励语（30字内）"
}}
"""

    messages = [
        {"role": "system", "content": "你是教育数据分析师。只输出 JSON。"},
        {"role": "user", "content": prompt},
    ]

    try:
        response = await llm_service.chat_async(messages, temperature=0.3)
        report = _parse_json(response)
        if report:
            cache = json.dumps(report, ensure_ascii=False)
            save_math_profile(user_id, insight_cache=cache)
            return report
    except Exception:
        pass
    return _empty_report()


def get_cached_or_generate(user_id: str) -> dict | None:
    """同步检查缓存：24h 内 + 诊断无更新 → 返回缓存。否则返回 None。"""
    from app.db.math_profile_db import get_math_profile

    profile = get_math_profile(user_id)
    if not profile:
        return None

    cache_raw = profile.get("insight_cache", "{}")
    generated_at = profile.get("insight_generated_at")
    last_diagnosed = profile.get("last_diagnosed_at")

    if isinstance(cache_raw, str):
        try:
            cache = json.loads(cache_raw)
        except Exception:
            cache = {}
    elif isinstance(cache_raw, dict):
        cache = cache_raw
    else:
        cache = {}

    if not cache or not generated_at:
        return None

    # 检查是否超过 24 小时
    if isinstance(generated_at, str):
        try:
            gen_time = datetime.fromisoformat(generated_at)
        except Exception:
            return None
    else:
        gen_time = generated_at

    if datetime.utcnow() - gen_time > timedelta(hours=24):
        return None

    # 检查是否有新的诊断
    if last_diagnosed:
        if isinstance(last_diagnosed, str):
            try:
                diag_time = datetime.fromisoformat(last_diagnosed)
            except Exception:
                diag_time = None
        else:
            diag_time = last_diagnosed
        if diag_time and diag_time > gen_time:
            return None

    return cache


def _parse_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None


def _empty_report() -> dict:
    return {
        "overall_assessment": "暂无足够数据生成学习洞察。请多进行几次问答和练习后再查看。",
        "strengths": [],
        "weaknesses": [],
        "learning_trend": "stable",
        "recommended_focus": [],
        "recommended_strategy": "继续保持学习节奏",
        "motivation_message": "每一次提问都是进步，继续加油！",
    }
