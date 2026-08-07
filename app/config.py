import os
from pathlib import Path

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# Read env file manually if python-dotenv fails
if ENV_FILE.exists():
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(ENV_FILE)

DATA_DIR = BASE_DIR / "data"
TEXTBOOK_DIR = DATA_DIR / "textbooks"


class Config:
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    TEXTBOOK_DIR: Path = TEXTBOOK_DIR

    # QA回答用LLM（文字提问）
    QA_LLM_API_KEY: str = os.getenv("QA_LLM_API_KEY", "")
    QA_LLM_API_BASE: str = os.getenv("QA_LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QA_LLM_MODEL: str = os.getenv("QA_LLM_MODEL", "qwen3.6-plus")
    EXERCISE_AUTHOR_MODEL: str = os.getenv("EXERCISE_AUTHOR_MODEL", QA_LLM_MODEL)
    EXERCISE_REVIEWER_MODEL: str = os.getenv("EXERCISE_REVIEWER_MODEL", QA_LLM_MODEL)
    EXERCISE_GRADER_MODEL: str = os.getenv("EXERCISE_GRADER_MODEL", QA_LLM_MODEL)
    EXERCISE_MAX_CONCURRENCY: int = int(os.getenv("EXERCISE_MAX_CONCURRENCY", "3"))
    INTERVENTION_PLANNER_MODEL: str = os.getenv("INTERVENTION_PLANNER_MODEL", QA_LLM_MODEL)
    INTERVENTION_MAX_CONCURRENCY: int = int(os.getenv("INTERVENTION_MAX_CONCURRENCY", "1"))
    TEACHING_CONTROLLER_MODE: str = os.getenv(
        "TEACHING_CONTROLLER_MODE", "shadow"
    ).strip().lower()

    TOOL_MAX_MODEL_ROUNDS: int = max(1, int(os.getenv("TOOL_MAX_MODEL_ROUNDS", "5")))
    TOOL_MAX_TOTAL_CALLS: int = max(1, int(os.getenv("TOOL_MAX_TOTAL_CALLS", "8")))
    TOOL_DEFAULT_TIMEOUT_SECONDS: float = max(0.1, float(os.getenv("TOOL_DEFAULT_TIMEOUT_SECONDS", "15")))
    TOOL_MAX_CONSECUTIVE_FAILURE_ROUNDS: int = max(1, int(os.getenv("TOOL_MAX_CONSECUTIVE_FAILURE_ROUNDS", "2")))
    VISION_EXTRACTION_CONFIDENCE: float = float(os.getenv("VISION_EXTRACTION_CONFIDENCE", "0.70"))
    QA_TEXT_TURN_TIMEOUT_SECONDS: float = max(0.0, float(os.getenv("QA_TEXT_TURN_TIMEOUT_SECONDS", "0")))
    QA_SCREENSHOT_TURN_TIMEOUT_SECONDS: float = max(0.0, float(os.getenv("QA_SCREENSHOT_TURN_TIMEOUT_SECONDS", "0")))

    # 截图问答用 VL 模型（DashScope 原生 MultiModal API）
    QA_VL_MODEL: str = os.getenv("QA_VL_MODEL", "qwen3.6-plus")

    # 用户画像用 LLM（诊断分析）
    PROFILE_LLM_API_KEY: str = os.getenv("PROFILE_LLM_API_KEY", "")
    PROFILE_LLM_API_BASE: str = os.getenv("PROFILE_LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    PROFILE_LLM_MODEL: str = os.getenv("PROFILE_LLM_MODEL", "qwen3.6-flash")

    # Formula conversion providers, attempted in this fixed order: local,
    # Cloudflare Workers AI, then the existing profile model.
    FORMULA_LOCAL_API_BASE: str = os.getenv("FORMULA_LOCAL_API_BASE", "")
    FORMULA_LOCAL_API_KEY: str = os.getenv("FORMULA_LOCAL_API_KEY", "local")
    FORMULA_LOCAL_MODEL: str = os.getenv("FORMULA_LOCAL_MODEL", "")
    FORMULA_CLOUDFLARE_ACCOUNT_ID: str = os.getenv("FORMULA_CLOUDFLARE_ACCOUNT_ID", "")
    FORMULA_CLOUDFLARE_API_TOKEN: str = os.getenv("FORMULA_CLOUDFLARE_API_TOKEN", "")
    FORMULA_CLOUDFLARE_MODEL: str = os.getenv(
        "FORMULA_CLOUDFLARE_MODEL", "@cf/qwen/qwen3-30b-a3b-fp8"
    )
    FORMULA_EXISTING_API_BASE: str = (
        os.getenv("FORMULA_EXISTING_API_BASE") or PROFILE_LLM_API_BASE
    )
    FORMULA_EXISTING_API_KEY: str = (
        os.getenv("FORMULA_EXISTING_API_KEY") or PROFILE_LLM_API_KEY
    )
    FORMULA_EXISTING_MODEL: str = (
        os.getenv("FORMULA_EXISTING_MODEL") or PROFILE_LLM_MODEL
    )
    FORMULA_CONVERSION_TIMEOUT_SECONDS: float = float(
        os.getenv("FORMULA_CONVERSION_TIMEOUT_SECONDS", "8")
    )

    # 认知诊断 V2 发布档位：shadow（只记证据）/ stage_only / full
    DIAGNOSIS_V2_MODE: str = os.getenv("DIAGNOSIS_V2_MODE", "shadow").strip().lower()

    # 对话概率状态 V1：仅 shadow 写入独立状态表，不影响现有画像。
    DIALOGUE_STATE_MODE: str = os.getenv("DIALOGUE_STATE_MODE", "shadow").strip().lower()
    DIALOGUE_STATE_MODEL_VERSION: str = os.getenv(
        "DIALOGUE_STATE_MODEL_VERSION", "ordinal-bayes-v1"
    ).strip()


    DB_PATH: str = os.getenv("AI_MATH_DB_PATH", str(DATA_DIR / "learning.db"))
    DB_JOURNAL_MODE: str = os.getenv("AI_MATH_DB_JOURNAL_MODE", "WAL").strip().upper()

    # JWT 密钥
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")

    # 反馈邮件 SMTP
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # Neo4j 连接配置
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

    # 数学动画：Web API 只负责入队和签名，Manim 运行在独立 Worker。
    VISUALIZATION_REDIS_URL: str = os.getenv("VISUALIZATION_REDIS_URL", "redis://localhost:6379/0")
    VISUALIZATION_QUEUE: str = os.getenv("VISUALIZATION_QUEUE", "math-visualization")
    VISUALIZATION_S3_ENDPOINT: str = os.getenv("VISUALIZATION_S3_ENDPOINT", "http://localhost:9000")
    VISUALIZATION_S3_REGION: str = os.getenv("VISUALIZATION_S3_REGION", "us-east-1")
    VISUALIZATION_S3_BUCKET: str = os.getenv("VISUALIZATION_S3_BUCKET", "ai-math-visualizations")
    VISUALIZATION_S3_ACCESS_KEY: str = os.getenv("VISUALIZATION_S3_ACCESS_KEY", "minioadmin")
    VISUALIZATION_S3_SECRET_KEY: str = os.getenv("VISUALIZATION_S3_SECRET_KEY", "minioadmin")
    VISUALIZATION_URL_TTL_SECONDS: int = int(os.getenv("VISUALIZATION_URL_TTL_SECONDS", "900"))
    VISUALIZATION_MAX_OUTPUT_BYTES: int = int(os.getenv("VISUALIZATION_MAX_OUTPUT_BYTES", str(25 * 1024 * 1024)))
    VISUALIZATION_WORKER_CONCURRENCY: int = max(1, int(os.getenv("VISUALIZATION_WORKER_CONCURRENCY", "1")))

    @classmethod
    def ensure_dirs(cls):
        cls.TEXTBOOK_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
