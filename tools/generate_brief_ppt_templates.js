const path = require("path");
const fs = require("fs");
const sharp = require("C:/Users/hp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/sharp@0.34.5/node_modules/sharp");
const PptxGenJS = require("C:/Users/hp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/pptxgenjs@4.0.1/node_modules/pptxgenjs");

const OUT_DIR = "D:/ai-math/简要汇报";
const IMAGES = {
  ai: path.join(OUT_DIR, "4968a1561fe089cab50b8bb07ad95610.png"),
  marker: path.join(OUT_DIR, "51236543ce7f14dddc63b952d4e36ddb.png"),
  graph: path.join(OUT_DIR, "64236a919f359b816e4fe71397f859a5.png"),
  main: path.join(OUT_DIR, "6e3b30fd04a581a2ffbfed1822367a41.png"),
  weak: path.join(OUT_DIR, "74837d93f29079dddba00dd699c4bef3.png"),
};

const SLIDE_W = 13.333;
const SLIDE_H = 7.5;
const FONT = "Microsoft YaHei";

function makeDeck(title, subject) {
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "张凯";
  pptx.company = "华南师范大学";
  pptx.subject = subject;
  pptx.title = title;
  pptx.lang = "zh-CN";
  pptx.theme = {
    headFontFace: FONT,
    bodyFontFace: FONT,
    lang: "zh-CN",
  };
  return pptx;
}

function addText(slide, text, opts) {
  slide.addText(text, {
    fontFace: FONT,
    fit: "shrink",
    breakLine: false,
    margin: 0.04,
    ...opts,
  });
}

function rect(slide, x, y, w, h, fill, line = fill, radius = false, transparency = 0) {
  slide.addShape(radius ? "roundRect" : "rect", {
    x,
    y,
    w,
    h,
    rectRadius: 0.08,
    fill: { color: fill, transparency },
    line: { color: line, transparency: line === fill ? 100 : 0, width: 1 },
  });
}

function footer(slide, label, color = "64748B") {
  addText(slide, label, {
    x: 0.72,
    y: 7.05,
    w: 5.8,
    h: 0.22,
    fontSize: 8.5,
    color,
  });
}

async function addImageContain(slide, imagePath, box, opts = {}) {
  const meta = await sharp(imagePath).metadata();
  const ratio = meta.width / meta.height;
  let w = box.w;
  let h = w / ratio;
  if (h > box.h) {
    h = box.h;
    w = h * ratio;
  }
  const x = box.x + (box.w - w) / 2;
  const y = box.y + (box.h - h) / 2;
  if (opts.frame) {
    rect(slide, box.x - 0.05, box.y - 0.05, box.w + 0.1, box.h + 0.1, opts.frameFill || "FFFFFF", opts.frameLine || "E2E8F0", true);
  }
  slide.addImage({ path: imagePath, x, y, w, h });
}

async function addImageCover(slide, imagePath, box, opts = {}) {
  if (opts.frame) {
    rect(slide, box.x - 0.05, box.y - 0.05, box.w + 0.1, box.h + 0.1, opts.frameFill || "FFFFFF", opts.frameLine || "E2E8F0", true);
  }
  slide.addImage({
    path: imagePath,
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    sizing: { type: "cover", x: box.x, y: box.y, w: box.w, h: box.h },
  });
}

function addTitle(slide, title, subtitle, palette) {
  addText(slide, title, {
    x: 0.72,
    y: 0.45,
    w: 8.8,
    h: 0.42,
    fontSize: 20,
    bold: true,
    color: palette.title,
  });
  if (subtitle) {
    addText(slide, subtitle, {
      x: 0.74,
      y: 0.9,
      w: 9.4,
      h: 0.3,
      fontSize: 10.5,
      color: palette.muted,
    });
  }
}

function addNumber(slide, n, x, y, palette) {
  rect(slide, x, y, 0.42, 0.42, palette.accent, palette.accent, true);
  addText(slide, String(n), {
    x,
    y: y + 0.06,
    w: 0.42,
    h: 0.2,
    fontSize: 10,
    bold: true,
    color: "FFFFFF",
    align: "center",
  });
}

function card(slide, x, y, w, h, title, body, palette, n) {
  rect(slide, x, y, w, h, "FFFFFF", palette.border, true);
  if (n) addNumber(slide, n, x + 0.18, y + 0.2, palette);
  addText(slide, title, {
    x: x + (n ? 0.72 : 0.26),
    y: y + 0.22,
    w: w - (n ? 0.96 : 0.52),
    h: 0.28,
    fontSize: 12.5,
    bold: true,
    color: palette.title,
  });
  addText(slide, body, {
    x: x + 0.26,
    y: y + 0.68,
    w: w - 0.52,
    h: h - 0.84,
    fontSize: 9.5,
    color: palette.body,
    breakLine: false,
    valign: "top",
    fit: "shrink",
  });
}

async function buildA() {
  const palette = {
    bg: "F8FAFC",
    navy: "1E3A8A",
    title: "0F172A",
    body: "334155",
    muted: "64748B",
    border: "D8E0EA",
    accent: "2563EB",
    warm: "F97316",
  };
  const pptx = makeDeck("智学助手简要汇报 A", "正式清爽版");

  let slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  rect(slide, 0, 0, 13.333, 7.5, palette.navy, palette.navy);
  rect(slide, 8.45, 0, 4.88, 7.5, "EFF6FF", "EFF6FF");
  await addImageContain(slide, IMAGES.main, { x: 7.35, y: 1.08, w: 5.25, h: 4.95 }, { frame: true });
  addText(slide, "智学助手", { x: 0.88, y: 1.1, w: 5.5, h: 0.65, fontSize: 33, bold: true, color: "FFFFFF" });
  addText(slide, "从学习痛点到自适应教育智能体", { x: 0.93, y: 1.9, w: 5.8, h: 0.38, fontSize: 16, color: "DDEBFF" });
  addText(slide, "高等代数学习支持系统 · 开发经验分享", { x: 0.93, y: 2.42, w: 5.3, h: 0.26, fontSize: 10.5, color: "C7D2FE" });
  card(slide, 0.93, 4.25, 1.85, 1.0, "教材页锚定", "从真实学习现场出发", { ...palette, title: "FFFFFF", body: "DBEAFE", border: "3656A8", accent: palette.warm });
  card(slide, 3.0, 4.25, 1.85, 1.0, "AI 引导", "先提示，再让学生思考", { ...palette, title: "FFFFFF", body: "DBEAFE", border: "3656A8", accent: palette.warm });
  card(slide, 5.07, 4.25, 1.85, 1.0, "学习闭环", "记录、诊断、练习反馈", { ...palette, title: "FFFFFF", body: "DBEAFE", border: "3656A8", accent: palette.warm });
  footer(slide, "张凯 · 23小教 · 2026.05", "C7D2FE");

  slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addTitle(slide, "01 先让系统进入学习现场", "把 AI 放在教材页旁边，而不是脱离上下文闲聊。", palette);
  await addImageContain(slide, IMAGES.main, { x: 0.72, y: 1.35, w: 11.9, h: 5.32 }, { frame: true });
  footer(slide, "主界面：PDF 教材 + AI 对话 + 页面标记 + 出题入口", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addTitle(slide, "02 AI 不只是给答案", "苏格拉底式引导：先确认概念，再推动学生自己做一步。", palette);
  await addImageContain(slide, IMAGES.ai, { x: 0.85, y: 1.35, w: 3.55, h: 5.75 }, { frame: true });
  card(slide, 4.85, 1.48, 3.2, 1.45, "先定位卡点", "系统先判断学生是否理解代数余子式、按行展开等前置概念。", palette, 1);
  card(slide, 4.85, 3.1, 3.2, 1.45, "再给思考台阶", "通过小例子和关键步骤，让学生在提示下完成推理。", palette, 2);
  card(slide, 4.85, 4.72, 3.2, 1.45, "最后形成练习", "把解释转化为可动手尝试的任务，而不是停留在看懂。", palette, 3);
  addText(slide, "核心表达：先引导理解，再推动学生自己推一遍。", {
    x: 8.55, y: 2.18, w: 3.7, h: 1.0, fontSize: 17, bold: true, color: palette.navy,
    valign: "mid",
  });
  rect(slide, 8.52, 3.5, 3.75, 1.4, "DBEAFE", "DBEAFE", true);
  addText(slide, "适合分享时说：\n我希望它像一位助教，不是替学生想完，而是把学生带到能继续想的位置。", {
    x: 8.82, y: 3.78, w: 3.15, h: 0.72, fontSize: 10.3, color: palette.body,
    fit: "shrink",
  });
  footer(slide, "示例：行列式性质与代数余子式", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addTitle(slide, "03 学习过程要能回到原处", "页面标记让提问、回答和教材位置发生连接。", palette);
  await addImageContain(slide, IMAGES.marker, { x: 0.86, y: 1.5, w: 7.6, h: 1.85 }, { frame: true });
  await addImageContain(slide, IMAGES.main, { x: 0.86, y: 3.65, w: 7.6, h: 2.75 }, { frame: true });
  card(slide, 8.9, 1.62, 3.35, 1.18, "红蓝圆点", "标记学生在教材页上的历史提问位置。", palette);
  card(slide, 8.9, 3.03, 3.35, 1.18, "回看问题", "点击标记可以回到当时的问题、回答与追问。", palette);
  card(slide, 8.9, 4.44, 3.35, 1.18, "形成轨迹", "学习记录不再散落在聊天框里，而是贴回教材。", palette);
  footer(slide, "这一页主要讲：学习不是一次性对话，而是可回看的过程。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addTitle(slide, "04 把薄弱点放回知识结构", "知识图谱帮助学生看到概念之间的前后依赖。", palette);
  await addImageContain(slide, IMAGES.graph, { x: 0.72, y: 1.32, w: 11.9, h: 5.38 }, { frame: true });
  footer(slide, "知识图谱：用于概念关系、前置知识和薄弱点定位", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addTitle(slide, "05 给学弟学妹的三个建议", "不用等完全准备好，真实项目往往是在动手中长出来的。", palette);
  card(slide, 0.86, 1.62, 3.65, 3.9, "从一个小痛点开始", "不要一开始就追求大而全。先找到一个自己真的遇到过的问题，把最小可用版本做出来。", palette, 1);
  card(slide, 4.84, 1.62, 3.65, 3.9, "把问题拆小验证", "界面、数据、模型、反馈，每一块都可以单独试。能跑起来，就有迭代空间。", palette, 2);
  card(slide, 8.82, 1.62, 3.65, 3.9, "让真实反馈推动改进", "同学、老师和自己使用时的不舒服，往往就是下一轮优化的入口。", palette, 3);
  addText(slide, "想干就先做，做完再把它变好。", { x: 2.3, y: 6.28, w: 8.7, h: 0.4, fontSize: 18, bold: true, color: palette.navy, align: "center" });
  footer(slide, "结尾页：回到行动力、好奇心和持续迭代", palette.muted);

  await pptx.writeFile({ fileName: path.join(OUT_DIR, "模板A_正式清爽版.pptx") });
}

async function buildB() {
  const palette = {
    bg: "FFFDF8",
    title: "1F2937",
    body: "374151",
    muted: "6B7280",
    border: "E5D8C5",
    accent: "B45309",
    green: "4D7C0F",
    pale: "FEF3C7",
  };
  const pptx = makeDeck("智学助手简要汇报 B", "故事分享版");

  let slide = pptx.addSlide();
  slide.background = { color: "2B2118" };
  rect(slide, 0.7, 0.7, 11.92, 6.05, "FFF7ED", "FFF7ED", true);
  addText(slide, "从一个学习痛点开始", { x: 1.18, y: 1.22, w: 6.8, h: 0.55, fontSize: 30, bold: true, color: "2B2118" });
  addText(slide, "智学助手开发经验分享", { x: 1.22, y: 1.92, w: 5.2, h: 0.34, fontSize: 15, color: "92400E" });
  await addImageContain(slide, IMAGES.weak, { x: 8.45, y: 1.35, w: 3.05, h: 2.2 }, { frame: true, frameFill: "FFFFFF", frameLine: "E5D8C5" });
  addText(slide, "不是先有完整能力，\n而是先有一个想解决的问题。", { x: 1.26, y: 3.35, w: 6.0, h: 1.1, fontSize: 19, bold: true, color: "3F2B16" });
  addText(slide, "张凯 · 23小教", { x: 1.25, y: 5.68, w: 3.0, h: 0.24, fontSize: 10.5, color: "6B4E2E" });

  slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addTitle(slide, "故事线 1：为什么要做", "高等代数难点常常不是没有答案，而是不知道自己卡在哪里。", palette);
  await addImageContain(slide, IMAGES.main, { x: 6.15, y: 1.24, w: 6.2, h: 5.6 }, { frame: true });
  card(slide, 0.9, 1.55, 4.55, 1.15, "真实学习现场", "学生是在教材页里困住的，不是在空白聊天框里困住的。", palette, 1);
  card(slide, 0.9, 2.95, 4.55, 1.15, "通用 AI 的问题", "容易脱离教材、直接给答案，学生看完仍然不知道下一步怎么想。", palette, 2);
  card(slide, 0.9, 4.35, 4.55, 1.15, "项目出发点", "让 AI 既懂当前页面，也能根据学生状态给出适当支架。", palette, 3);
  footer(slide, "这一页适合讲项目动机，不用讲技术细节。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addTitle(slide, "故事线 2：先做一个能用的版本", "先把 PDF 阅读和 AI 问答跑起来，再逐步加能力。", palette);
  await addImageContain(slide, IMAGES.main, { x: 0.75, y: 1.35, w: 8.1, h: 5.4 }, { frame: true });
  rect(slide, 9.32, 1.6, 2.95, 4.62, palette.pale, palette.pale, true);
  addText(slide, "迭代顺序", { x: 9.62, y: 1.9, w: 2.1, h: 0.3, fontSize: 15, bold: true, color: palette.title });
  addText(slide, "1  PDF 页面\n2  AI 问答\n3  截图提问\n4  页面标记\n5  图谱与画像\n6  智能练习", {
    x: 9.64, y: 2.48, w: 2.1, h: 2.55, fontSize: 12, color: palette.body, breakLine: false, fit: "shrink",
  });
  addText(slide, "先跑起来，再迭代。", { x: 9.62, y: 5.55, w: 2.15, h: 0.3, fontSize: 13, bold: true, color: palette.accent });
  footer(slide, "这一页讲方法：最小可用版本，而不是一开始追求完美。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addTitle(slide, "故事线 3：让 AI 学会少给答案", "好的助教不是替学生走完，而是把学生扶到能继续走。", palette);
  await addImageContain(slide, IMAGES.ai, { x: 0.88, y: 1.25, w: 3.35, h: 5.85 }, { frame: true });
  rect(slide, 4.8, 1.55, 7.4, 3.8, "FFFFFF", palette.border, true);
  addText(slide, "这张图讲什么？", { x: 5.15, y: 1.92, w: 3.2, h: 0.34, fontSize: 18, bold: true, color: palette.title });
  addText(slide, "先问学生是否理解关键概念，再用一个小例子拆出可操作步骤。学生不是只看结论，而是被推动着亲自算一步。", {
    x: 5.18, y: 2.55, w: 6.28, h: 1.0, fontSize: 13.5, color: palette.body, fit: "shrink",
  });
  addText(slide, "分享重点：把“会回答”改造成“会引导”。", { x: 5.18, y: 4.18, w: 5.4, h: 0.36, fontSize: 15, bold: true, color: palette.accent });
  footer(slide, "这一页讲教育味道：苏格拉底式引导与脚手架。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addTitle(slide, "故事线 4：把零散问题变成结构", "提问记录贴回教材，薄弱点放进知识图谱。", palette);
  await addImageContain(slide, IMAGES.marker, { x: 0.88, y: 1.45, w: 5.2, h: 1.15 }, { frame: true });
  await addImageContain(slide, IMAGES.graph, { x: 0.88, y: 2.95, w: 11.65, h: 3.82 }, { frame: true });
  addText(slide, "从“我问过什么”到“我卡在哪条知识链上”", { x: 6.55, y: 1.58, w: 5.4, h: 0.32, fontSize: 14.5, bold: true, color: palette.title });
  addText(slide, "页面标记解决回看，知识图谱解决结构理解。", { x: 6.58, y: 2.04, w: 5.0, h: 0.25, fontSize: 10.5, color: palette.muted });
  footer(slide, "这一页可以快速带过，不必解释每个节点。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: "2B2118" };
  addText(slide, "给大一同学的几句话", { x: 0.95, y: 0.92, w: 6.6, h: 0.5, fontSize: 27, bold: true, color: "FFF7ED" });
  card(slide, 1.02, 2.0, 3.25, 2.45, "不用等完全学会", "项目会逼着你学，动手本身就是学习方式。", { ...palette, title: "2B2118", body: "4B3827", border: "FFF7ED", accent: "B45309" }, 1);
  card(slide, 5.05, 2.0, 3.25, 2.45, "把大问题拆小", "每次只解决一个最卡人的小环节。", { ...palette, title: "2B2118", body: "4B3827", border: "FFF7ED", accent: "B45309" }, 2);
  card(slide, 9.08, 2.0, 3.25, 2.45, "让反馈推动你", "别人觉得难用的地方，就是下一次改进的方向。", { ...palette, title: "2B2118", body: "4B3827", border: "FFF7ED", accent: "B45309" }, 3);
  addText(slide, "谢谢大家", { x: 4.95, y: 5.75, w: 3.4, h: 0.42, fontSize: 21, bold: true, color: "FDE68A", align: "center" });

  await pptx.writeFile({ fileName: path.join(OUT_DIR, "模板B_故事分享版.pptx") });
}

async function buildC() {
  const palette = {
    bg: "F7F9FB",
    title: "111827",
    body: "374151",
    muted: "6B7280",
    border: "D1D5DB",
    accent: "0F766E",
    soft: "CCFBF1",
    dark: "134E4A",
  };
  const pptx = makeDeck("智学助手简要汇报 C", "现场演示版");

  let slide = pptx.addSlide();
  slide.background = { color: palette.bg };
  addText(slide, "智学助手现场演示", { x: 0.82, y: 0.82, w: 6.5, h: 0.55, fontSize: 30, bold: true, color: palette.dark });
  addText(slide, "10-15 分钟轻量分享版", { x: 0.86, y: 1.56, w: 4.0, h: 0.28, fontSize: 12.5, color: palette.muted });
  const items = [
    ["打开教材", "PDF + AI 对话"],
    ["提出问题", "文字或截图求助"],
    ["看引导", "分步提示与练习"],
    ["看结构", "标记与知识图谱"],
  ];
  items.forEach((it, idx) => {
    const x = 0.9 + idx * 3.05;
    card(slide, x, 3.0, 2.45, 2.05, it[0], it[1], palette, idx + 1);
  });
  footer(slide, "建议开场用这一页，告诉大家今天只看一个项目怎么一步步做出来。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: "FFFFFF" };
  addTitle(slide, "演示 1：系统从教材页开始", "先让大家看到完整学习界面，再讲为什么不是普通聊天工具。", palette);
  await addImageContain(slide, IMAGES.main, { x: 0.65, y: 1.25, w: 12.05, h: 5.55 }, { frame: true });
  footer(slide, "讲述提示：左边是学习材料，右边是助教，问题不会脱离当前页面。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: "FFFFFF" };
  addTitle(slide, "演示 2：AI 引导学生自己走一步", "这里不要讲模型，讲它怎么像助教一样搭台阶。", palette);
  await addImageContain(slide, IMAGES.ai, { x: 0.85, y: 1.22, w: 4.1, h: 5.9 }, { frame: true });
  addText(slide, "现场说法", { x: 5.55, y: 1.6, w: 2.0, h: 0.3, fontSize: 18, bold: true, color: palette.dark });
  addText(slide, "这段回答不是直接把结论抛出来，而是先问前置概念，再给一个 3 阶行列式的小任务，让学生自己算一步。", {
    x: 5.58,
    y: 2.2,
    w: 5.9,
    h: 1.1,
    fontSize: 14,
    color: palette.body,
    fit: "shrink",
  });
  card(slide, 5.58, 4.1, 2.0, 1.15, "可讲 30 秒", "先定位，再引导。", palette);
  card(slide, 7.92, 4.1, 2.0, 1.15, "可讲 30 秒", "不是替学，而是助学。", palette);
  card(slide, 10.26, 4.1, 2.0, 1.15, "可讲 30 秒", "讲完转入练习闭环。", palette);
  footer(slide, "这一页适合停留稍久，是最能体现教育价值的一页。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: "FFFFFF" };
  addTitle(slide, "演示 3：问题留在教材原位", "页面标记把一次性对话变成可回看的学习记录。", palette);
  await addImageContain(slide, IMAGES.marker, { x: 0.82, y: 1.45, w: 7.25, h: 1.55 }, { frame: true });
  await addImageContain(slide, IMAGES.main, { x: 0.82, y: 3.35, w: 7.25, h: 3.15 }, { frame: true });
  addText(slide, "现场说法", { x: 8.72, y: 1.75, w: 2.0, h: 0.3, fontSize: 18, bold: true, color: palette.dark });
  addText(slide, "学生以后复习时，不需要在聊天记录里翻来翻去，可以回到教材页上找到当时的问题。", {
    x: 8.75, y: 2.42, w: 3.45, h: 1.15, fontSize: 13.2, color: palette.body, fit: "shrink",
  });
  rect(slide, 8.72, 4.3, 3.4, 1.15, palette.soft, palette.soft, true);
  addText(slide, "关键词：可回看、可追踪、贴近教材", { x: 9.02, y: 4.68, w: 2.8, h: 0.26, fontSize: 11.5, bold: true, color: palette.dark, align: "center" });
  footer(slide, "如果时间紧，这页讲 1 分钟即可。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: "FFFFFF" };
  addTitle(slide, "演示 4：从薄弱点看到知识结构", "知识图谱不是为了炫技术，而是为了帮助学生理解前后依赖。", palette);
  await addImageContain(slide, IMAGES.graph, { x: 0.72, y: 1.3, w: 11.9, h: 5.38 }, { frame: true });
  footer(slide, "讲述提示：不用解释每条边，强调“知识不是碎片，薄弱点有前后关系”。", palette.muted);

  slide = pptx.addSlide();
  slide.background = { color: palette.dark };
  addText(slide, "最后 1 分钟：我的开发心得", { x: 0.9, y: 0.9, w: 6.8, h: 0.45, fontSize: 25, bold: true, color: "FFFFFF" });
  card(slide, 1.0, 2.0, 3.1, 2.55, "先把想法做小", "第一个版本只要解决一个真实痛点，不要一开始就追求完整平台。", { ...palette, title: "FFFFFF", body: "D1FAE5", border: "2A6963", accent: "14B8A6" }, 1);
  card(slide, 5.12, 2.0, 3.1, 2.55, "不会就拆开学", "项目由很多小问题组成，拆到能搜索、能验证、能修改就行。", { ...palette, title: "FFFFFF", body: "D1FAE5", border: "2A6963", accent: "14B8A6" }, 2);
  card(slide, 9.24, 2.0, 3.1, 2.55, "用反馈逼近真实", "好项目不是一次设计出来的，而是在不断使用和调整中变得更像样。", { ...palette, title: "FFFFFF", body: "D1FAE5", border: "2A6963", accent: "14B8A6" }, 3);
  addText(slide, "谢谢大家", { x: 5.1, y: 5.88, w: 3.1, h: 0.4, fontSize: 21, bold: true, color: "CCFBF1", align: "center" });

  await pptx.writeFile({ fileName: path.join(OUT_DIR, "模板C_现场演示版.pptx") });
}

async function main() {
  for (const p of Object.values(IMAGES)) {
    if (!fs.existsSync(p)) throw new Error(`Missing image: ${p}`);
  }
  await buildA();
  await buildB();
  await buildC();
  console.log("Generated 3 PPT templates in", OUT_DIR);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
