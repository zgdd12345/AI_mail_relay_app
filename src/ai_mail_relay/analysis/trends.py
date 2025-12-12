"""Trend analysis utilities for arXiv papers."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Sequence

from ..arxiv_parser import ArxivPaper
from ..config import AnalysisConfig
from ..llm_client import LLMClient
from ..repositories.cluster_repository import TrendSnapshot

logger = logging.getLogger(__name__)


def _prefix(research_field: str) -> str:
    if not research_field:
        return "未分类"
    return research_field.split("→")[0].strip()


@dataclass
class TrendAnalysisResult:
    snapshot_date: date
    period_type: str
    period_start: date
    period_end: date
    field_trends: dict[str, int]
    analysis_summary: str
    hot_topics: List[str]
    emerging_topics: List[str]
    declining_topics: List[str]
    previous_snapshot_date: date | None = None
    deltas: dict[str, int] | None = None


class TrendAnalyzer:
    """Compute field-level distributions and LLM-backed summaries."""

    def __init__(self, config: AnalysisConfig, llm_client: LLMClient | None = None) -> None:
        self._config = config
        self._llm = llm_client

    def analyze(
        self,
        papers: Sequence[ArxivPaper],
        period_type: str,
        period_start: date,
        period_end: date,
        previous_snapshot: TrendSnapshot | None = None,
    ) -> TrendAnalysisResult:
        counts = Counter()
        examples: Dict[str, List[str]] = {}
        for paper in papers:
            prefix = _prefix(paper.research_field)
            counts[prefix] += 1
            examples.setdefault(prefix, []).append(paper.title)

        hot_topics = self._top_fields(counts)
        deltas = self._compute_deltas(counts, previous_snapshot)
        emerging = self._top_positive(deltas)
        declining = self._top_negative(deltas)
        sampled_titles = self._sample_titles(counts, examples, self._config.trend_llm_max_papers)
        summary = self._build_summary(
            counts=counts,
            hot_topics=hot_topics,
            emerging_topics=emerging,
            declining_topics=declining,
            sampled_titles=sampled_titles,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            previous_snapshot_date=previous_snapshot.snapshot_date if previous_snapshot else None,
        )
        logger.info(
            "Generated trend snapshot (%s) for %d paper(s) across %d fields",
            period_type,
            len(papers),
            len(counts),
        )
        return TrendAnalysisResult(
            snapshot_date=date.today(),
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            field_trends=dict(counts),
            analysis_summary=summary,
            hot_topics=hot_topics,
            emerging_topics=emerging,
            declining_topics=declining,
            previous_snapshot_date=previous_snapshot.snapshot_date if previous_snapshot else None,
            deltas=deltas or None,
        )

    @staticmethod
    def _top_fields(counts: Counter, limit: int = 3) -> List[str]:
        return [field for field, _ in counts.most_common(limit)]

    @staticmethod
    def _top_positive(deltas: Dict[str, int], limit: int = 3) -> List[str]:
        positive = [(field, delta) for field, delta in deltas.items() if delta > 0]
        positive.sort(key=lambda item: item[1], reverse=True)
        return [field for field, _ in positive[:limit]]

    @staticmethod
    def _top_negative(deltas: Dict[str, int], limit: int = 3) -> List[str]:
        negative = [(field, delta) for field, delta in deltas.items() if delta < 0]
        negative.sort(key=lambda item: item[1])
        return [field for field, _ in negative[:limit]]

    @staticmethod
    def _sample_titles(
        counts: Counter, examples: Dict[str, List[str]], limit: int
    ) -> List[tuple[str, str]]:
        """Return up to `limit` (field, title) pairs ordered by field popularity."""
        samples: List[tuple[str, str]] = []
        for field, _ in counts.most_common():
            for title in examples.get(field, []):
                samples.append((field, title))
                if len(samples) >= limit:
                    return samples
        return samples

    @staticmethod
    def _compute_deltas(
        counts: Counter, previous_snapshot: TrendSnapshot | None
    ) -> Dict[str, int]:
        if not previous_snapshot:
            return {}

        previous_counts = Counter(previous_snapshot.field_trends or {})
        deltas: Dict[str, int] = {}
        for field, current in counts.items():
            delta = current - previous_counts.get(field, 0)
            if delta != 0:
                deltas[field] = delta
        for field, previous in previous_counts.items():
            if field not in counts:
                deltas[field] = -previous
        return deltas

    def _build_summary(
        self,
        counts: Counter,
        hot_topics: List[str],
        emerging_topics: List[str],
        declining_topics: List[str],
        sampled_titles: List[tuple[str, str]],
        period_type: str,
        period_start: date,
        period_end: date,
        previous_snapshot_date: date | None,
    ) -> str:
        if not counts:
            return "未找到足够的论文用于趋势分析。"

        if self._llm is None:
            return self._fallback_summary(
                counts=counts,
                hot_topics=hot_topics,
                emerging_topics=emerging_topics,
                declining_topics=declining_topics,
                previous_snapshot_date=previous_snapshot_date,
            )

        prompt = self._compose_prompt(
            counts=counts,
            hot_topics=hot_topics,
            emerging_topics=emerging_topics,
            declining_topics=declining_topics,
            sampled_titles=sampled_titles,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            previous_snapshot_date=previous_snapshot_date,
        )
        try:
            return self._llm.generate_text(prompt)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("LLM trend summary failed (%s); falling back to heuristic summary.", exc)
            return self._fallback_summary(
                counts=counts,
                hot_topics=hot_topics,
                emerging_topics=emerging_topics,
                declining_topics=declining_topics,
                previous_snapshot_date=previous_snapshot_date,
            )

    @staticmethod
    def _fallback_summary(
        counts: Counter,
        hot_topics: List[str],
        emerging_topics: List[str],
        declining_topics: List[str],
        previous_snapshot_date: date | None,
    ) -> str:
        top = counts.most_common(3)
        parts: List[str] = []
        parts.append("当前最活跃的研究方向：" + "、".join(f"{field}（{count}篇）" for field, count in top))
        if emerging_topics:
            parts.append("上升趋势：" + "、".join(emerging_topics))
        if declining_topics:
            parts.append("下行趋势：" + "、".join(declining_topics))
        if len(counts) > 3:
            others = sum(count for _, count in counts.items()) - sum(count for _, count in top)
            parts.append(f"其他方向共 {others} 篇。")
        if previous_snapshot_date:
            parts.append(f"（对比基准：{previous_snapshot_date.isoformat()} 的快照）")
        return " ".join(parts)

    @staticmethod
    def _compose_prompt(
        counts: Counter,
        hot_topics: List[str],
        emerging_topics: List[str],
        declining_topics: List[str],
        sampled_titles: List[tuple[str, str]],
        period_type: str,
        period_start: date,
        period_end: date,
        previous_snapshot_date: date | None,
    ) -> str:
        lines: List[str] = []
        lines.append("你是一名科研趋势分析师，请基于 arXiv 论文分布生成简洁的中文趋势解读。")
        lines.append(f"时间范围: {period_start} 至 {period_end} （{period_type}）")
        if previous_snapshot_date:
            lines.append(f"对比基准: {previous_snapshot_date.isoformat()} 的同周期快照")

        lines.append("\n当前领域分布（按论文量排序）：")
        for field, count in counts.most_common():
            lines.append(f"- {field}: {count} 篇")

        if hot_topics:
            lines.append("\n系统识别的热点方向（高数量）：")
            for field in hot_topics:
                lines.append(f"- {field}")
        if emerging_topics:
            lines.append("\n系统识别的上升方向（数量增长）：")
            for field in emerging_topics:
                lines.append(f"- {field}")
        if declining_topics:
            lines.append("\n系统识别的下行方向（数量下降）：")
            for field in declining_topics:
                lines.append(f"- {field}")

        if sampled_titles:
            lines.append("\n示例论文（用于辅助理解，每行包含领域和标题）：")
            for field, title in sampled_titles:
                lines.append(f"- [{field}] {title}")

        lines.append(
            "\n请输出：1) 热点方向；2) 上升/新兴方向；3) 下行方向；4) 120-180 字的整体趋势总结。"
            " 使用项目符号或短句，保持客观，不要重复列出相同的字段。"
        )
        return "\n".join(lines)


__all__ = ["TrendAnalyzer", "TrendAnalysisResult"]
