from __future__ import annotations

from typing import Literal

import httpx

from app.core.config import get_settings

ChatProvider = Literal["deepseek", "openai", "dashscope"]


class ChatService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def _default_provider(self) -> ChatProvider:
        provider = self._settings.default_chat_provider.strip().lower()
        if provider in {"deepseek", "openai", "dashscope"}:
            return provider  # type: ignore[return-value]
        return "deepseek"

    def _provider_config(self, provider: ChatProvider) -> tuple[str, str, str]:
        if provider == "deepseek":
            deepseek_model = self._settings.deepseek_chat_model or self._settings.model
            return (
                self._settings.deepseek_api_key,
                self._settings.deepseek_base_url,
                deepseek_model,
            )
        if provider == "openai":
            return (
                self._settings.openai_api_key,
                self._settings.openai_base_url,
                self._settings.openai_chat_model,
            )
        return (
            self._settings.dashscope_api_key,
            self._settings.dashscope_base_url,
            self._settings.dashscope_chat_model,
        )

    def _build_messages(self, query: str, context_blocks: list[str]) -> list[dict[str, str]]:
        if not context_blocks:
            return [
                {
                    "role": "system",
                    "content": "你是RAG问答助手。请直接、准确回答用户问题，若不确定请明确说明。",
                },
                {"role": "user", "content": query},
            ]
        joined_context = "\n\n".join(context_blocks)
        return [
            {
                "role": "system",
                "content": (
                    "你是RAG问答助手。请严格基于提供的知识片段回答。"
                    "当引用片段时，使用 [1][2][3] 这样的引用编号标记。"
                    "如果片段信息不足，请明确告知。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"问题：{query}\n\n"
                    f"知识片段：\n{joined_context}\n\n"
                    "请输出简洁中文回答，并在对应句子后标注引用编号。"
                ),
            },
        ]

    def complete(
        self,
        query: str,
        context_chunks: list[tuple[int, str]],
        provider: ChatProvider | None = None,
        model: str | None = None,
    ) -> tuple[str, ChatProvider, str]:
        selected_provider = provider or self._default_provider()
        api_key, base_url, default_model = self._provider_config(selected_provider)
        if not api_key:
            raise ValueError(f"{selected_provider} API key is required.")
        if not base_url:
            raise ValueError(f"{selected_provider} base url is required.")
        selected_model = model.strip() if model else default_model
        if not selected_model:
            raise ValueError(f"{selected_provider} model is required.")

        context_blocks = [f"[{index}] {content}" for index, content in context_chunks]
        payload = {
            "model": selected_model,
            "messages": self._build_messages(query=query, context_blocks=context_blocks),
            "temperature": 0.2,
        }
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        with httpx.Client(timeout=60.0) as client:
            response = client.post(endpoint, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"chat completion failed: {response.status_code} - {response.text}")
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("chat completion response missing choices")
        content = (
            choices[0].get("message", {}).get("content")
            if isinstance(choices[0], dict)
            else None
        )
        if not content or not isinstance(content, str):
            raise RuntimeError("chat completion response missing content")
        return content.strip(), selected_provider, selected_model


chat_service = ChatService()
