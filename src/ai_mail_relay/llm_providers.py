"""Provider-specific adapters for calling different LLM APIs."""

from __future__ import annotations

import abc
import logging
from dataclasses import replace
from typing import Dict

import httpx

from .config import LLMConfig


LOGGER = logging.getLogger(__name__)


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BaseLLMProvider(abc.ABC):
    """Abstract base class for provider-specific adapters."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._timeout = config.request_timeout

    @abc.abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a completion for the provided prompt."""

    def _post_json(self, url: str, headers: Dict[str, str], payload: Dict) -> Dict:
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=self._timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network failure path
            status = exc.response.status_code if exc.response else None
            raise LLMProviderError(f"LLM request failed: {exc}", status_code=status) from exc
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise LLMProviderError(f"LLM request failed: {exc}") from exc


class OpenAICompatibleProvider(BaseLLMProvider):
    """Shared handler for OpenAI-style chat completion APIs."""

    def __init__(self, config: LLMConfig, endpoint_suffix: str = "/v1/chat/completions") -> None:
        super().__init__(config)
        base_url = config.endpoint.rstrip("/")
        self._url = f"{base_url}{endpoint_suffix}"

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一位专业的AI研究助理。请为忙碌的AI研究人员总结arXiv论文。"
                        "为每篇论文提供结构化的中文摘要，包括研究背景、方法、创新点、实验结果和结论。"
                        "使用清晰的Markdown格式，保持简洁专业。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

        LOGGER.debug("Calling OpenAI-compatible endpoint %s", self._url)
        data = self._post_json(self._url, headers, payload)
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(f"Unexpected response format: {data}") from exc


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config, endpoint_suffix="/v1/chat/completions")


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self, config: LLMConfig) -> None:
        # If the user left the OpenAI default endpoint, swap to DeepSeek's public endpoint.
        if config.endpoint.rstrip("/") == "https://api.openai.com":
            config = replace(config, endpoint="https://api.deepseek.com")
        super().__init__(config, endpoint_suffix="/v1/chat/completions")


class QwenProvider(OpenAICompatibleProvider):
    def __init__(self, config: LLMConfig) -> None:
        endpoint = config.endpoint.rstrip("/")
        if endpoint == "https://api.openai.com":
            config = replace(config, endpoint="https://dashscope.aliyuncs.com")
        super().__init__(config, endpoint_suffix="/compatible-mode/v1/chat/completions")


class ByteDanceProvider(OpenAICompatibleProvider):
    """ByteDance Ark/Doubao OpenAI-compatible endpoint."""

    def __init__(self, config: LLMConfig) -> None:
        endpoint = config.endpoint.rstrip("/")
        if endpoint == "https://api.openai.com":
            config = replace(config, endpoint="https://ark.cn-beijing.volces.com")
        super().__init__(config, endpoint_suffix="/api/v3/chat/completions")


class AnthropicProvider(BaseLLMProvider):
    """Adapter for Claude (Anthropic) Messages API."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        base = config.endpoint.rstrip("/")
        if base in {"", "https://api.openai.com"}:
            base = "https://api.anthropic.com"
        self._url = f"{base}/v1/messages"

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "你是一位专业的AI研究助理。请为忙碌的AI研究人员总结arXiv论文。"
                                "为每篇论文提供结构化的中文摘要，包括研究背景、方法、创新点、实验结果和结论。"
                                "使用清晰的Markdown格式，保持简洁专业。\n\n"
                                f"{prompt}"
                            ),
                        }
                    ],
                }
            ],
        }

        headers = {
            "x-api-key": self._config.api_key,
            "anthropic-version": self._config.anthropic_version,
            "content-type": "application/json",
        }

        LOGGER.debug("Calling Anthropic endpoint %s", self._url)
        data = self._post_json(self._url, headers, payload)
        try:
            parts = data.get("content", [])
            text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
            return text.strip()
        except AttributeError as exc:
            raise LLMProviderError(f"Unexpected Anthropic response format: {data}") from exc


__all__ = [
    "AnthropicProvider",
    "BaseLLMProvider",
    "ByteDanceProvider",
    "DeepSeekProvider",
    "LLMProviderError",
    "OpenAIProvider",
    "QwenProvider",
]

