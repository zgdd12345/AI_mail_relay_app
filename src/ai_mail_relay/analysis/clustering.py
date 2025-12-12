"""Hybrid clustering utilities for arXiv papers."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from ..arxiv_parser import ArxivPaper
from ..config import AnalysisConfig
from ..repositories import EmbeddingRecord

logger = logging.getLogger(__name__)


@dataclass
class ClusteredPaper:
    paper: ArxivPaper
    embedding: np.ndarray
    distance_to_centroid: float | None = None


@dataclass
class ClusterResult:
    cluster_label: str
    research_field_prefix: str
    papers: List[ClusteredPaper]
    centroid: np.ndarray

    @property
    def paper_ids(self) -> List[int]:
        return [p.paper.db_id for p in self.papers if p.paper.db_id is not None]

    @property
    def paper_titles(self) -> List[str]:
        return [p.paper.title for p in self.papers]

    @property
    def paper_count(self) -> int:
        return len(self.papers)


class HybridClusterer:
    """Two-stage clustering: by research field prefix then embedding similarity."""

    def __init__(self, config: AnalysisConfig) -> None:
        self._config = config

    def cluster(
        self,
        papers: Iterable[ArxivPaper],
        embeddings: Dict[int, EmbeddingRecord],
    ) -> List[ClusterResult]:
        grouped: Dict[str, List[ClusteredPaper]] = {}
        for paper in papers:
            if paper.db_id is None or paper.db_id not in embeddings:
                continue
            prefix = self._extract_prefix(paper.research_field)
            grouped.setdefault(prefix, []).append(
                ClusteredPaper(paper=paper, embedding=embeddings[paper.db_id].embedding)
            )

        results: List[ClusterResult] = []
        cluster_counter = 1
        for prefix, bucket in grouped.items():
            if len(bucket) < self._config.cluster_min_papers:
                label = self._make_label(prefix, bucket, cluster_counter)
                centroid = self._compute_centroid([item.embedding for item in bucket])
                results.append(
                    ClusterResult(
                        cluster_label=label,
                        research_field_prefix=prefix,
                        papers=bucket,
                        centroid=centroid,
                    )
                )
                cluster_counter += 1
                continue

            vectors = np.stack([item.embedding for item in bucket])
            distance_threshold = 1.0 - self._config.cluster_similarity_threshold
            model = AgglomerativeClustering(
                metric="cosine",
                linkage="average",
                distance_threshold=distance_threshold,
                n_clusters=None,
            )
            labels = model.fit_predict(vectors)

            for label_id in sorted(set(labels)):
                indices = [idx for idx, lbl in enumerate(labels) if lbl == label_id]
                cluster_papers = [bucket[idx] for idx in indices]
                centroid = self._compute_centroid([bucket[idx].embedding for idx in indices])
                self._attach_distances(cluster_papers, centroid)
                label = self._make_label(prefix, cluster_papers, cluster_counter)
                results.append(
                    ClusterResult(
                        cluster_label=label,
                        research_field_prefix=prefix,
                        papers=cluster_papers,
                        centroid=centroid,
                    )
                )
                cluster_counter += 1

        # Cap number of clusters per field
        limited: List[ClusterResult] = []
        for prefix in grouped.keys():
            prefix_clusters = [c for c in results if c.research_field_prefix == prefix]
            prefix_clusters.sort(key=lambda c: c.paper_count, reverse=True)
            limited.extend(prefix_clusters[: self._config.cluster_max_per_field])

        # Sort for stable output
        limited.sort(key=lambda c: c.paper_count, reverse=True)
        logger.info("Generated %d clusters across %d fields", len(limited), len(grouped))
        return limited

    @staticmethod
    def _extract_prefix(research_field: str) -> str:
        if not research_field:
            return "未分类"
        parts = research_field.split("→")
        return parts[0].strip() if parts else research_field.strip()

    @staticmethod
    def _compute_centroid(vectors: List[np.ndarray]) -> np.ndarray:
        if not vectors:
            return np.zeros(1, dtype=np.float32)
        centroid = np.mean(np.stack(vectors), axis=0)
        return centroid.astype(np.float32)

    @staticmethod
    def _attach_distances(papers: List[ClusteredPaper], centroid: np.ndarray) -> None:
        centroid_norm = np.linalg.norm(centroid)
        for item in papers:
            vec = item.embedding
            denom = (np.linalg.norm(vec) * centroid_norm) or 1e-8
            cosine_sim = float(np.dot(vec, centroid) / denom)
            item.distance_to_centroid = 1.0 - cosine_sim

    @staticmethod
    def _make_label(prefix: str, papers: List[ClusteredPaper], idx: int) -> str:
        keywords = HybridClusterer._top_keywords([p.paper.title for p in papers])
        suffix = " / ".join(keywords) if keywords else f"Cluster {idx}"
        return f"{prefix} · {suffix}" if prefix else suffix

    @staticmethod
    def _top_keywords(titles: List[str], limit: int = 3) -> List[str]:
        counter: dict[str, int] = {}
        for title in titles:
            for token in re.findall(r"[A-Za-z0-9]+", title.lower()):
                if len(token) <= 3:
                    continue
                counter[token] = counter.get(token, 0) + 1
        sorted_tokens = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)
        return [token for token, _ in sorted_tokens[:limit]]


__all__ = ["HybridClusterer", "ClusterResult", "ClusteredPaper"]
