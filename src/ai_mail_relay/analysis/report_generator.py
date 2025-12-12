"""Report generation helpers for analysis outputs."""

from __future__ import annotations

from html import escape
from collections import defaultdict
from datetime import date
from typing import Dict, List

from ..api.schemas import AnalysisReport, ClusterInfo, ClusterPaper, ReportStatistics, TrendSection
from ..repositories import ClusterRecord
from .clustering import ClusterResult
from .trends import TrendAnalysisResult


class AnalysisReportGenerator:
    """Generate Markdown reports for clustering and trend analysis."""

    @staticmethod
    def generate_markdown(
        report_date: date,
        clusters: List[ClusterResult],
        trend: TrendAnalysisResult,
        total_papers: int,
    ) -> str:
        lines: List[str] = []
        lines.append("# arXiv AI 研究趋势报告")
        lines.append(f"**生成日期**: {report_date.isoformat()}")
        lines.append("")
        lines.append("## 统计概览")
        lines.append(f"- 论文总数: {total_papers}")
        lines.append(f"- 分析时间范围: {trend.period_start} 至 {trend.period_end}")
        lines.append(f"- 聚类数量: {len(clusters)}")
        lines.append("")
        lines.append("## 趋势分析")
        lines.append(f"- 周期: {trend.period_type}")
        if trend.previous_snapshot_date:
            lines.append(f"- 对比基准: {trend.previous_snapshot_date}")
        if trend.hot_topics:
            lines.append(f"- 热点方向: {', '.join(trend.hot_topics)}")
        if trend.emerging_topics:
            lines.append(f"- 上升方向: {', '.join(trend.emerging_topics)}")
        if trend.declining_topics:
            lines.append(f"- 下行方向: {', '.join(trend.declining_topics)}")
        if trend.deltas:
            lines.append("- 变化详情:")
            for field, delta in sorted(trend.deltas.items(), key=lambda kv: kv[1], reverse=True):
                sign = "+" if delta > 0 else ""
                lines.append(f"  - {field}: {sign}{delta}")
        lines.append(f"- 摘要: {trend.analysis_summary}")
        lines.append("- 领域分布:")
        for field, count in sorted(trend.field_trends.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"  - {field}: {count} 篇")

        if clusters:
            lines.append("")
            lines.append("## 论文聚类")
            grouped: Dict[str, List[ClusterResult]] = defaultdict(list)
            for cluster in clusters:
                grouped[cluster.research_field_prefix].append(cluster)

            for field, field_clusters in grouped.items():
                lines.append(f"### {field}")
                for cluster in field_clusters:
                    lines.append(f"#### {cluster.cluster_label} ({cluster.paper_count}篇)")
                    for paper in cluster.papers:
                        lines.append(f"- **{paper.paper.title}**")
                    lines.append("")

        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def generate_html(
        report_date: date,
        clusters: List[ClusterResult],
        trend: TrendAnalysisResult,
        total_papers: int,
    ) -> str:
        grouped: Dict[str, List[ClusterResult]] = defaultdict(list)
        for cluster in clusters:
            grouped[cluster.research_field_prefix].append(cluster)

        def _render_field_distribution() -> str:
            items = "".join(
                f"<li><span class='field'>{escape(field)}</span><span class='count'>{count} 篇</span></li>"
                for field, count in sorted(trend.field_trends.items(), key=lambda kv: kv[1], reverse=True)
            )
            return f"<ul class='field-list'>{items}</ul>"

        def _render_trend_lists() -> str:
            parts: List[str] = []
            if trend.hot_topics:
                items = "".join(f"<li>{escape(topic)}</li>" for topic in trend.hot_topics)
                parts.append(f"<div><h4>热点方向</h4><ul>{items}</ul></div>")
            if trend.emerging_topics:
                items = "".join(f"<li>{escape(topic)}</li>" for topic in trend.emerging_topics)
                parts.append(f"<div><h4>上升方向</h4><ul>{items}</ul></div>")
            if trend.declining_topics:
                items = "".join(f"<li>{escape(topic)}</li>" for topic in trend.declining_topics)
                parts.append(f"<div><h4>下行方向</h4><ul>{items}</ul></div>")
            return "".join(parts)

        def _render_clusters() -> str:
            blocks: List[str] = []
            ordered_fields = sorted(
                grouped.items(),
                key=lambda item: sum(cluster.paper_count for cluster in item[1]),
                reverse=True,
            )
            for field, field_clusters in ordered_fields:
                cards: List[str] = []
                for cluster in field_clusters:
                    papers_html = "".join(
                        f"<li><strong>{escape(paper.paper.title)}</strong></li>"
                        for paper in cluster.papers
                    )
                    cards.append(
                        "<div class='cluster-card'>"
                        f"<div class='cluster-title'>{escape(cluster.cluster_label)}"
                        f" <span class='badge'>{cluster.paper_count} 篇</span></div>"
                        f"<ul>{papers_html}</ul>"
                        "</div>"
                    )
                blocks.append(
                    f"<section class='field-block'><h3>{escape(field)}</h3>{''.join(cards)}</section>"
                )
            return "".join(blocks)

        html_parts = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>arXiv AI 研究趋势报告</title>
  <style>
    body {{ font-family: "Inter", "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #f7f7fb; color: #1f2933; }}
    h1 {{ margin-bottom: 4px; }}
    h2 {{ margin-top: 32px; }}
    h3 {{ margin-bottom: 8px; }}
    .meta {{ color: #4b5563; margin-bottom: 16px; }}
    .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .stat-card {{ background: #fff; padding: 12px 14px; border-radius: 10px; box-shadow: 0 6px 24px rgba(0,0,0,0.05); }}
    .section {{ background: #fff; padding: 16px; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.06); margin-top: 18px; }}
    .field-list {{ list-style: none; padding: 0; margin: 8px 0 0 0; }}
    .field-list li {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #eef2f7; font-size: 14px; }}
    .cluster-card {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; margin-bottom: 10px; }}
    .cluster-title {{ font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }}
    .badge {{ background: #eef2ff; color: #4338ca; padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
    ul {{ padding-left: 18px; }}
    .trend-blocks {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 10px; }}
  </style>
</head>
<body>
  <h1>arXiv AI 研究趋势报告</h1>
  <div class="meta">生成日期：{report_date.isoformat()}</div>

  <section class="stat-grid">
    <div class="stat-card"><div>论文总数</div><strong>{total_papers}</strong></div>
    <div class="stat-card"><div>分析时间范围</div><strong>{trend.period_start} - {trend.period_end}</strong></div>
    <div class="stat-card"><div>聚类数量</div><strong>{len(clusters)}</strong></div>
    <div class="stat-card"><div>周期</div><strong>{escape(trend.period_type)}</strong></div>
  </section>

  <section class="section">
    <h2>趋势分析</h2>
    <p>{escape(trend.analysis_summary)}</p>
    {_render_trend_lists()}
    <h4>领域分布</h4>
    {_render_field_distribution()}
  </section>

  <section class="section">
    <h2>论文聚类</h2>
    {_render_clusters()}
  </section>
</body>
</html>
"""
        return html_parts

    @staticmethod
    def generate_json_payload(
        report_date: date,
        clusters: List[ClusterResult],
        trend: TrendAnalysisResult,
        total_papers: int,
        cluster_records: List[ClusterRecord] | None = None,
    ) -> dict:
        record_ids = [record.id for record in cluster_records] if cluster_records else []
        cluster_infos: List[ClusterInfo] = []
        for idx, cluster in enumerate(clusters):
            cluster_infos.append(
                ClusterInfo(
                    cluster_id=record_ids[idx] if idx < len(record_ids) else None,
                    label=cluster.cluster_label,
                    research_field_prefix=cluster.research_field_prefix,
                    paper_count=cluster.paper_count,
                    papers=[
                        ClusterPaper(
                            arxiv_id=item.paper.arxiv_id,
                            title=item.paper.title,
                            summary=item.paper.summary,
                            research_field=item.paper.research_field,
                            distance_to_centroid=item.distance_to_centroid,
                        )
                        for item in cluster.papers
                    ],
                )
            )

        trend_section = TrendSection(
            period_type=trend.period_type,
            period_start=trend.period_start,
            period_end=trend.period_end,
            summary=trend.analysis_summary,
            field_distribution=trend.field_trends,
            hot_topics=trend.hot_topics,
            emerging_topics=trend.emerging_topics,
            declining_topics=trend.declining_topics,
            comparison_basis_date=trend.previous_snapshot_date,
            deltas=trend.deltas,
        )
        report = AnalysisReport(
            report_date=report_date,
            statistics=ReportStatistics(
                total_papers=total_papers,
                cluster_count=len(clusters),
                date_range_start=trend.period_start,
                date_range_end=trend.period_end,
            ),
            trends=trend_section,
            clusters=cluster_infos,
        )
        return report.to_dict()


__all__ = ["AnalysisReportGenerator"]
