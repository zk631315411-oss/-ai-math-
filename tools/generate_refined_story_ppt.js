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
};

const FONT = "Microsoft YaHei";

function deck() {
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "张凯";
  pptx.title = "智学助手开发经验分享";
  pptx.subject = "26春石《AIED原理方法》交流";
  pptx.company = "华南师范大学";
  pptx.lang = "zh-CN";
  pptx.theme = { headFontFace: FONT, bodyFontFace: FONT, lang: "zh-CN" };
  return pptx;
}

const P = {
  bg: "FFFDF8",
  dark: "2B2118",
  title: "1F2937",
  body: "374151",
  muted: "6B7280",
  border: "E7D8C5",
  accent: "B45309",
  pale: "FEF3C7",
  pale2: "FFF7ED",
  green: "4D7C0F",
};

function text(slide, s, o) {
  slide.addText(s, {
    fontFace: FONT,
    fit: "shrink",
    margin: 0.04,
    color: P.body,
    ...o,
  });
}

function rect(slide, x, y, w, h, fill, line = fill, radius = true, transparency = 0) {
  slide.addShape(radius ? "roundRect" : "rect", {
    x, y, w, h,
    rectRadius: 0.08,
    fill: { color: fill, transparency },
    line: { color: line, width: line === fill ? 0 : 1 },
  });
}

function title(slide, main, sub) {
  text(slide, main, { x: 0.75, y: 0.48, w: 7.9, h: 0.42, fontSize: 19, bold: true, color: P.title });
  if (sub) text(slide, sub, { x: 0.78, y: 0.96, w: 9.2, h: 0.28, fontSize: 10.5, color: P.muted });
}

function footer(slide, s) {
  text(slide, s, { x: 0.78, y: 7.08, w: 8.6, h: 0.2, fontSize: 8.5, color: P.muted });
}

function num(slide, n, x, y) {
  rect(slide, x, y, 0.42, 0.42, P.accent, P.accent, true);
  text(slide, String(n), { x, y: y + 0.06, w: 0.42, h: 0.2, fontSize: 10, bold: true, color: "FFFFFF", align: "center" });
}

function card(slide, x, y, w, h, head, body, n = null, opts = {}) {
  rect(slide, x, y, w, h, opts.fill || "FFFFFF", opts.line || P.border, true);
  if (n !== null) num(slide, n, x + 0.2, y + 0.22);
  text(slide, head, { x: x + (n !== null ? 0.72 : 0.28), y: y + 0.24, w: w - (n !== null ? 0.95 : 0.56), h: 0.26, fontSize: 12.4, bold: true, color: opts.headColor || P.title });
  text(slide, body, { x: x + 0.28, y: y + 0.72, w: w - 0.56, h: h - 0.86, fontSize: 9.8, color: opts.bodyColor || P.body, valign: "top" });
}

async function contain(slide, img, box, frame = true) {
  const meta = await sharp(img).metadata();
  const ratio = meta.width / meta.height;
  let w = box.w;
  let h = w / ratio;
  if (h > box.h) {
    h = box.h;
    w = h * ratio;
  }
  const x = box.x + (box.w - w) / 2;
  const y = box.y + (box.h - h) / 2;
  if (frame) rect(slide, box.x - 0.05, box.y - 0.05, box.w + 0.1, box.h + 0.1, "FFFFFF", P.border, true);
  slide.addImage({ path: img, x, y, w, h });
}

async function cover(slide, img, box, frame = true) {
  if (frame) rect(slide, box.x - 0.05, box.y - 0.05, box.w + 0.1, box.h + 0.1, "FFFFFF", P.border, true);
  slide.addImage({
    path: img,
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    sizing: { type: "cover", x: box.x, y: box.y, w: box.w, h: box.h },
  });
}

async function build() {
  for (const img of Object.values(IMAGES)) {
    if (!fs.existsSync(img)) throw new Error(`missing image: ${img}`);
  }
  const pptx = deck();

  let s = pptx.addSlide();
  s.background = { color: P.dark };
  rect(s, 0.72, 0.68, 11.9, 6.05, P.pale2, P.pale2, true);
  text(s, "从一个学习痛点开始", { x: 1.18, y: 1.2, w: 6.7, h: 0.58, fontSize: 30, bold: true, color: P.dark });
  text(s, "智学助手开发经验分享", { x: 1.22, y: 1.94, w: 4.8, h: 0.32, fontSize: 15, color: "92400E" });
  rect(s, 1.2, 3.0, 5.85, 1.6, "FFFFFF", P.border, true);
  text(s, "这次不讲复杂技术，主要讲：我怎么从一个学习中的小问题，慢慢做出一个能用的系统。", {
    x: 1.48, y: 3.42, w: 5.25, h: 0.7, fontSize: 15.5, bold: true, color: "3F2B16",
  });
  await contain(s, IMAGES.main, { x: 8.0, y: 1.08, w: 3.8, h: 4.35 });
  text(s, "张凯 · 23小教", { x: 1.24, y: 5.72, w: 3.0, h: 0.24, fontSize: 10.5, color: "6B4E2E" });

  s = pptx.addSlide();
  s.background = { color: P.bg };
  title(s, "故事线 1：为什么要做", "高等代数难点常常不是没有答案，而是不知道自己卡在哪里。");
  card(s, 0.88, 1.56, 4.48, 1.08, "真实学习现场", "学生是在教材页里困住的，不是在空白聊天框里困住的。", 1);
  card(s, 0.88, 2.88, 4.48, 1.08, "通用 AI 的问题", "容易脱离教材、直接给答案，看完之后仍然不知道下一步怎么想。", 2);
  card(s, 0.88, 4.2, 4.48, 1.08, "项目出发点", "让 AI 既看见当前页面，也能根据学生状态给出适当支架。", 3);
  rect(s, 0.88, 5.75, 4.48, 0.55, P.pale, P.pale, true);
  text(s, "讲法：先讲痛点，不急着讲技术。", { x: 1.1, y: 5.93, w: 4.0, h: 0.18, fontSize: 9.2, color: P.accent, bold: true });
  await contain(s, IMAGES.main, { x: 6.1, y: 1.26, w: 6.15, h: 5.35 });
  footer(s, "关键词：教材页、学习现场、不是普通聊天框");

  s = pptx.addSlide();
  s.background = { color: P.bg };
  title(s, "故事线 2：先做一个能用的版本", "先把最小链路跑起来，再根据问题一层层补能力。");
  await contain(s, IMAGES.main, { x: 0.82, y: 1.34, w: 7.8, h: 5.3 });
  rect(s, 9.02, 1.35, 3.05, 4.95, P.pale, P.pale, true);
  text(s, "迭代顺序", { x: 9.35, y: 1.72, w: 2.2, h: 0.34, fontSize: 16, bold: true, color: P.title });
  const steps = [
    "PDF 页面",
    "AI 问答",
    "截图提问",
    "页面标记",
    "图谱与画像",
    "智能练习",
  ];
  steps.forEach((step, i) => {
    num(s, i + 1, 9.36, 2.35 + i * 0.48);
    text(s, step, { x: 9.9, y: 2.43 + i * 0.48, w: 1.55, h: 0.17, fontSize: 9.5, color: P.body });
  });
  text(s, "先跑起来，\n再迭代。", { x: 9.35, y: 5.55, w: 2.2, h: 0.52, fontSize: 17, bold: true, color: P.accent, align: "center" });
  footer(s, "关键词：最小可用版本、边做边学、边用边改");

  s = pptx.addSlide();
  s.background = { color: P.bg };
  title(s, "故事线 3：让 AI 学会少给答案", "好的助教不是替学生走完，而是把学生带到能继续想的位置。");
  await contain(s, IMAGES.ai, { x: 0.88, y: 1.2, w: 3.55, h: 5.78 });
  card(s, 4.85, 1.45, 2.4, 1.18, "先定位卡点", "是否理解代数余子式、按行展开等前置概念。", 1);
  card(s, 4.85, 2.88, 2.4, 1.18, "再搭台阶", "用 3 阶行列式的小例子，把任务拆成可做的一步。", 2);
  card(s, 4.85, 4.31, 2.4, 1.18, "不替学生做完", "让学生在提示下自己算出关键一步。", 3);
  rect(s, 7.95, 1.55, 3.95, 3.25, "FFFFFF", P.border, true);
  text(s, "这一页我会这样讲", { x: 8.28, y: 1.9, w: 3.0, h: 0.3, fontSize: 16.5, bold: true, color: P.title });
  text(s, "我后来发现，AI 不能只追求“答得对”。如果它一下子把答案讲完，学生可能只是看懂了，并没有真正会做。所以我尝试让它先确认学生卡在哪，再给一个小任务。", {
    x: 8.28, y: 2.48, w: 3.28, h: 1.28, fontSize: 11.4, color: P.body,
  });
  rect(s, 7.95, 5.15, 3.95, 0.82, P.pale, P.pale, true);
  text(s, "一句话：从“会回答”变成“会引导”。", { x: 8.28, y: 5.44, w: 3.28, h: 0.2, fontSize: 10.2, bold: true, color: P.accent, align: "center" });
  footer(s, "关键词：苏格拉底式引导、脚手架、少给结论多给台阶");

  s = pptx.addSlide();
  s.background = { color: P.bg };
  title(s, "故事线 4：把零散问题变成结构", "提问记录贴回教材，薄弱点放进知识图谱。");
  rect(s, 0.82, 1.4, 5.45, 1.24, "FFFFFF", P.border, true);
  await contain(s, IMAGES.marker, { x: 0.98, y: 1.58, w: 5.08, h: 0.86 }, false);
  text(s, "页面标记：把一次提问留在教材原位", { x: 6.7, y: 1.72, w: 4.8, h: 0.3, fontSize: 14.5, bold: true, color: P.title });
  text(s, "学生复习时可以回到当时的问题，而不是在聊天记录里翻找。", { x: 6.72, y: 2.2, w: 4.8, h: 0.23, fontSize: 10.4, color: P.muted });
  await contain(s, IMAGES.graph, { x: 0.88, y: 3.05, w: 11.55, h: 3.62 });
  rect(s, 0.88, 6.42, 11.55, 0.36, P.pale, P.pale, true);
  text(s, "知识图谱：不是为了炫技术，而是帮助学生看到“我卡住的知识点和哪些前后知识有关”。", {
    x: 1.1, y: 6.53, w: 11.0, h: 0.14, fontSize: 8.7, color: P.accent, bold: true, align: "center",
  });
  footer(s, "关键词：可回看、可追踪、结构化理解");

  s = pptx.addSlide();
  s.background = { color: P.dark };
  text(s, "给学弟学妹的几句话", { x: 0.95, y: 0.9, w: 6.6, h: 0.48, fontSize: 26, bold: true, color: "FFF7ED" });
  text(s, "这部分不用念得很正式，像聊天一样说就好。", { x: 0.98, y: 1.48, w: 5.2, h: 0.24, fontSize: 10.5, color: "FDE68A" });
  card(s, 1.0, 2.05, 3.1, 2.25, "不用等完全学会", "项目会逼着你学。很多东西不是先学完再做，而是做着做着才真的学会。", 1, { fill: "3A2A1D", line: "5A4230", headColor: "FFFFFF", bodyColor: "FDEDD3" });
  card(s, 5.12, 2.05, 3.1, 2.25, "把问题拆小", "一个大系统其实就是很多小问题。拆到能查、能问、能试，就能继续往前走。", 2, { fill: "3A2A1D", line: "5A4230", headColor: "FFFFFF", bodyColor: "FDEDD3" });
  card(s, 9.24, 2.05, 3.1, 2.25, "让反馈推着你改", "别人觉得别扭的地方，往往就是下一轮最该优化的地方。", 3, { fill: "3A2A1D", line: "5A4230", headColor: "FFFFFF", bodyColor: "FDEDD3" });
  rect(s, 2.48, 5.35, 8.35, 0.82, "FFF7ED", "FFF7ED", true);
  text(s, "我自己的体会：想干就先做，做出来再慢慢把它变好。", { x: 2.95, y: 5.64, w: 7.4, h: 0.22, fontSize: 13.5, bold: true, color: P.dark, align: "center" });
  text(s, "谢谢大家", { x: 5.1, y: 6.55, w: 3.1, h: 0.3, fontSize: 18, bold: true, color: "FDE68A", align: "center" });

  await pptx.writeFile({ fileName: path.join(OUT_DIR, "模板B_精修版.pptx") });
}

build().catch((e) => {
  console.error(e);
  process.exit(1);
});
