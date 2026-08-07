"""
大模型服务 — 使用 OpenAI SDK 支持流式与异步非流式输出
"""
from openai import OpenAI, AsyncOpenAI
from app.config import config
from typing import Any


class LLMService:
    """统一的LLM服务，支持QA和Profile两个独立配置"""

    def __init__(self):
        # QA用LLM客户端（同步，用于流式 SSE）
        self.qa_client = None
        if config.QA_LLM_API_KEY:
            self.qa_client = OpenAI(
                api_key=config.QA_LLM_API_KEY,
                base_url=config.QA_LLM_API_BASE
            )
            print(f"[OK] QA LLM client initialized (model: {config.QA_LLM_MODEL})")
        else:
            print("[WARN] QA_LLM_API_KEY not configured")

        self.qa_async = None
        if config.QA_LLM_API_KEY:
            self.qa_async = AsyncOpenAI(
                api_key=config.QA_LLM_API_KEY,
                base_url=config.QA_LLM_API_BASE,
            )

        # 用户画像用LLM客户端（同步，遗留兼容）
        self.profile_client = None
        if config.PROFILE_LLM_API_KEY:
            self.profile_client = OpenAI(
                api_key=config.PROFILE_LLM_API_KEY,
                base_url=config.PROFILE_LLM_API_BASE
            )
            print(f"[OK] Profile LLM client initialized (model: {config.PROFILE_LLM_MODEL})")
        else:
            print("[WARN] PROFILE_LLM_API_KEY not configured")

        # Phase 2: 异步 Profile 客户端（不阻塞事件循环）
        self.profile_async = None
        if config.PROFILE_LLM_API_KEY:
            self.profile_async = AsyncOpenAI(
                api_key=config.PROFILE_LLM_API_KEY,
                base_url=config.PROFILE_LLM_API_BASE
            )
            print(f"[OK] Profile Async LLM client initialized (model: {config.PROFILE_LLM_MODEL})")

        # Practice workers run independently from profile diagnosis.  Keeping a
        # separate async client prevents a background exercise call from
        # changing the diagnosis model or blocking the QA event loop.
        self.qa_async = None
        if config.QA_LLM_API_KEY:
            self.qa_async = AsyncOpenAI(
                api_key=config.QA_LLM_API_KEY,
                base_url=config.QA_LLM_API_BASE,
            )

    def is_qa_available(self) -> bool:
        return self.qa_client is not None

    def is_profile_available(self) -> bool:
        return self.profile_client is not None

    def stream_chat(self, messages: list, model: str = None, enable_thinking: bool = True):
        """
        流式调用 - 使用 OpenAI SDK（QA用）

        Args:
            enable_thinking: 是否启用思考过程输出（Qwen3 Thinking 模型支持）
        """
        if not self.qa_client:
            raise RuntimeError("QA LLM 服务未初始化")

        # Qwen3 Thinking 模型通过 extra_body.enable_thinking 启用思考过程
        extra_body = {}
        if enable_thinking:
            extra_body["enable_thinking"] = True

        return self.qa_client.chat.completions.create(
            model=model or config.QA_LLM_MODEL,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
            temperature=0.7,
            extra_body=extra_body if extra_body else None,
        )

    def chat(self, messages: list, model: str = None, use_profile: bool = False,
             response_format: dict = None, temperature: float = 0.3):
        """
        非流式调用

        Args:
            use_profile: True则使用Profile LLM，False使用QA LLM
            response_format: JSON响应格式，如 {"type": "json_object"}
            temperature: 温度参数
        """
        client = self.profile_client if use_profile else self.qa_client
        if not client:
            raise RuntimeError("LLM 服务未初始化")

        model_name = config.PROFILE_LLM_MODEL if use_profile else config.QA_LLM_MODEL

        kwargs = {
            "model": model or model_name,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        return client.chat.completions.create(**kwargs)

    def chat_with_tools(
        self,
        messages: list,
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> Any:
        """非流式调用，支持 Function Calling tools 参数。

        返回 OpenAI 响应对象，包含 choices[0].finish_reason
        和 choices[0].message.tool_calls。
        """
        if not self.qa_client:
            raise RuntimeError("QA LLM 服务未初始化")

        return self.qa_client.chat.completions.create(
            model=model or config.QA_LLM_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=False,
            temperature=temperature,
        )

    def vision_chat(
        self,
        image_data: str,
        prompt: str,
        *,
        stream: bool = False,
        temperature: float = 0.1,
    ) -> Any:
        """Call the configured multimodal model through the QA endpoint."""
        if not self.qa_client:
            raise RuntimeError("QA LLM service is not initialized")
        return self.qa_client.chat.completions.create(
            model=config.QA_VL_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data}},
                    {"type": "text", "text": prompt},
                ],
            }],
            stream=stream,
            temperature=temperature,
        )

    async def chat_with_tools_async(
        self,
        messages: list,
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
        tool_choice: str = "auto",
    ) -> Any:
        """Async OpenAI-compatible function calling used by ToolRuntime."""
        if not self.qa_async:
            raise RuntimeError("QA LLM 服务未初始化")
        return await self.qa_async.chat.completions.create(
            model=model or config.QA_LLM_MODEL,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            stream=False,
            temperature=temperature,
        )

    async def chat_async(self, messages: list, model: str = None, temperature: float = 0.3,
                         response_format: dict = None) -> str:
        """
        异步非流式调用 — 不阻塞 FastAPI 事件循环。

        用于 exercise submit 批改、错因分析、insight 生成等非流式场景。
        使用 AsyncOpenAI 客户端，async handler 中直接 await 即可。
        """
        if not self.profile_async:
            raise RuntimeError("Profile Async LLM 服务未初始化")

        kwargs = {
            "model": model or config.PROFILE_LLM_MODEL,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self.profile_async.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def chat_qa_async(self, messages: list, model: str = None, temperature: float = 0.2,
                            response_format: dict = None) -> str:
        """Async QA-model call for isolated practice planning/grading workers."""
        if not self.qa_async:
            raise RuntimeError("QA LLM 服务未初始化")
        kwargs = {
            "model": model or config.QA_LLM_MODEL,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format
        response = await self.qa_async.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


llm_service = LLMService()
