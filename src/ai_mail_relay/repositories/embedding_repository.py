"""Repository for managing paper embeddings."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Set

import numpy as np

from ..database.connection import get_connection

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingRecord:
    paper_id: int
    embedding: np.ndarray
    model_name: str
    embedding_dim: int
    created_at: datetime | None = None


def _serialize_vector(vector: np.ndarray) -> bytes:
    """Serialize an embedding vector into bytes for SQLite storage."""
    if vector.dtype != np.float32:
        vector = vector.astype(np.float32)
    return vector.tobytes()


def _deserialize_vector(blob: bytes, dim: int) -> np.ndarray:
    """Deserialize bytes from SQLite into a numpy vector."""
    return np.frombuffer(blob, dtype=np.float32, count=dim)


class EmbeddingRepository:
    """Persistence layer for paper embeddings."""

    def get_existing_ids(self, paper_ids: Iterable[int]) -> Set[int]:
        ids = list(paper_ids)
        if not ids:
            return set()

        conn = get_connection()
        placeholders = ",".join("?" for _ in ids)
        cursor = conn.execute(
            f"SELECT paper_id FROM paper_embeddings WHERE paper_id IN ({placeholders})",
            ids,
        )
        return {row["paper_id"] for row in cursor.fetchall()}

    def get_by_paper_ids(self, paper_ids: Iterable[int]) -> Dict[int, EmbeddingRecord]:
        ids = list(paper_ids)
        if not ids:
            return {}

        conn = get_connection()
        placeholders = ",".join("?" for _ in ids)
        cursor = conn.execute(
            f"""
            SELECT paper_id, embedding, model_name, embedding_dim, created_at
            FROM paper_embeddings
            WHERE paper_id IN ({placeholders})
            """,
            ids,
        )
        records: Dict[int, EmbeddingRecord] = {}
        for row in cursor.fetchall():
            vector = _deserialize_vector(row["embedding"], row["embedding_dim"])
            created_at = None
            if row["created_at"]:
                created_at = datetime.fromisoformat(row["created_at"])
            records[row["paper_id"]] = EmbeddingRecord(
                paper_id=row["paper_id"],
                embedding=vector,
                model_name=row["model_name"],
                embedding_dim=row["embedding_dim"],
                created_at=created_at,
            )
        return records

    def upsert_embeddings(self, embeddings: Iterable[EmbeddingRecord]) -> int:
        records = list(embeddings)
        if not records:
            return 0

        conn = get_connection()
        conn.executemany(
            """
            INSERT INTO paper_embeddings (paper_id, embedding, model_name, embedding_dim)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(paper_id) DO UPDATE SET
                embedding=excluded.embedding,
                model_name=excluded.model_name,
                embedding_dim=excluded.embedding_dim,
                created_at=CURRENT_TIMESTAMP
            """,
            [
                (
                    record.paper_id,
                    _serialize_vector(record.embedding),
                    record.model_name,
                    record.embedding_dim,
                )
                for record in records
            ],
        )
        conn.commit()
        logger.debug("Upserted %d embedding(s)", len(records))
        return len(records)


__all__ = ["EmbeddingRepository", "EmbeddingRecord"]
