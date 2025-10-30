"""Wrapper around multiple LLM providers for summarizing arXiv papers."""

from __future__ import annotations

import logging
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

LOGGER = logging.getLogger(__name__)


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
        """Return a digest summary for the provided papers by processing each paper individually."""
        if not papers:
            return "No AI-relevant submissions were detected in today's arXiv digest."

        all_summaries = []
        total_papers = len(papers)

        LOGGER.info(f"Starting to process {total_papers} papers individually...")

        for idx, paper in enumerate(papers, start=1):
            LOGGER.info(f"Processing paper {idx}/{total_papers}: {paper.title[:60]}...")

            try:
                # Generate summary for single paper
                summary = self.summarize_single_paper(paper)

                # Extract research field and work content from summary
                self._extract_paper_metadata(summary, paper)

                # Collect summary with proper header for compatibility
                all_summaries.append(f"## Paper {idx}: {paper.title}\n\n{summary}")

                LOGGER.info(f"Successfully processed paper {idx}/{total_papers}")

            except Exception as e:
                error_msg = f"生成摘要失败：{str(e)}"
                LOGGER.error(f"Failed to summarize paper {idx} ({paper.title}): {e}")
                all_summaries.append(f"## Paper {idx}: {paper.title}\n\n{error_msg}")

        LOGGER.info(f"Completed processing all {total_papers} papers")

        # Join all summaries into markdown format
        combined_summary = "\n\n".join(all_summaries)

        if self._response_format == "markdown":
            return combined_summary

        # Allow simple text fallback when markdown is not desired.
        return combined_summary.replace("*", "").replace("#", "")

    def summarize_single_paper(self, paper: ArxivPaper) -> str:
        """Generate summary for a single paper."""
        prompt = self._build_single_paper_prompt(paper)
        try:
            summary = self._provider.generate(prompt)
            return summary
        except LLMProviderError as exc:
            raise RuntimeError(f"Failed to obtain LLM summary: {exc}") from exc

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

    def _build_prompt(self, papers: List[ArxivPaper]) -> str:
        """Legacy method for batch processing (deprecated, kept for compatibility)."""
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

1. **细分领域**：给出这篇论文所属的层级化研究领域（格式：一级领域 → 二级领域 → 三级领域）
2. **工作内容**：用一句话（不超过100字）总结这篇论文是做什么工作的
3. **研究背景**：简要说明研究的动机和现有问题
4. **方法**：描述论文提出的主要方法或技术
5. **创新点**：突出论文的关键创新之处
6. **实验结果**：总结主要的实验发现（如有）
7. **结论**：概括论文的主要贡献和影响

输出格式要求：
- 每篇论文使用 "## Paper {编号}: {论文标题}" 作为标题
- 在标题下第一行立即输出 "**细分领域**：{层级化领域}"
- 第二行输出 "**工作内容**：{一句话总结}"
- 其他部分使用 "**部分名**：内容" 的格式
- 保持简洁，除工作内容外每个部分2-3句话
- 使用 Markdown 格式
"""

        blocks.append(instruction)
        return "\n\n".join(blocks)

    def _extract_paper_metadata(self, summary_md: str, paper: ArxivPaper) -> None:
        """Extract research field and work content from a single paper's summary."""
        # Extract research field
        field_match = re.search(r'\*\*细分领域\*\*[：:]\s*(.+?)(?:\n|$)', summary_md)
        if field_match:
            paper.research_field = field_match.group(1).strip()

        # Extract work content
        work_match = re.search(r'\*\*工作内容\*\*[：:]\s*(.+?)(?:\n|$)', summary_md)
        if work_match:
            paper.summary = work_match.group(1).strip()


__all__ = ["LLMClient"]
