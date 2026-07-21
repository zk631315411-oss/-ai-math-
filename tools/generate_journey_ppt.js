const fs = require("fs");
const path = require("path");
const sharp = require("C:/Users/hp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/sharp@0.34.5/node_modules/sharp");
const PptxGenJS = require("C:/Users/hp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/pptxgenjs@4.0.1/node_modules/pptxgenjs");

const OUT_DIR = "D:/ai-math/简要汇报";
const IMAGES = {
  main: path.join(OUT_DIR, "6e3b30fd04a581a2ffbfed1822367a41.png"),
  ai: path.join(OUT_DIR, "4968a1561fe089cab50b8bb07ad95610.png"),
  marker: path.join(OUT_DIR, "51236543ce7f14dddc63b952d4e36ddb.png"),
  graph: path.join(OUT_DIR, "64236a919f359b816e4fe71397f859a5.png"),
  weak: path.join(OUT_DIR, "74837d93f29079dddba00dd699c4bef3.png"),
};

const FONT = "Microsoft YaHei";

const C = {
  bg: "F8FAFC",
  bg2: "EEF2FF",
  ink: "0F172A",
  title: "111827",
  body: "334155",
  muted: "64748B",
  border: "D6DCE5",
  accent: "2563EB",
  teal: "0F766E",
  cream: "FFF7ED",
  cream2: "FEF3C7",
  dark: "1E293B",
};

function deck() {
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "张凯";
  pptx.company = "华南师范大学";
  pptx.title = "从豆包查题到智学助手";
  pptx.subject = "心路历程版";
  pptx.lang = "zh-CN";
  pptx.theme = { headFontFace: FONT, bodyFontFace: FONT, lang: "zh-CN" };
  return pptx;
}

function t(slide, text, opts = {}) {
  slide.addText(text, {
    fontFace: FONT,
    margin: 0.04,
    fit: "shrink",
    color: C.body,
    ...opts,
  });
}

function box(slide, x, y, w, h, fill, line = fill, radius = true, transparency = 0) {
  slide.addShape(radius ? "roundRect" : "rect", {
    x,
    y,
    w,
    h,
    rectRadius: 0.08,
    fill: { color: fill, transparency },
    line: { color: line, width: line === fill ? 0 : 1 },
  });
}

function num(slide, n, x, y, accent = C.accent) {
  box(slide, x, y, 0.42, 0.42, accent, accent, true);
  t(slide, String(n), {
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

function title(slide, main, sub) {
  t(slide, main, {
    x: 0.78,
    y: 0.45,
    w: 8.3,
    h: 0.42,
    fontSize: 20,
    bold: true,
    color: C.title,
  });
  if (sub) {
    t(slide, sub, {
      x: 0.8,
      y: 0.92,
      w: 8.9,
      h: 0.24,
      fontSize: 10.3,
      color: C.muted,
    });
  }
}

function footer(slide, text) {
  t(slide, text, { x: 0.8, y: 7.08, w: 8.4, h: 0.2, fontSize: 8.5, color: C.muted });
}

function card(slide, x, y, w, h, head, body, n = null, opts = {}) {
  box(slide, x, y, w, h, opts.fill || "FFFFFF", opts.line || C.border, true);
  if (n !== null) num(slide, n, x + 0.2, y + 0.18, opts.accent || C.accent);
  t(slide, head, {
    x: x + (n !== null ? 0.72 : 0.26),
    y: y + 0.21,
    w: w - (n !== null ? 0.98 : 0.52),
    h: 0.28,
    fontSize: 12.4,
    bold: true,
    color: opts.headColor || C.title,
  });
  t(slide, body, {
    x: x + 0.26,
    y: y + 0.68,
    w: w - 0.52,
    h: h - 0.85,
    fontSize: 9.7,
    color: opts.bodyColor || C.body,
  });
}

async function contain(slide, image, boxArea, frame = true) {
  const meta = await sharp(image).metadata();
  const ratio = meta.width / meta.height;
  let w = boxArea.w;
  let h = w / ratio;
  if (h > boxArea.h) {
    h = boxArea.h;
    w = h * ratio;
  }
  const x = boxArea.x + (boxArea.w - w) / 2;
  const y = boxArea.y + (boxArea.h - h) / 2;
  if (frame) box(slide, boxArea.x - 0.05, boxArea.y - 0.05, boxArea.w + 0.1, boxArea.h + 0.1, "FFFFFF", C.border, true);
  slide.addImage({ path: image, x, y, w, h });
}

async function build() {
  for (const img of Object.values(IMAGES)) {
    if (!fs.existsSync(img)) throw new Error(`Missing image: ${img}`);
  }

  const pptx = deck();

  // Slide 1: cover
  let s = pptx.addSlide();
  s.background = { color: C.bg };
  box(s, 0, 0, 5.45, 7.5, C.ink, C.ink, false);
  t(s, "从豆包查题到\n智学助手", {
    x: 0.8,
    y: 1.1,
    w: 4.2,
    h: 1.1,
    fontSize: 30,
    bold: true,
    color: "FFFFFF",
  });
  t(s, "一个学生做教育智能体的\n心路历程", {
    x: 0.82,
    y: 2.62,
    w: 4.3,
    h: 0.7,
    fontSize: 17,
    color: "DBEAFE",
  });
  t(s, "起点很简单：我只是觉得查题、拍照、解析、回到题目之间的切换太麻烦了。", {
    x: 0.84,
    y: 3.8,
    w: 4.2,
    h: 0.72,
    fontSize: 12.4,
    color: "E2E8F0",
  });
  box(s, 0.82, 5.08, 1.15, 0.42, C.teal, C.teal, true);
  t(s, "查题", { x: 0.82, y: 5.18, w: 1.15, h: 0.16, fontSize: 9.5, bold: true, color: "FFFFFF", align: "center" });
  box(s, 2.06, 5.08, 1.15, 0.42, "334155", "334155", true);
  t(s, "整合", { x: 2.06, y: 5.18, w: 1.15, h: 0.16, fontSize: 9.5, bold: true, color: "FFFFFF", align: "center" });
  box(s, 3.3, 5.08, 1.55, 0.42, C.accent, C.accent, true);
  t(s, "做成产品", { x: 3.3, y: 5.18, w: 1.55, h: 0.16, fontSize: 9.5, bold: true, color: "FFFFFF", align: "center" });
  t(s, "张凯 · 23小教", { x: 0.84, y: 6.55, w: 2.4, h: 0.2, fontSize: 10, color: "C7D2FE" });
  await contain(s, IMAGES.main, { x: 5.95, y: 0.88, w: 6.4, h: 5.7 });
  box(s, 6.25, 6.15, 5.6, 0.52, "FFFFFF", C.border, true);
  t(s, "我想做的，不是另一个聊天框，而是一个真正能用的学习工具。", {
    x: 6.5,
    y: 6.31,
    w: 5.1,
    h: 0.16,
    fontSize: 11,
    color: C.title,
    bold: true,
    align: "center",
  });

  // Slide 2: why build
  s = pptx.addSlide();
  s.background = { color: C.bg };
  title(s, "1. 起点：我只是觉得麻烦", "一开始没有那么宏大，就是想把查题这件事做顺一点。");
  card(
    s,
    0.86,
    1.5,
    4.45,
    1.08,
    "查题流程太碎",
    "用豆包搜数学题解析时，往往要先打开摄像机，再拍照、再提问，步骤有点散。",
    1
  );
  card(
    s,
    0.86,
    2.82,
    4.45,
    1.08,
    "问题总要重说",
    "每次都要重新描述题目、上下文和需求，效率并不高。",
    2
  );
  card(
    s,
    0.86,
    4.14,
    4.45,
    1.08,
    "所以我开始想",
    "能不能把拍照、提问、解析这些能力整合到同一个页面里。",
    3
  );
  box(s, 0.86, 5.68, 4.45, 0.48, C.cream2, C.cream2, true);
  t(s, "动机很朴素：我只是想少折腾一点。", {
    x: 1.08,
    y: 5.85,
    w: 4.0,
    h: 0.14,
    fontSize: 9.5,
    color: C.accent,
    bold: true,
    align: "center",
  });
  box(s, 6.05, 1.18, 6.45, 5.3, "FFFFFF", C.border, true);
  t(s, "一个很简单的想法", {
    x: 6.42,
    y: 1.54,
    w: 3.0,
    h: 0.2,
    fontSize: 16,
    bold: true,
    color: C.title,
  });
  t(s, "把“拍照、提问、解析、回到题目”放在同一个学习现场。", {
    x: 6.42,
    y: 2.05,
    w: 5.5,
    h: 0.5,
    fontSize: 15,
    color: C.body,
  });
  box(s, 6.42, 3.0, 1.42, 0.58, C.bg2, C.bg2, true);
  t(s, "拍照", { x: 6.42, y: 3.18, w: 1.42, h: 0.14, fontSize: 10, bold: true, color: C.accent, align: "center" });
  box(s, 8.0, 3.0, 1.42, 0.58, "E0F2FE", "E0F2FE", true);
  t(s, "提问", { x: 8.0, y: 3.18, w: 1.42, h: 0.14, fontSize: 10, bold: true, color: C.teal, align: "center" });
  box(s, 9.58, 3.0, 1.42, 0.58, "FEF3C7", "FEF3C7", true);
  t(s, "解析", { x: 9.58, y: 3.18, w: 1.42, h: 0.14, fontSize: 10, bold: true, color: "92400E", align: "center" });
  box(s, 11.16, 3.0, 1.0, 0.58, "DCFCE7", "DCFCE7", true);
  t(s, "整合", { x: 11.16, y: 3.18, w: 1.0, h: 0.14, fontSize: 10, bold: true, color: "166534", align: "center" });
  t(s, "我真正想做的，是减少切换成本。", {
    x: 6.42,
    y: 4.12,
    w: 4.8,
    h: 0.22,
    fontSize: 13.5,
    color: C.title,
    bold: true,
  });
  box(s, 6.42, 4.58, 5.75, 1.22, C.cream, C.cream, true);
  t(s, "后来我回头看，这其实已经不是单纯的“查题工具”了，\n而是我第一次认真想把学习流程做成一个产品。", {
    x: 6.72,
    y: 4.92,
    w: 5.15,
    h: 0.6,
    fontSize: 11.2,
    color: C.body,
  });
  footer(s, "起点：把零散的查题动作合在一起。");

  // Slide 3: boundary and tools
  s = pptx.addSlide();
  s.background = { color: C.bg };
  title(s, "2. 我开始追问：AI 的边界在哪", "如果 AI 能帮我查题、讲题、写代码，那它到底能走多远？");
  card(s, 0.86, 1.48, 3.45, 1.0, "AI 像老师", "有问题直接问就行，它可以解释，也可以追着你补概念。", 1);
  card(s, 0.86, 2.72, 3.45, 1.0, "AI 像搜索引擎", "它不只是搜答案，还能把知识讲开，省掉很多翻找成本。", 2);
  card(s, 0.86, 3.96, 3.45, 1.0, "AI 也能进开发", "我开始想，能不能把它真正用到产品实现里。", 3);
  box(s, 0.86, 5.38, 3.45, 0.56, C.cream2, C.cream2, true);
  t(s, "我对 AI 的理解，也是在这个阶段被重新打开的。", {
    x: 1.08,
    y: 5.58,
    w: 3.0,
    h: 0.14,
    fontSize: 9.5,
    color: "92400E",
    bold: true,
    align: "center",
  });
  box(s, 4.78, 1.42, 3.0, 4.68, "FFFFFF", C.border, true);
  t(s, "最开始的方式", {
    x: 5.08,
    y: 1.78,
    w: 2.2,
    h: 0.2,
    fontSize: 15,
    bold: true,
    color: C.title,
    align: "center",
  });
  box(s, 5.15, 2.4, 1.55, 0.62, C.bg2, C.bg2, true);
  t(s, "网页对话", { x: 5.15, y: 2.62, w: 1.55, h: 0.14, fontSize: 10.5, bold: true, color: C.accent, align: "center" });
  box(s, 5.15, 3.25, 1.55, 0.62, "E2E8F0", "E2E8F0", true);
  t(s, "重复描述", { x: 5.15, y: 3.47, w: 1.55, h: 0.14, fontSize: 10.5, bold: true, color: C.body, align: "center" });
  box(s, 5.15, 4.1, 1.55, 0.62, C.cream2, C.cream2, true);
  t(s, "效率太低", { x: 5.15, y: 4.32, w: 1.55, h: 0.14, fontSize: 10.5, bold: true, color: "92400E", align: "center" });
  box(s, 6.95, 2.4, 0.36, 2.32, C.teal, C.teal, true);
  t(s, "→", { x: 6.95, y: 3.34, w: 0.36, h: 0.16, fontSize: 16, bold: true, color: "FFFFFF", align: "center" });
  box(s, 7.55, 2.38, 2.0, 1.06, "FFFFFF", C.border, true);
  t(s, "Cursor / Claude Code", { x: 7.72, y: 2.69, w: 1.65, h: 0.14, fontSize: 11.2, bold: true, color: C.title, align: "center" });
  box(s, 7.55, 3.75, 2.0, 1.06, "FFFFFF", C.border, true);
  t(s, "vibe coding", { x: 7.72, y: 4.06, w: 1.65, h: 0.14, fontSize: 11.2, bold: true, color: C.teal, align: "center" });
  box(s, 7.55, 5.12, 2.0, 0.78, "E0F2FE", "E0F2FE", true);
  t(s, "更快地把想法变成代码", { x: 7.72, y: 5.38, w: 1.65, h: 0.14, fontSize: 9.4, color: C.accent, align: "center" });
  box(s, 10.0, 1.42, 2.2, 4.68, C.ink, C.ink, true);
  t(s, "这时我第一次明显感觉到：", {
    x: 10.28,
    y: 1.86,
    w: 1.7,
    h: 0.38,
    fontSize: 15.2,
    bold: true,
    color: "FFFFFF",
    align: "center",
  });
  t(s, "AI 不只是\n问答工具，\n它也能成为\n开发协作者。", {
    x: 10.28,
    y: 2.56,
    w: 1.7,
    h: 1.48,
    fontSize: 15,
    bold: true,
    color: "DBEAFE",
    align: "center",
  });
  box(s, 10.25, 4.76, 1.7, 0.74, C.teal, C.teal, true);
  t(s, "问题来了，\n我就直接问。", {
    x: 10.47,
    y: 4.98,
    w: 1.25,
    h: 0.22,
    fontSize: 9.2,
    bold: true,
    color: "FFFFFF",
    align: "center",
  });
  footer(s, "我开始真正把 AI 当成老师、搜索引擎和协作者来看。");

  // Slide 4: v1
  s = pptx.addSlide();
  s.background = { color: C.bg };
  title(s, "3. 第一版智学助手，只先跑通最小闭环", "那时候我做的东西很简单，但它真的开始“能用了”。");
  await contain(s, IMAGES.ai, { x: 0.86, y: 1.28, w: 4.0, h: 5.72 });
  card(s, 5.2, 1.42, 2.55, 1.18, "只有两个环节", "截图提问 + AI回答，先把最基础的交互跑通。", 1);
  card(s, 5.2, 2.88, 2.55, 1.18, "先做最小闭环", "我想先确认：它能不能真的解决一点学习问题。", 2);
  card(s, 5.2, 4.34, 2.55, 1.18, "第一次踩坑", "不是所有模型都支持图片输入，要先选对支持图像的模型。", 3);
  box(s, 8.48, 1.46, 4.0, 4.2, "FFFFFF", C.border, true);
  t(s, "我当时的感受", {
    x: 8.82,
    y: 1.84,
    w: 2.2,
    h: 0.22,
    fontSize: 16,
    bold: true,
    color: C.title,
  });
  t(s, "第一次看到它真的把题目看懂、\n又真的能回一句像样的回答时，\n我其实挺兴奋的。", {
    x: 8.82,
    y: 2.42,
    w: 3.3,
    h: 1.0,
    fontSize: 13.4,
    color: C.body,
  });
  box(s, 8.82, 4.18, 3.25, 0.86, C.cream2, C.cream2, true);
  t(s, "v1 不是完整产品，\n但它让我第一次看见了方向。", {
    x: 9.08,
    y: 4.48,
    w: 2.75,
    h: 0.26,
    fontSize: 10.6,
    bold: true,
    color: "92400E",
    align: "center",
  });
  footer(s, "第一版先活下来，再谈做得好不好。");

  // Slide 5: memory
  s = pptx.addSlide();
  s.background = { color: C.bg };
  title(s, "4. 我开始想让它记住", "如果答案刷新就没了，那它就还不够像一个真正的学习工具。");
  box(s, 0.84, 1.46, 5.25, 1.18, "FFFFFF", C.border, true);
  await contain(s, IMAGES.marker, { x: 0.98, y: 1.58, w: 4.95, h: 0.9 }, false);
  box(s, 6.48, 1.44, 5.9, 1.2, "FFFFFF", C.border, true);
  t(s, "我发现一个很现实的问题：", {
    x: 6.82,
    y: 1.8,
    w: 2.8,
    h: 0.2,
    fontSize: 15.8,
    bold: true,
    color: C.title,
  });
  t(s, "回答一刷新就没有了，\n学生也很难在下一次复习时接上前面的对话。", {
    x: 6.82,
    y: 2.2,
    w: 4.8,
    h: 0.42,
    fontSize: 11.4,
    color: C.body,
  });
  card(s, 0.88, 3.0, 3.58, 1.18, "先保存问答", "把回答留住，后面可以回看，也可以继续追问。", 1);
  card(s, 4.62, 3.0, 3.58, 1.18, "再做学生画像", "让系统知道“这个学生大概学到哪了”。", 2);
  card(s, 8.36, 3.0, 3.58, 1.18, "最后形成记忆", "它不再只是一次性问答，而是能陪着学习的工具。", 3);
  box(s, 0.88, 4.74, 11.06, 1.35, C.ink, C.ink, true);
  t(s, "问答记录  →  学生画像  →  连续学习", {
    x: 1.3,
    y: 5.1,
    w: 10.2,
    h: 0.22,
    fontSize: 18,
    bold: true,
    color: "FFFFFF",
    align: "center",
  });
  t(s, "我希望它留下来的，不只是答案，还有学习过程。", {
    x: 2.0,
    y: 5.48,
    w: 8.8,
    h: 0.18,
    fontSize: 10.2,
    color: "C7D2FE",
    align: "center",
  });
  footer(s, "从一次问答，慢慢走向连续记录。");

  // Slide 6: reflection
  s = pptx.addSlide();
  s.background = { color: C.bg };
  title(s, "5. 现在我怎么理解这件事", "做这个项目以后，我对 AI、开发和学习的理解都变了。");
  box(s, 0.86, 1.45, 3.45, 4.9, "FFFFFF", C.border, true);
  box(s, 4.56, 1.45, 3.45, 4.9, "FFFFFF", C.border, true);
  box(s, 8.26, 1.45, 3.85, 4.9, "FFFFFF", C.border, true);
  t(s, "AI 是很好的老师", {
    x: 1.12,
    y: 1.88,
    w: 2.9,
    h: 0.22,
    fontSize: 15.2,
    bold: true,
    color: C.title,
    align: "center",
  });
  t(s, "有问题直接问，\n它能解释，也能追着你补概念。", {
    x: 1.14,
    y: 2.42,
    w: 2.86,
    h: 0.58,
    fontSize: 12.1,
    color: C.body,
    align: "center",
  });
  t(s, "AI 也是大型搜索引擎", {
    x: 4.82,
    y: 1.88,
    w: 2.9,
    h: 0.22,
    fontSize: 15.2,
    bold: true,
    color: C.title,
    align: "center",
  });
  t(s, "它不只是找答案，\n还能把知识讲开，\n省掉很多反复翻找的成本。", {
    x: 4.84,
    y: 2.42,
    w: 2.86,
    h: 0.76,
    fontSize: 12.1,
    color: C.body,
    align: "center",
  });
  t(s, "AI 还是开发协作者", {
    x: 8.54,
    y: 1.88,
    w: 3.5,
    h: 0.22,
    fontSize: 15.2,
    bold: true,
    color: C.title,
    align: "center",
  });
  await contain(s, IMAGES.graph, { x: 8.56, y: 2.38, w: 3.48, h: 2.1 }, false);
  t(s, "我更像是需求提出者和方向把关的人，\nAI 负责实现很多具体动作。", {
    x: 8.6,
    y: 4.78,
    w: 3.36,
    h: 0.56,
    fontSize: 11.6,
    color: C.body,
    align: "center",
  });
  box(s, 8.56, 5.62, 3.48, 0.58, C.cream, C.cream, true);
  t(s, "AI 不是第一作者，但它是我很重要的协作者。", {
    x: 8.82,
    y: 5.84,
    w: 2.95,
    h: 0.14,
    fontSize: 9.6,
    color: "92400E",
    bold: true,
    align: "center",
  });
  box(s, 0.86, 6.56, 11.24, 0.34, C.teal, C.teal, true);
  t(s, "我做的事情，本质上是把一个真实的学习麻烦，慢慢做成一个能用、能记、能继续迭代的产品。", {
    x: 1.05,
    y: 6.65,
    w: 10.85,
    h: 0.12,
    fontSize: 9.2,
    color: "FFFFFF",
    bold: true,
    align: "center",
  });

  await pptx.writeFile({ fileName: path.join(OUT_DIR, "模板B_心路历程版.pptx") });
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
