from __future__ import annotations

import zipfile
from pathlib import Path


SRC = Path(r"D:\ai-math\简要汇报\模板B_精修版_学弟妹友好版.pptx")
DST = Path(r"D:\ai-math\简要汇报\模板B_精修版_学弟妹友好版_最终.pptx")


REPLACEMENTS = {
    "故事线 3：让 AI 学会少给答案": "3. 让 AI 学会少给答案",
    "这一页我会这样讲": "我后来发现",
    "故事线 4：把零散问题变成结构": "4. 把零散问题变成结构",
    "知识图谱：不是为了炫技术，而是帮助学生看到“我卡住的知识点和哪些前后知识有关”。": "知识图谱：帮助学生看到“我卡住的知识点和哪些前后知识有关”。",
    "这部分不用念得很正式，像聊天一样说就好。": "我想分享的不是标准答案，而是自己的真实体会。",
}


def patch_pptx(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)

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
    print(f"updated {DST}")
