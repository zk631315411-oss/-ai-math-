"""
LLM 模型切换验证测试

验证 QA_LLM (qwen3.5-plus) 和 PROFILE_LLM (qwen-flash) 在新模型下各调用路径正常工作。
"""
import sys
import os
import asyncio
import base64
import io
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []


def report(name: str, ok: bool, detail: str = ""):
    tag = "PASS" if ok else "FAIL"
    msg = f"[{tag}] {name}"
    if detail:
        msg += f"  → {detail[:120]}"
    print(msg)
    results.append((name, ok, detail[:200]))


# ─── 生成简单测试图片 (白色背景 + 黑色公式文字) ───
def make_test_image_base64() -> str:
    """生成一张简单图片的 base64 data URI"""
    # 最小 PNG: 1x1 白色像素, 用于验证多模态 API 通路
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (200, 80), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 30), "det(A - lambda I) = 0", fill="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        # PIL 未安装时用最小 PNG (1x1 白色)
        # 这是一个有效的 1x1 白色 PNG 的 base64
        return (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42m"
            "P8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        )


# ============================================================
# Test 1: QA_LLM 非流式文字问答
# ============================================================
def test_qa_chat_non_streaming():
    """测试 llm_service.chat() — QA_LLM 非流式"""
    from app.services.llm_service import llm_service

    if not llm_service.is_qa_available():
        report("1. QA非流式文字", False, "QA_LLM client 未初始化")
        return

    try:
        messages = [
            {"role": "user", "content": "请用一句话解释什么是矩阵的特征值。仅输出答案，不要多余内容。"}
        ]
        response = llm_service.chat(messages, temperature=0.3)
        answer = response.choices[0].message.content
        if answer and len(answer) > 5:
            report("1. QA非流式文字", True, answer)
        else:
            report("1. QA非流式文字", False, f"回答过短: {answer}")
    except Exception as e:
        report("1. QA非流式文字", False, str(e))


# ============================================================
# Test 2: QA_LLM 流式文字问答 (含 thinking)
# ============================================================
def test_qa_chat_streaming():
    """测试 llm_service.stream_chat() — QA_LLM 流式 + thinking"""
    from app.services.llm_service import llm_service

    if not llm_service.is_qa_available():
        report("2. QA流式文字", False, "QA_LLM client 未初始化")
        return

    try:
        messages = [
            {"role": "user", "content": "计算 2x+3=7 的解，仅输出 x 的值。"}
        ]
        stream = llm_service.stream_chat(messages, enable_thinking=True)

        content_chunks = []
        thinking_chunks = []

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta:
                continue

            # 捕获思考内容
            reasoning = getattr(delta, 'reasoning_content', None)
            if reasoning:
                thinking_chunks.append(reasoning)

            # 捕获正文内容
            if delta.content:
                content_chunks.append(delta.content)

        full_content = "".join(content_chunks)
        full_thinking = "".join(thinking_chunks)

        has_content = len(full_content.strip()) > 0
        has_thinking = len(full_thinking.strip()) > 0

        if has_content:
            detail = f"content={full_content[:60]}"
            if has_thinking:
                detail += f", thinking={len(full_thinking)}chars"
            else:
                detail += ", thinking=无(模型可能未开启或返回在content中)"
            report("2. QA流式文字", True, detail)
        else:
            report("2. QA流式文字", False, "流式输出无内容")
    except Exception as e:
        report("2. QA流式文字", False, str(e))


# ============================================================
# Test 3: QA_LLM 多模态截图问答
# ============================================================
def test_qa_multimodal():
    """测试 MultiModalConversation.call() — QA_LLM 多模态"""
    from app.config import config
    import dashscope
    from dashscope import MultiModalConversation

    dashscope.api_key = config.QA_LLM_API_KEY

    img_b64 = make_test_image_base64()

    try:
        response = MultiModalConversation.call(
            model=config.QA_LLM_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"image": f"data:image/png;base64,{img_b64}"},
                    {"text": "这张图片里有数学公式吗？只回答是或否。"}
                ]
            }],
            stream=False
        )

        if response.status_code == 200:
            answer = response.output['choices'][0]['message']['content'][0]['text']
            report("3. QA多模态", True, answer)
        else:
            report("3. QA多模态", False, f"HTTP {response.status_code}: {response.message}")
    except Exception as e:
        report("3. QA多模态", False, str(e))


# ============================================================
# Test 4: PROFILE_LLM 同步 JSON 模式
# ============================================================
def test_profile_chat_json():
    """测试 llm_service.chat(use_profile=True) — PROFILE_LLM JSON 输出"""
    from app.services.llm_service import llm_service

    if not llm_service.is_profile_available():
        report("4. Profile同步JSON", False, "PROFILE_LLM client 未初始化")
        return

    try:
        messages = [
            {"role": "system", "content": "你是一个JSON输出助手。只输出合法JSON，不要有其他内容。"},
            {"role": "user", "content": '输出一个JSON对象，包含字段: {"subject": "数学", "topic": "特征值", "level": 3}'}
        ]
        response = llm_service.chat(
            messages,
            use_profile=True,
            response_format={"type": "json_object"},
            temperature=0.3
        )
        answer = response.choices[0].message.content.strip()
        parsed = json.loads(answer)
        report("4. Profile同步JSON", True, f"parsed={json.dumps(parsed, ensure_ascii=False)}")
    except json.JSONDecodeError as e:
        report("4. Profile同步JSON", False, f"JSON解析失败: {e} | raw={answer[:100]}")
    except Exception as e:
        report("4. Profile同步JSON", False, str(e))


# ============================================================
# Test 5: PROFILE_LLM 异步 JSON 模式
# ============================================================
async def test_profile_async_json():
    """测试 llm_service.chat_async() — PROFILE_LLM 异步 JSON 输出"""
    from app.services.llm_service import llm_service

    if llm_service.profile_async is None:
        report("5. Profile异步JSON", False, "PROFILE_LLM async client 未初始化")
        return

    try:
        messages = [
            {"role": "system", "content": "你是一个JSON输出助手。只输出合法JSON。"},
            {"role": "user", "content": '输出JSON: {"status": "ok", "score": 0.85}'}
        ]
        answer = await llm_service.chat_async(
            messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        parsed = json.loads(answer.strip())
        report("5. Profile异步JSON", True, f"parsed={json.dumps(parsed, ensure_ascii=False)}")
    except json.JSONDecodeError as e:
        report("5. Profile异步JSON", False, f"JSON解析失败: {e} | raw={answer[:100]}")
    except Exception as e:
        report("5. Profile异步JSON", False, str(e))


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 60)
    print("LLM 模型切换验证测试")
    from app.config import config
    print(f"QA_LLM:     {config.QA_LLM_MODEL}")
    print(f"PROFILE_LLM: {config.PROFILE_LLM_MODEL}")
    print("=" * 60)

    # 同步测试
    test_qa_chat_non_streaming()
    test_qa_chat_streaming()
    test_qa_multimodal()
    test_profile_chat_json()

    # 异步测试
    asyncio.run(test_profile_async_json())

    # 汇总
    print("=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"结果: {passed}/{len(results)} 通过, {failed}/{len(results)} 失败")
    print("=" * 60)

    if failed > 0:
        print("\n失败项:")
        for name, ok, detail in results:
            if not ok:
                print(f"  [{name}] {detail}")

    return failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
