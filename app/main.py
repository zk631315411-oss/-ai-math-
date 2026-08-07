import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.db import init_db
from app.routers import chat, chat_tree, qa, auth, profile, exercise, feedback, formula, visualizations
from app.services.diagnostic_worker import diagnostic_worker_loop
from app.services.pending_worker import pending_worker_loop

# 确保目录存在
config.ensure_dirs()

# 初始化数据库
init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 2: 启动后台 Workers
    diag_task = asyncio.create_task(diagnostic_worker_loop())
    pending_task = asyncio.create_task(pending_worker_loop())
    yield
    # 关闭时取消
    for t in [diag_task, pending_task]:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="智学助手 API",
    description="AI智能学习辅助工具 - 教材问答与题目讲解",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router)
app.include_router(chat_tree.router)
app.include_router(qa.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(exercise.router)
app.include_router(feedback.router)
app.include_router(formula.router)
app.include_router(visualizations.router)


@app.get("/")
def root():
    return {"message": "智学助手 API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
