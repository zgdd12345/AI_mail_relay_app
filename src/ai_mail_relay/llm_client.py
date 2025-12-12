"""Wrapper around multiple LLM providers for summarizing arXiv papers."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from .arxiv_parser import ArxivPaper
from .config import LLMConfig
from .llm_providers import (
    AnthropicProvider,
    ByteDanceProvider,
    DeepSeekProvider,
    LLMProviderError,
    OpenAIProvider,
    QwenProvider,
)


LOGGER = logging.getLogger(__name__)


class RateLimiter:
    """Simple fixed-window rate limiter (requests per minute)."""

    def __init__(self, requests_per_minute: int) -> None:
        self._rpm = requests_per_minute
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()
        self._period = 60.0

    def acquire(self) -> None:
        if self._rpm <= 0:
            return

        while True:
            with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self._period:
                    self._timestamps.popleft()

                if len(self._timestamps) < self._rpm:
                    self._timestamps.append(now)
                    return

                wait_time = self._period - (now - self._timestamps[0])

            time.sleep(max(wait_time, 0.05))


class LLMClient:
    """Facade over provider-specific implementations with threaded concurrency."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        provider_key = config.provider.lower()
        if provider_key == "claude":
            provider_key = "anthropic"

        provider_registry = {
            "openai": OpenAIProvider,
            "deepseek": DeepSeekProvider,
            "anthropic": AnthropicProvider,
            "qwen": QwenProvider,
            "bytedance": ByteDanceProvider,
        }

        try:
            provider_cls = provider_registry[provider_key]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported LLM provider '{config.provider}'. "
                "Valid options: openai, deepseek, claude/anthropic, qwen, bytedance."
            ) from exc

        self._provider = provider_cls(config)
        self._response_format = config.response_format
        self._rate_limiter = RateLimiter(config.rate_limit_rpm)

    async def summarize_papers(self, papers: List[ArxivPaper]) -> str:
        """Return a digest summary for the provided papers using a thread pool."""
        if not papers:
            return "No AI-relevant submissions were detected in today's arXiv digest."

        loop = asyncio.get_running_loop()
        LOGGER.info(
            "Processing %d papers with up to %d concurrent LLM requests",
            len(papers),
            self._config.max_concurrent_requests,
        )

        with ThreadPoolExecutor(max_workers=self._config.max_concurrent_requests) as executor:
            tasks: list[asyncio.Future] = []
            future_to_idx: Dict[asyncio.Future, int] = {}
            for idx, paper in enumerate(papers, start=1):
                task = loop.run_in_executor(executor, self._summarize_paper_sync, idx, paper)
                wrapped = asyncio.ensure_future(task)
                tasks.append(wrapped)
                future_to_idx[wrapped] = idx

            results: list[Any] = [None] * len(papers)
            completed = 0
            total = len(papers)

            for future in asyncio.as_completed(tasks):
                idx = future_to_idx.get(future)
                try:
                    result = await future
                except Exception as exc:  # pragma: no cover - defensive
                    result = exc
                if idx is not None:
                    results[idx - 1] = result
                completed += 1
                self._log_progress(completed, total)

        combined_blocks: List[str] = []
        for idx, result in enumerate(results, start=1):
            paper = papers[idx - 1]
            if isinstance(result, Exception):
                LOGGER.error("Failed to summarize paper %d (%s): %s", idx, paper.title, result)
                combined_blocks.append(f"## Paper {idx}: {paper.title}\n\n生成摘要失败：{result}")
            else:
                combined_blocks.append(f"## Paper {idx}: {paper.title}\n\n{result}")

        LOGGER.info("Completed LLM summarization for %d papers", len(papers))

        combined_summary = "\n\n".join(combined_blocks)
        if self._response_format == "markdown":
            return combined_summary

        # Allow simple text fallback when markdown is not desired.
        return combined_summary.replace("*", "").replace("#", "")

    def _summarize_paper_sync(self, idx: int, paper: ArxivPaper) -> str:
        """Summarize a single paper within a worker thread."""
        LOGGER.debug("Thread worker picked paper %d: %s", idx, paper.title)
        prompt = self._build_single_paper_prompt(paper)
        summary = self._call_provider_with_retry(prompt)
        self._extract_paper_metadata(summary, paper)
        return summary

    def _call_provider_with_retry(self, prompt: str) -> str:
        """Call provider with rate limiting and optional retries."""
        attempts = self._config.retry_attempts if self._config.retry_on_rate_limit else 0
        for attempt in range(attempts + 1):
            self._rate_limiter.acquire()
            try:
                return self._provider.generate(prompt)
            except LLMProviderError as exc:
                if (
                    self._config.retry_on_rate_limit
                    and exc.status_code == 429
                    and attempt < attempts
                ):
                    delay = self._config.retry_base_delay * (2 ** attempt)
                    LOGGER.warning(
                        "Rate limit hit (attempt %d/%d). Retrying in %.1fs.",
                        attempt + 1,
                        attempts + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"Failed to obtain LLM summary: {exc}") from exc
        raise RuntimeError("Failed to obtain LLM summary after retries.")

    def summarize_single_paper(self, paper: ArxivPaper) -> str:
        """Synchronous helper for unit tests or manual use."""
        prompt = self._build_single_paper_prompt(paper)
        summary = self._call_provider_with_retry(prompt)
        self._extract_paper_metadata(summary, paper)
        return summary

    def generate_text(self, prompt: str) -> str:
        """Generate free-form text with the configured provider."""
        return self._call_provider_with_retry(prompt)

    def _build_single_paper_prompt(self, paper: ArxivPaper) -> str:
        """Build prompt for a single paper with research field requirement."""
        paper_info = [
            f"Title: {paper.title}",
            f"Authors: {paper.authors or 'Unknown'}",
            f"Categories: {', '.join(paper.categories) or 'Unspecified'}",
            f"Abstract: {paper.abstract}",
        ]
        if paper.links:
            paper_info.append(f"Links: {', '.join(paper.links)}")

        instruction = """
请为这篇论文生成结构化的中文摘要，包含以下部分：

1. **细分领域**：给出这篇论文所属的层级化研究领域（格式：一级领域 → 二级领域 → 三级领域）
   例如：
   - 计算机视觉 → 目标检测 → 小目标检测
   - 自然语言处理 → 机器翻译 → 低资源语言翻译
   - 强化学习 → 多智能体 → 协作博弈
   - 计算机视觉 → 图像分割 → 语义分割

2. **工作内容**：用一句话（不超过100字）总结这篇论文是做什么工作的

3. **研究背景**：简要说明研究的动机和现有问题

4. **方法**：描述论文提出的主要方法或技术

5. **创新点**：突出论文的关键创新之处

6. **实验结果**：总结主要的实验发现（如有）

7. **结论**：概括论文的主要贡献和影响

输出格式要求：
- 第一行必须是 "**细分领域**：{层级化领域}"
- 第二行必须是 "**工作内容**：{一句话总结}"
- 其他部分使用 "**部分名**：内容" 的格式
- 保持简洁，除工作内容外每个部分2-3句话
- 使用 Markdown 格式
"""

        return "\n\n".join(["\n".join(paper_info), instruction])

    def _extract_paper_metadata(self, summary_md: str, paper: ArxivPaper) -> None:
        """Extract research field and work content from a single paper's summary."""
        field_match = re.search(r"\*\*细分领域\*\*[：:]\s*(.+?)(?:\n|$)", summary_md)
        if field_match:
            paper.research_field = field_match.group(1).strip()

        work_match = re.search(r"\*\*工作内容\*\*[：:]\s*(.+?)(?:\n|$)", summary_md)
        if work_match:
            paper.summary = work_match.group(1).strip()

    @staticmethod
    def _log_progress(completed: int, total: int) -> None:
        """Log a simple textual progress bar."""
        if total <= 0:
            return
        width = 20
        ratio = min(max(completed / total, 0.0), 1.0)
        filled = int(ratio * width)
        bar = "#" * filled + "-" * (width - filled)
        LOGGER.info("LLM progress [%s] %d/%d", bar, completed, total)


__all__ = ["LLMClient"]
