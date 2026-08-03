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

    # JWT 密钥
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")

    # 反馈邮件 SMTP
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # Neo4j 连接配置
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

    @classmethod
    def ensure_dirs(cls):
        cls.TEXTBOOK_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
