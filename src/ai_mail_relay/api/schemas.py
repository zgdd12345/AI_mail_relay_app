"""Data schemas for analysis JSON payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional


@dataclass
class TrendSection:
    period_type: str
    period_start: date
    period_end: date
    summary: str
    field_distribution: Dict[str, int]
    hot_topics: List[str]
    emerging_topics: List[str]
    declining_topics: List[str]
    comparison_basis_date: Optional[date] = None
    deltas: Dict[str, int] | None = None

    def to_dict(self) -> dict:
        return {
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "summary": self.summary,
            "field_distribution": self.field_distribution,
            "hot_topics": self.hot_topics,
            "emerging_topics": self.emerging_topics,
            "declining_topics": self.declining_topics,
            "comparison_basis_date": self.comparison_basis_date.isoformat()
            if self.comparison_basis_date
            else None,
            "deltas": self.deltas,
        }


@dataclass
class ClusterPaper:
    arxiv_id: str
    title: str
    summary: str
    research_field: str
    distance_to_centroid: float | None = None

    def to_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "summary": self.summary,
            "research_field": self.research_field,
            "distance_to_centroid": self.distance_to_centroid,
        }


@dataclass
class ClusterInfo:
    cluster_id: int | None
    label: str
    research_field_prefix: str
    paper_count: int
    papers: List[ClusterPaper]

    def to_dict(self) -> dict:
        return {
            "id": self.cluster_id,
            "label": self.label,
            "research_field_prefix": self.research_field_prefix,
            "paper_count": self.paper_count,
            "papers": [paper.to_dict() for paper in self.papers],
        }


@dataclass
class ReportStatistics:
    total_papers: int
    cluster_count: int
    date_range_start: date
    date_range_end: date

    def to_dict(self) -> dict:
        return {
            "total_papers": self.total_papers,
            "cluster_count": self.cluster_count,
            "date_range": [
                self.date_range_start.isoformat(),
                self.date_range_end.isoformat(),
            ],
        }


@dataclass
class AnalysisReport:
    report_date: date
    statistics: ReportStatistics
    trends: TrendSection
    clusters: List[ClusterInfo]

    def to_dict(self) -> dict:
        return {
            "report_date": self.report_date.isoformat(),
            "statistics": self.statistics.to_dict(),
            "trends": self.trends.to_dict(),
            "clusters": [cluster.to_dict() for cluster in self.clusters],
        }


__all__ = [
    "AnalysisReport",
    "ClusterInfo",
    "ClusterPaper",
    "ReportStatistics",
    "TrendSection",
]
