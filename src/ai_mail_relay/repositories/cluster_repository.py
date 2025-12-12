"""Repository for clustering runs, clusters, and trend snapshots."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Tuple

import numpy as np

from ..database.connection import get_connection

logger = logging.getLogger(__name__)


def _serialize_vector(vector: np.ndarray | None) -> bytes | None:
    if vector is None:
        return None
    if vector.dtype != np.float32:
        vector = vector.astype(np.float32)
    return vector.tobytes()


def _deserialize_vector(blob: bytes | None, dim: int | None) -> np.ndarray | None:
    if blob is None or dim is None:
        if blob is None:
            return None
        return np.frombuffer(blob, dtype=np.float32)
    return np.frombuffer(blob, dtype=np.float32, count=dim)


@dataclass
class ClusterRun:
    id: int | None
    run_date: date
    date_range_start: date
    date_range_end: date
    algorithm: str
    num_clusters: int
    parameters: dict | None
    created_at: datetime | None = None


@dataclass
class ClusterRecord:
    id: int | None
    run_id: int
    cluster_label: str
    research_field_prefix: str | None
    centroid: np.ndarray | None
    paper_count: int
    created_at: datetime | None = None


@dataclass
class ClusterPaperLink:
    cluster_id: int
    paper_id: int
    distance_to_centroid: float | None = None


@dataclass
class TrendSnapshot:
    id: int | None
    snapshot_date: date
    period_type: str
    period_start: date
    period_end: date
    field_trends: Dict[str, int]
    analysis_summary: str | None = None
    created_at: datetime | None = None


class ClusterRepository:
    """Persistence helper for clustering results and trend snapshots."""

    def create_run(
        self,
        run_date: date,
        date_range_start: date,
        date_range_end: date,
        algorithm: str,
        num_clusters: int,
        parameters: dict | None = None,
    ) -> int:
        conn = get_connection()
        cursor = conn.execute(
            """
            INSERT INTO cluster_runs (
                run_date, date_range_start, date_range_end,
                algorithm, num_clusters, parameters
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_date.isoformat(),
                date_range_start.isoformat(),
                date_range_end.isoformat(),
                algorithm,
                num_clusters,
                json.dumps(parameters or {}),
            ),
        )
        conn.commit()
        run_id = cursor.lastrowid
        logger.debug("Created cluster run %d (%s)", run_id, algorithm)
        return run_id

    def save_clusters(
        self,
        run_id: int,
        clusters: Iterable[ClusterRecord],
        links: Iterable[ClusterPaperLink],
    ) -> Tuple[int, int]:
        conn = get_connection()
        cluster_rows = list(clusters)
        link_rows = list(links)

        if cluster_rows:
            conn.executemany(
                """
                INSERT INTO clusters (
                    run_id, cluster_label, research_field_prefix, centroid, paper_count
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.run_id,
                        row.cluster_label,
                        row.research_field_prefix,
                        _serialize_vector(row.centroid),
                        row.paper_count,
                    )
                    for row in cluster_rows
                ],
            )

        # Refresh cluster IDs when inserted
        if cluster_rows:
            conn.commit()
            last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            first_id = last_id - len(cluster_rows) + 1
            for idx, row in enumerate(cluster_rows):
                row.id = first_id + idx

        if link_rows:
            conn.executemany(
                """
                INSERT OR IGNORE INTO cluster_papers (
                    cluster_id, paper_id, distance_to_centroid
                ) VALUES (?, ?, ?)
                """,
                [(link.cluster_id, link.paper_id, link.distance_to_centroid) for link in link_rows],
            )

        conn.commit()
        logger.debug(
            "Persisted %d clusters and %d cluster-paper links for run %d",
            len(cluster_rows),
            len(link_rows),
            run_id,
        )
        return len(cluster_rows), len(link_rows)

    def get_run_clusters(self, run_id: int) -> List[ClusterRecord]:
        conn = get_connection()
        cursor = conn.execute(
            """
            SELECT id, run_id, cluster_label, research_field_prefix, centroid, paper_count, created_at
            FROM clusters
            WHERE run_id = ?
            ORDER BY paper_count DESC, id ASC
            """,
            (run_id,),
        )
        rows = cursor.fetchall()
        result: List[ClusterRecord] = []
        for row in rows:
            centroid = _deserialize_vector(row["centroid"], None)
            created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            result.append(
                ClusterRecord(
                    id=row["id"],
                    run_id=row["run_id"],
                    cluster_label=row["cluster_label"],
                    research_field_prefix=row["research_field_prefix"],
                    centroid=centroid,
                    paper_count=row["paper_count"],
                    created_at=created_at,
                )
        )
        return result

    def get_latest_trend_snapshot(
        self, period_type: str, before_date: date | None = None
    ) -> TrendSnapshot | None:
        conn = get_connection()
        query = """
            SELECT id, snapshot_date, period_type, period_start, period_end,
                   field_trends, analysis_summary, created_at
            FROM trend_snapshots
            WHERE period_type = ?
        """
        params: list = [period_type]
        if before_date:
            query += " AND snapshot_date < ?"
            params.append(before_date.isoformat())
        query += " ORDER BY snapshot_date DESC LIMIT 1"

        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        if not row:
            return None

        created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
        return TrendSnapshot(
            id=row["id"],
            snapshot_date=date.fromisoformat(row["snapshot_date"]),
            period_type=row["period_type"],
            period_start=date.fromisoformat(row["period_start"]),
            period_end=date.fromisoformat(row["period_end"]),
            field_trends=json.loads(row["field_trends"] or "{}"),
            analysis_summary=row["analysis_summary"],
            created_at=created_at,
        )

    def save_trend_snapshot(self, snapshot: TrendSnapshot) -> int:
        conn = get_connection()
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO trend_snapshots (
                snapshot_date, period_type, period_start, period_end,
                field_trends, analysis_summary
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.snapshot_date.isoformat(),
                snapshot.period_type,
                snapshot.period_start.isoformat(),
                snapshot.period_end.isoformat(),
                json.dumps(snapshot.field_trends),
                snapshot.analysis_summary,
            ),
        )
        conn.commit()
        snapshot_id = cursor.lastrowid
        logger.debug(
            "Stored trend snapshot (%s) for %s with %d fields",
            snapshot.period_type,
            snapshot.snapshot_date,
            len(snapshot.field_trends),
        )
        return snapshot_id

    def save_cluster_links(self, links: Iterable[ClusterPaperLink]) -> int:
        rows = list(links)
        if not rows:
            return 0
        conn = get_connection()
        conn.executemany(
            """
            INSERT OR IGNORE INTO cluster_papers (
                cluster_id, paper_id, distance_to_centroid
            ) VALUES (?, ?, ?)
            """,
            [(link.cluster_id, link.paper_id, link.distance_to_centroid) for link in rows],
        )
        conn.commit()
        logger.debug("Persisted %d cluster-paper link(s)", len(rows))
        return len(rows)


__all__ = [
    "ClusterRepository",
    "ClusterRun",
    "ClusterRecord",
    "ClusterPaperLink",
    "TrendSnapshot",
]
