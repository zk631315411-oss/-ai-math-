from __future__ import annotations

import zipfile
from pathlib import Path


SRC = Path(r"D:\ai-math\简要汇报\模板B_精修版.pptx")
DST = Path(r"D:\ai-math\简要汇报\模板B_精修版_学弟妹友好版.pptx")


REPLACEMENTS = {
    # Slide 1
    "智学助手开发经验分享": "智学助手：一个学生做项目的故事",
    "这次不讲复杂技术，主要讲：我怎么从一个学习中的小问题，慢慢做出一个能用的系统。": "这次主要讲我怎么从一个学习中的小问题，慢慢做出一个能用的系统。",
    # Slide 2
    "故事线 1：为什么要做": "1. 我为什么想做",
    "高等代数难点常常不是没有答案，而是不知道自己卡在哪里。": "学习高等代数时，很多时候不是没答案，而是不知道自己卡在哪一步。",
    "容易脱离教材、直接给答案，看完之后仍然不知道下一步怎么想。": "容易脱离教材、直接给答案，学生看完后还是不知道下一步怎么想。",
    "让 AI 既看见当前页面，也能根据学生状态给出适当支架。": "让 AI 既看见当前页面，也能根据学生情况给出合适提示。",
    "讲法：先讲痛点，不急着讲技术。": "讲法：先讲自己的起点，不急着讲技术。",
    # Slide 3
    "故事线 2：先做一个能用的版本": "2. 先把最小闭环跑通",
    "Cursor / Claude Code": "AI 辅助开发工具",
    "vibe coding": "边问边改",
    "更快把想法变成代码": "更快把想法做出来",
    "AI 不只是\n问答工具，\n它也能成为\n我做项目的\n帮手。": "AI 不只是\n问答工具，\n它也能帮我\n更快做项目。",
    "我开始真正把 AI 当成老师、搜索引擎和协作者来看。": "我开始把 AI 当成老师、帮手和协作者来看。",
    # Slide 4
    "不是所有模型都能直接看图，得先选合适的能力。": "最开始也不是很顺，先把截图提问和回答跑通最重要。",
    "v1 不是完整产品，\n但它让我第一次看见了方向。": "v1 还很粗糙，\n但它让我第一次看见了方向。",
    # Slide 5
    "再做学生画像": "再做学习档案",
    "让系统知道“这个学生大概学到哪了”。": "让系统知道这个学生大概学到哪了。",
    "我希望它留下来的，不只是答案，还有学习过程。": "我希望它留下来的，不只是答案，还有下一次继续学的线索。",
    # Slide 6
    "AI 是很好的老师": "AI 是学习助手",
    "有问题直接问，\n它能解释，也能追着你补概念。": "有问题直接问，\n它能帮我查缺补漏。",
    "AI 也是大型搜索引擎": "AI 也是知识帮手",
    "它不只是找答案，\n还能把知识讲开，\n省掉很多反复翻找的成本。": "它不只是找答案，\n还能把知识讲清楚。",
    "AI 还是开发协作者": "AI 是开发帮手",
    "我更像是需求提出者和方向把关的人，\nAI 负责实现很多具体动作。": "我更像是提出问题、把关方向的人，\nAI 帮我把很多具体动作做快。",
}


def patch_pptx(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    if dst.exists():
        dst.unlink()

    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("ppt/slides/slide") and item.filename.endswith(".xml"):
                text = data.decode("utf-8")
                for old, new in REPLACEMENTS.items():
                    text = text.replace(old, new)
                data = text.encode("utf-8")
            zout.writestr(item, data)


if __name__ == "__main__":
    patch_pptx(SRC, DST)
    print(f"wrote {DST}")
