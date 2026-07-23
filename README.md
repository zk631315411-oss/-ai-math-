# 学数有道 — Textbook-Page-Embedded Intelligent Tutoring Platform

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-18-61dafb.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![Neo4j](https://img.shields.io/badge/neo4j-5.x-4581C3.svg)](https://neo4j.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> A subject-agnostic intelligent tutoring framework that embeds AI guidance directly into textbook pages. Advanced Algebra (高等代数) is the first deployed use case. The pipeline supports any structured textbook — Advanced Mathematics, Discrete Mathematics, Physics, Chemistry, Computer Science, and beyond.

**Live Demo**: http://8.134.195.113

---

## Open Core Model

This repository is **MIT licensed** and includes the full student-facing tutoring experience — textbook reading, page-anchored Q&A, knowledge graph visualization, cognitive tracking, and the exercise system. You can self-host this entire stack.

**What's not in this repo (available as commercial deployment/customization):**

- Teacher dashboard with class-level analytics
- Batch textbook pipeline (PDF → KG → deploy in one click)
- Private model hosting and school-local deployment scripts
- Integration with university SSO and LMS platforms (Moodle, Blackboard, Canvas)
- Custom competency profile dimensions per discipline

If you're a university course team or publisher interested in deploying 学数有道 for your textbook, contact: 631315411@qq.com.

---

## Why does this exist?

I built this because I was frustrated with existing AI tutors. They're all the same — a chatbot with a PDF upload button, answering questions with no awareness of where you are in the textbook, what you already know, or what you should learn next.

**The core problem**: A student reading §3.4 of an Advanced Algebra textbook who asks _"why does this theorem work?"_ needs an answer that is (a) grounded in that specific textbook's definitions, (b) aware of which prerequisite concepts the student has actually mastered, and (c) delivered with the right pedagogical strategy for their current cognitive stage.

This system solves all three.

---

## The Framework Is Subject-Agnostic

The only subject-specific components are **content** and **verification**:

| Layer | What it is | Subject-dependent? |
|-------|-----------|-------------------|
| Textbook rendering | react-pdf + page-anchored markers | Any PDF |
| Knowledge graph construction | Structured MD → Neo4j pipeline | Any structured textbook (MinerU → MD → KG) |
| Q&A with KG grounding | Neo4j whitelist constrains LLM answers | Any domain with concept prerequisites |
| Cognitive tracking | 6-stage per-concept model | Any domain |
| Competency profile | 15-dimensional assessment (5 dims × 3 rubrics) | Dimensions adapt across disciplines |
| Socratic scaffolding | 4-level cognitive apprenticeship | Any domain |
| Exercise generation | LLM + sandbox verification | **Only this needs a domain-specific sandbox** (SymPy for math, physics engine for physics, chemical equation solver for chemistry, etc.) |

### Diagnosis Version Status

The legacy Diagnosis V1 module has been archived. It used a mixed one-shot LLM assessment that directly changed student profiles. The active diagnosis architecture is V2: QA and exercise evidence are scored separately, written to an evidence ledger, then projected into long-term state by deterministic rules.

V2 is currently released in `shadow` mode. It records and audits evidence without changing student profiles; planned promotion is `shadow -> stage_only -> full`. See [`docs/design/diagnosis-README.md`](docs/design/diagnosis-README.md) for the runtime boundary and archive policy.

**Current textbooks available:**

| Textbook | PDF | KG Status | Nodes / Edges |
|----------|-----|-----------|---------------|
| 高等代数 上册 (丘维声) | ✓ | v4.4 deployed | 2980 / 4396 (9 node types, 16 edge types) |
| 高等代数 下册 (丘维声) | ✓ | v4.4 deployed (combined with 上册) | — |
| 高等数学 上册 (黄立宏) | ✓ | Structured MD ready, page map done | — |
| 高等数学 下册 (黄立宏) | ✓ | Structured MD ready, page map done | — |
| 离散数学 第六版 (耿素云) | — | Structured MD ready | — |

KG extraction uses the **v4.4 pipeline** (教材提取模块/高代提取/): 25-script multi-round LLM pipeline with rule-case extraction, knowledge grouping, AI review gating, and Neo4j import. See `教材提取模块/高代提取/v4.4_step说明.md` for full documentation.

---

## What makes this different?

| Feature | Generic AI Tutor | 学数有道 |
|---------|-----------------|----------|
| Question context | Loose chat history | **Page-anchored markers** — red/blue dots pinned to exact PDF page positions |
| Answer boundary | Model's general knowledge | **Knowledge graph constraint** — Neo4j PREREQUISITE_OF chains define legal concept scope, preventing hallucination |
| Source traceability | "I think..." | **Every answer cites the specific textbook section and theorem number** used to generate it |
| Teaching style | One-size-fits-all | **4-level cognitive apprenticeship** (Modeling → Coaching → Scaffolding → Fading), auto-adjusted per concept stage |
| Student model | "You scored 3/5" | **15-dimensional competency profile** + **6-stage cognitive tracking** per concept |
| Exercise integration | Random problem bank | **Section-contextual exercises** — problems generated from the exact page you're reading, with 3-level progressive hints + error analysis |
| Learning evidence | Chat log | **Question markers on the textbook page itself** — revisit what you asked, where you asked it, and how you progressed |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   React 18 Frontend                  │
│  PDFViewer  ChatPanel  ProfilePanel  ExercisePanel  │
│  PageMarker  KnowledgeGraph  AiBall  AuthModal      │
└──────────────────────┬──────────────────────────────┘
                       │ SSE / REST
┌──────────────────────┴──────────────────────────────┐
│                  FastAPI Backend                     │
│  ┌─────────────── Agent Layer ─────────────────┐    │
│  │  QAAgent · ExerciseAgent · (预留 Function Calling) │
│  │  BaseAgent 统一接口 · Registry 注册表        │    │
│  └──────────────────────┬───────────────────────┘    │
│                         │                             │
│  ┌──────────────────────┴───────────────────────┐    │
│  │              Services Layer                    │    │
│  │  prompt_engine · scaffolding_controller       │    │
│  │  prerequisite_checker · error_analyzer        │    │
│  │  exercise_generator · sympy_sandbox           │    │
│  │  diagnostic_worker · pending_worker           │    │
│  └───────────────────────────────────────────────┘    │
│  ┌─────────────── Data Layer ─────────────────┐    │
│  │  SQLite (12 tables)  │  Neo4j (2,980 nodes)  │    │
│  │  math_profiles       │  Concept · Theorem    │    │
│  │  knowledge_stages    │  USES · DERIVES       │    │
│  │  exercise_bank       │  HAS_PROPERTY · etc.  │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

### The Cognitive Loop

```
Student asks question on page 86
        │
        ▼
System identifies current section (§1.5 Cramer's Rule)
        │
        ▼
Neo4j: find ALL prerequisites for this section's concepts
        │
        ▼
SQLite: check student's knowledge_stages for each prerequisite
        │
        ▼
Prompt engine: assemble 10+ signals (whitelist + gap report + profile + history)
        │
        ▼
Scaffolding controller: select teaching level (Modeling/Coaching/Scaffolding/Fading)
        │
        ▼
LLM generates answer constrained by whitelist + pedagogical strategy
        │
        ▼
Answer streamed to student via per-turn StreamBus event bus
        │
        ├──→ SSE route consumes events → frontend
        ├──→ Persist consumer (async) → save turn record to DB
        └──→ Diagnosis consumer (real-time) → update student state
```

---

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
cd frontend && npm install
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add your LLM API keys and Neo4j credentials
```

### 3. Run

```bash
# Backend
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

### 4. Add a Textbook

```bash
# The KG pipeline processes structured Markdown into Neo4j
# 1. Convert PDF to Markdown (MinerU or similar)
# 2. Run the heading classifier to produce 5-level structured MD
# 3. Run the KG extraction pipeline (rule-based entity extraction + LLM relationship inference)
# 4. Merge into Neo4j
```

### Production

```bash
cd frontend && npm run build    # vite build → dist/
# Serve dist/ via Nginx
# Backend: systemd uvicorn (ai-math.service)
```

---

## Key Capabilities

### Smart Q&A (SSE Streaming)
- Screenshot + text questions, with streaming thinking process + answer
- Markdown + LaTeX rendering in chat
- Neo4j whitelist constrains answers to textbook scope
- **StreamBus event bus** decouples production from consumption
- Persistence is **async** — turn record saving does not block the SSE response
- Diagnosis is **real-time event-driven**
- **Agent Layer**: BaseAgent uniform interface, QAAgent, ExerciseAgent, AgentRegistry

### Page-Anchored Question Markers
- Red dots (screenshot questions) and blue dots (text questions) pinned to exact PDF page positions
- Click any marker to revisit the full Q&A thread with follow-ups
- Markers persist across sessions — your learning history lives on the page

### Dual Teaching Modes
- **Socratic mode** — guides through hints and follow-up questions (4 sub-modes: preview, exam review, connected review, unclassified)
- **Direct mode** — provides complete explanations
- Scaffolding level auto-adjusts based on student's concept mastery stage (0–5)

### 15-Dimension Competency Profile
- 5 dimensions: Mathematical Thinking, Logical Reasoning, Symbolic Operation, Multi-Representation, Problem Solving
- 3 rubrics each: Coverage, Radius, Technical
- Radar chart visualization + diagnostic history timeline

### 6-Stage Cognitive Tracking
- Each concept tracked through stages 0–5 (unfamiliar → mastered)
- Background diagnostic worker analyzes conversations (real-time via StreamBus + 30s polling fallback)
- Pending queue with debounced stage transitions

### Knowledge Graph Visualization
- Weak concepts displayed with prerequisite/dependent relationships
- Node colors encode mastery stage (red → yellow → green)
- Powered by Neo4j with v4.4 KG: 2,980 nodes, 4,396 edges, 9 node types (Concept, Theorem, Method, Formula, ProblemClass, RuleCase, ConditionExpression, Outcome, KnowledgeGroup)

### Contextual Exercise System
- LLM-generated problems from the current textbook section
- SymPy sandbox verification for computational answers
- 3-level progressive hints + LLM error analysis
- LaTeX input with matrix editor

### Tablet & Mobile
- Portrait: fullscreen PDF + floating AI ball for questions
- Screenshot cropping for mobile
- Legacy browser compatibility via IIFE PDF worker

---

## API Endpoints

### Q&A
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/qa/solve-stream` | Streaming SSE Q&A (text + screenshot) |

### Auth & Profile
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/math-profile` | 15-dimension competency profile |
| GET | `/api/auth/knowledge-graph` | Weak concept prerequisite graph |
| GET | `/api/auth/diagnostic-history` | Assessment history timeline |

### Exercises
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/exercise/generate` | Generate exercises from current textbook page |
| POST | `/api/exercise/{id}/submit` | Submit answer + LLM grading + error analysis |
| POST | `/api/exercise/{id}/hint` | Get progressive hint (3 levels) |

---

## Project Structure

```
ai-math/
├── app/
│   ├── routers/         # 6 route modules
│   ├── services/        # 10+ service modules + agents/ + qa/ 子模块
│   │   ├── agents/      # BaseAgent 统一接口 · Registry · QAAgent · ExerciseAgent
│   │   └── qa/          # StreamBus · turn_store · prompt_builder · 其他 QA 子模块
│   ├── db/              # 16 data modules
│   └── models/          # Pydantic schemas
├── frontend/src/
│   ├── components/      # 19 React components
│   └── hooks/           # Auth + textbook preference hooks
├── pipeline/            # Legacy KG construction scripts
├── 教材提取模块/         # KG extraction pipeline (v4.4: 25-script LLM pipeline)
│   ├── 高代提取/         #   Full pipeline run for 高等代数 (2,980 nodes deployed)
│   └── 正式脚本/         #   v4.1 / ima simulation experiments
└── data/                # SQLite database + textbooks
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, TailwindCSS, react-pdf, KaTeX |
| Backend | FastAPI, Uvicorn, SSE streaming |
| LLM | DashScope Qwen3.6-plus (QA), Qwen3.6-flash (diagnostic) |
| Data | SQLite WAL (12 tables), Neo4j Aura (knowledge graph) |
| Math Sandbox | SymPy |
| Deployment | Alibaba Cloud ECS, Nginx, systemd |

## License

MIT

## Citation

```bibtex
@software{xueshuyoudao2026,
  author = {Zhang Kai},
  title = {学数有道: A Textbook-Page-Embedded Intelligent Tutoring Platform},
  year = {2026},
  url = {https://github.com/zk631315411-oss/-ai-math-}
}
```
