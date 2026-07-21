from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MODULE_DIR = SCRIPT_DIR.parents[1]
ENV_PATHS = [REPO_ROOT / ".env", MODULE_DIR / ".env"]


def _read_dotenv_value(key: str) -> str:
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    return ""


def _read_windows_user_env(key: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as env_key:
            value, _ = winreg.QueryValueEx(env_key, key)
            return str(value).strip()
    except Exception:
        return ""


def load_env_value(key: str) -> str:
    key = str(key or "").strip()
    if not key:
        return ""
    value = _read_dotenv_value(key)
    if value:
        return value
    if os.environ.get(key):
        return str(os.environ[key]).strip()
    return _read_windows_user_env(key)


def _unique(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if isinstance(value, list):
            nested = _unique(value)
            for item in nested:
                if item not in seen:
                    seen.add(item)
                    output.append(item)
            continue
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def load_api_key(llm_config: dict[str, Any]) -> str:
    candidates = _unique(
        [
            llm_config.get("api_key_env"),
            llm_config.get("env_api_key"),
            llm_config.get("fallback_env_api_keys", []),
            "OPENAI_API_KEY",
            "LLM_API_KEY",
            "DEEPSEEK_API_KEY",
        ]
    )
    for name in candidates:
        value = load_env_value(name)
        if value:
            return value
    return ""


def resolve_base_url(cli_base_url: str, llm_config: dict[str, Any], default: str = "http://120.224.38.132:7361/v1") -> str:
    if cli_base_url:
        return cli_base_url
    candidates = _unique(
        [
            llm_config.get("base_url_env"),
            llm_config.get("env_base_url"),
            llm_config.get("fallback_env_base_urls", []),
            "OPENAI_BASE_URL",
            "LLM_BASE_URL",
            "DEEPSEEK_API_BASE",
        ]
    )
    for name in candidates:
        value = load_env_value(name)
        if value:
            return value
    return str(llm_config.get("base_url") or default)


def resolve_timeout(cli_timeout: float | None, llm_config: dict[str, Any], default: float = 180.0) -> float:
    if cli_timeout is not None:
        return float(cli_timeout)
    return float(llm_config.get("timeout_seconds", llm_config.get("timeout", default)))
