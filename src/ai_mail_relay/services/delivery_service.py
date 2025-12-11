"""Delivery history service for multi-user mode."""

from __future__ import annotations

import logging
from typing import Iterable, List

from ..database.connection import get_connection
from ..arxiv_parser import ArxivPaper

logger = logging.getLogger(__name__)


class DeliveryService:
    """Handle delivery history to avoid duplicate sends per user."""

    def __init__(self, skip_delivered: bool = True) -> None:
        self._skip_delivered = skip_delivered

    def filter_undelivered(self, user_id: int, papers: List[ArxivPaper]) -> List[ArxivPaper]:
        """Return only papers that have not been delivered to the user."""
        if not self._skip_delivered or not papers:
            return papers

        paper_ids = [paper.db_id for paper in papers if paper.db_id is not None]
        if not paper_ids:
            return papers

        conn = get_connection()
        placeholders = ",".join("?" for _ in paper_ids)
        cursor = conn.execute(
            f"""
            SELECT paper_id FROM delivery_history
            WHERE user_id = ? AND paper_id IN ({placeholders})
            """,
            [user_id, *paper_ids],
        )
        delivered = {row["paper_id"] for row in cursor.fetchall()}

        filtered = [paper for paper in papers if paper.db_id is None or paper.db_id not in delivered]
        logger.debug(
            "User %d: %d/%d papers filtered out as already delivered",
            user_id,
            len(papers) - len(filtered),
            len(papers),
        )
        return filtered

    def record_delivery(self, user_id: int, paper_ids: Iterable[int]) -> int:
        """Persist delivery history for the given user and paper IDs."""
        ids = [pid for pid in paper_ids if pid is not None]
        if not ids:
            return 0

        conn = get_connection()
        conn.executemany(
            """
            INSERT OR IGNORE INTO delivery_history (user_id, paper_id)
            VALUES (?, ?)
            """,
            [(user_id, pid) for pid in ids],
        )
        conn.commit()
        logger.debug("Recorded delivery for user %d: %d paper(s)", user_id, len(ids))
        return len(ids)


__all__ = ["DeliveryService"]
