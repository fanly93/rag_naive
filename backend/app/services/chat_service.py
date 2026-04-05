from __future__ import annotations

import json
from typing import Literal
from typing import Iterator

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

    def _extract_content_text(self, content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return ""

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
        content = ""
        if isinstance(choices[0], dict):
            content = self._extract_content_text(choices[0].get("message", {}).get("content"))
        if not content:
            raise RuntimeError("chat completion response missing content")
        return content.strip(), selected_provider, selected_model

    def stream_complete(
        self,
        query: str,
        context_chunks: list[tuple[int, str]],
        provider: ChatProvider | None = None,
        model: str | None = None,
    ) -> tuple[Iterator[str], ChatProvider, str]:
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
            "stream": True,
        }
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        def _iter() -> Iterator[str]:
            with httpx.Client(timeout=120.0) as client:
                with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        body = response.read().decode("utf-8", errors="ignore")
                        raise RuntimeError(
                            f"chat stream failed: {response.status_code} - {body}"
                        )
                    for line in response.iter_lines():
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            item = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        choices = item.get("choices") or []
                        if not choices or not isinstance(choices[0], dict):
                            continue
                        delta = choices[0].get("delta", {})
                        text = self._extract_content_text(delta.get("content")) if isinstance(delta, dict) else ""
                        if text:
                            yield text

        return _iter(), selected_provider, selected_model


chat_service = ChatService()
