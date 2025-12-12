"""Orchestration service for embeddings, clustering, and trend analysis."""

from __future__ import annotations

import logging
import json
from datetime import date
from pathlib import Path
from typing import List

from ..analysis import AnalysisReportGenerator, EmbeddingGenerator, HybridClusterer, TrendAnalyzer
from ..config import Settings
from ..database import init_database, run_migrations
from ..llm_client import LLMClient
from ..repositories import (
    ClusterPaperLink,
    ClusterRecord,
    ClusterRepository,
    EmbeddingRepository,
    PaperRepository,
    TrendSnapshot,
)
from ..analysis.trends import TrendAnalysisResult

logger = logging.getLogger(__name__)


class AnalysisService:
    """High-level operations for the analysis CLI commands."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._config = settings.analysis
        self._paper_repo = PaperRepository()
        self._embedding_repo = EmbeddingRepository()
        self._cluster_repo = ClusterRepository()
        self._embedding_generator = EmbeddingGenerator(self._config, self._embedding_repo)
        self._clusterer = HybridClusterer(self._config)
        self._trend_analyzer = TrendAnalyzer(self._config, llm_client=LLMClient(settings.llm))

    def _ensure_database(self) -> None:
        if not self._settings.database.enabled:
            raise RuntimeError("Analysis requires DATABASE_ENABLED=true.")
        init_database(self._settings.database)
        run_migrations()

    def _normalize_end_date(self, start_date: date, end_date: date | None) -> date:
        return end_date or start_date

    def _load_papers(self, start_date: date, end_date: date | None) -> List:
        end = self._normalize_end_date(start_date, end_date)
        papers = self._paper_repo.find_by_ingested_date_range(start_date, end)
        return papers

    def generate_embeddings(self, start_date: date, end_date: date | None = None, force: bool = False) -> int:
        """Generate embeddings for papers within the date range."""
        self._ensure_database()
        papers = self._load_papers(start_date, end_date)
        if not papers:
            logger.warning("No papers found between %s and %s", start_date, end_date or start_date)
            return 0
        created = self._embedding_generator.generate_for_papers(papers, force=force)
        return len(created)

    def run_clustering(
        self,
        start_date: date,
        end_date: date | None = None,
    ) -> tuple[int, List[ClusterRecord], List]:
        """Cluster papers and persist the results."""
        self._ensure_database()
        end = self._normalize_end_date(start_date, end_date)
        papers = self._load_papers(start_date, end)
        if not papers:
            raise RuntimeError(f"No papers available for clustering between {start_date} and {end}.")

        # Ensure embeddings exist
        self._embedding_generator.generate_for_papers(papers, force=False)
        embeddings = self._embedding_generator.load_embeddings_map(papers)

        clusters = self._clusterer.cluster(papers, embeddings)
        parameters = {
            "cluster_min_papers": self._config.cluster_min_papers,
            "cluster_similarity_threshold": self._config.cluster_similarity_threshold,
            "cluster_max_per_field": self._config.cluster_max_per_field,
        }
        run_id = self._cluster_repo.create_run(
            run_date=date.today(),
            date_range_start=start_date,
            date_range_end=end,
            algorithm="hierarchical_hybrid",
            num_clusters=len(clusters),
            parameters=parameters,
        )

        # Persist clusters
        cluster_records: List[ClusterRecord] = [
            ClusterRecord(
                id=None,
                run_id=run_id,
                cluster_label=cluster.cluster_label,
                research_field_prefix=cluster.research_field_prefix,
                centroid=cluster.centroid,
                paper_count=cluster.paper_count,
            )
            for cluster in clusters
        ]
        self._cluster_repo.save_clusters(run_id, cluster_records, [])

        # Persist paper links now that IDs exist
        links: List[ClusterPaperLink] = []
        for record, cluster in zip(cluster_records, clusters):
            if record.id is None:
                continue
            for item in cluster.papers:
                if item.paper.db_id is None:
                    continue
                links.append(
                    ClusterPaperLink(
                        cluster_id=record.id,
                        paper_id=item.paper.db_id,
                        distance_to_centroid=item.distance_to_centroid,
                    )
                )
        self._cluster_repo.save_cluster_links(links)
        logger.info("Finished clustering run %d with %d clusters", run_id, len(cluster_records))
        return run_id, cluster_records, clusters

    def run_trend_analysis(
        self,
        start_date: date,
        end_date: date | None,
        period_type: str,
    ) -> TrendAnalysisResult:
        """Compute field distribution and persist a trend snapshot."""
        self._ensure_database()
        end = self._normalize_end_date(start_date, end_date)
        papers = self._load_papers(start_date, end)
        previous_snapshot = self._cluster_repo.get_latest_trend_snapshot(
            period_type=period_type, before_date=start_date
        )
        result = self._trend_analyzer.analyze(
            papers,
            period_type,
            start_date,
            end,
            previous_snapshot=previous_snapshot,
        )
        snapshot = TrendSnapshot(
            id=None,
            snapshot_date=result.snapshot_date,
            period_type=period_type,
            period_start=start_date,
            period_end=end,
            field_trends=result.field_trends,
            analysis_summary=result.analysis_summary,
        )
        self._cluster_repo.save_trend_snapshot(snapshot)
        return result

    def generate_report(
        self,
        clusters,
        trend: TrendAnalysisResult,
        total_papers: int,
        output_path: Path | None = None,
        fmt: str | None = None,
        cluster_records: List[ClusterRecord] | None = None,
    ) -> str:
        """Render and optionally persist a Markdown report."""
        report_date = date.today()
        report_format = (fmt or self._settings.analysis.analysis_report_format).lower()
        if report_format == "markdown":
            content = AnalysisReportGenerator.generate_markdown(
                report_date=report_date,
                clusters=clusters,
                trend=trend,
                total_papers=total_papers,
            )
        elif report_format == "html":
            content = AnalysisReportGenerator.generate_html(
                report_date=report_date,
                clusters=clusters,
                trend=trend,
                total_papers=total_papers,
            )
        elif report_format == "json":
            payload = AnalysisReportGenerator.generate_json_payload(
                report_date=report_date,
                clusters=clusters,
                trend=trend,
                total_papers=total_papers,
                cluster_records=cluster_records,
            )
            content = json.dumps(payload, ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"Unsupported report format: {report_format}")

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            logger.info("Report written to %s (%s)", output_path, report_format)
        return content


__all__ = ["AnalysisService"]
