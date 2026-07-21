from __future__ import annotations

import re
import zipfile
from pathlib import Path


SRC = Path(r"D:\ai-math\简要汇报\模板B_精修版_学弟妹友好版_最终.pptx")
DST = Path(r"D:\ai-math\简要汇报\模板B_精修版_学弟妹友好版_润色版2.pptx")


REPLACEMENTS_BY_SLIDE = {
    "ppt/slides/slide2.xml": {
        "懒是人类进步的阶梯": "对效率的追求，往往是改进工具的起点",
        "要打开软件，要拍照，要写提示词，要各种被打断": "要打开软件、拍照、写提示词，学习过程很容易被打断",
        "让学习更加轻松，更加愉快，更加高效": "让学习过程更连贯、更轻松，也更高效",
        "提速增效、更好的体验": "提速增效、更好的学习体验",
    },
    "ppt/slides/slide4.xml": {
        "帮助我们更好的学习": "帮助我们更好地学习",
        "的科学。理论并不远离生活，它源于真实的教育实践，是经验沉淀后的智慧结晶。善于理解和运用教育理论，能够帮助我们更好地观察学习、设计支持，并改进自己的学习与教学实践。": "的科学。理论源于真实的教育实践，是经验沉淀后的智慧结晶。善于运用教育理论，能够帮助我们更好地观察学习、设计支持，并改进实践。",
    },
    "ppt/slides/slide5.xml": {
        "发现问题，分析问题，收集资料，构建计划，开始行动": "从发现问题到开始行动",
        "提问记录贴回教材，薄弱点放进知识图谱。": "把提问记录贴回教材，把薄弱点放进知识结构中。",
        "知识图谱：看到“我卡住的知识点和哪些前后知识有关”。": "知识图谱：看到“我卡住的知识点”和前后知识的关系。",
        "可视化的学习": "可视化的学习过程",
    },
    "ppt/slides/slide6.xml": {
        "世界是一个草台班子": "很多事情没有想象中那么遥远",
        "很多东西": "看上去复杂的东西，",
        "其实并不难，看上去高大上的东西或许一个高中生经过三个月的学习就能上手。": "真正拆开后，往往也是一个个可以学习、可以解决的小问题。",
        "一颗旺盛的好奇心与说干就干的行动力，是解决问题的良药": "好奇心和行动力，是推动自己往前走的关键。",
        "复杂的系统本质上也是": "复杂系统本质上也是",
        ">小<": ">许多小<",
        "模块的结合": "模块的组合",
        "把大问题拆解成一个个的小问题": "把大问题拆成能查、能问、能试的小问题",
        "再解决一个个小问题，成功之路自己就会慢慢出现。": "一步步解决，路径就会慢慢清楚。",
        "实践是检验真理的唯一标准": "先行动，再迭代",
        "栽一棵树最好的时机是十年前，第二好的时机是现在。与其把想到完美再行动，不如在行动中不断迭代发展。": "栽一棵树最好的时机是十年前，第二好的时机是现在。与其等到想得完美再行动，不如在行动中不断迭代完善。",
    },
}


def patch_pptx() -> None:
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    if DST.exists():
        DST.unlink()

    with zipfile.ZipFile(SRC, "r") as zin, zipfile.ZipFile(DST, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if re.match(r"ppt/slides/slide\d+\.xml$", item.filename):
                text = data.decode("utf-8")
                for old, new in REPLACEMENTS_BY_SLIDE.get(item.filename, {}).items():
                    text = text.replace(old, new)
                data = text.encode("utf-8")
            zout.writestr(item, data)


if __name__ == "__main__":
    patch_pptx()
    print(f"wrote {DST}")
