"""Wrapper around multiple LLM providers for summarizing arXiv papers."""

from __future__ import annotations

import re
from typing import List

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


class LLMClient:
    """Facade over provider-specific implementations."""

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

    def summarize_papers(self, papers: List[ArxivPaper]) -> str:
        """Return a digest summary for the provided papers and extract work summaries."""
        if not papers:
            return "No AI-relevant submissions were detected in today's arXiv digest."

        prompt = self._build_prompt(papers)
        try:
            summary = self._provider.generate(prompt)
        except LLMProviderError as exc:
            raise RuntimeError(f"Failed to obtain LLM summary: {exc}") from exc

        # Extract work content summaries and populate paper.summary field
        self._extract_work_summaries(summary, papers)

        if self._response_format == "markdown":
            return summary

        # Allow simple text fallback when markdown is not desired.
        return summary.replace("*", "").replace("#", "")

    def _build_prompt(self, papers: List[ArxivPaper]) -> str:
        blocks = []
        for idx, paper in enumerate(papers, start=1):
            block_lines = [
                f"Paper {idx}:",
                f"Title: {paper.title}",
                f"Authors: {paper.authors or 'Unknown'}",
                f"Categories: {', '.join(paper.categories) or 'Unspecified'}",
                f"Abstract: {paper.abstract}",
            ]
            if paper.links:
                block_lines.append(f"Links: {', '.join(paper.links)}")
            blocks.append("\n".join(block_lines))

        instruction = """
请为每篇论文生成结构化的中文摘要，包含以下部分：

1. **工作内容**：用一句话（不超过100字）总结这篇论文是做什么工作的
2. **研究背景**：简要说明研究的动机和现有问题
3. **方法**：描述论文提出的主要方法或技术
4. **创新点**：突出论文的关键创新之处
5. **实验结果**：总结主要的实验发现（如有）
6. **结论**：概括论文的主要贡献和影响

输出格式要求：
- 每篇论文使用 "## Paper {编号}: {论文标题}" 作为标题
- 在标题下第一行立即输出 "**工作内容**：{一句话总结}" （必须是第一项）
- 其他部分使用 "**部分名**：内容" 的格式
- 保持简洁，除工作内容外每个部分2-3句话
- 使用 Markdown 格式
"""

        blocks.append(instruction)
        return "\n\n".join(blocks)

    def _extract_work_summaries(self, summary_md: str, papers: List[ArxivPaper]) -> None:
        """Extract work content summaries from LLM output and populate paper.summary field."""
        # Split by paper headers
        pattern = r'## Paper (\d+):'
        parts = re.split(pattern, summary_md)

        # Parse each paper's summary
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                paper_num = int(parts[i])
                content = parts[i + 1]

                # Extract "工作内容" from the content
                work_match = re.search(r'\*\*工作内容\*\*[：:]\s*(.+?)(?:\n|$)', content)
                if work_match and paper_num <= len(papers):
                    # Update the corresponding paper's summary field
                    papers[paper_num - 1].summary = work_match.group(1).strip()


__all__ = ["LLMClient"]
