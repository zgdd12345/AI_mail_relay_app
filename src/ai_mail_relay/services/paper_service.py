"""Paper service for deduplication and storage logic."""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

from ..repositories.paper_repository import PaperRepository

if TYPE_CHECKING:
    from ..arxiv_parser import ArxivPaper

logger = logging.getLogger(__name__)


class PaperService:
    """Service for paper deduplication and storage operations."""

    def __init__(self) -> None:
        """Initialize the paper service with a repository."""
        self._repository = PaperRepository()

    def deduplicate_and_store(
        self,
        papers: list[ArxivPaper],
    ) -> list[ArxivPaper]:
        """Deduplicate papers against the database and store new ones.

        This method:
        1. Checks each paper against the database by arxiv_id
        2. Inserts new papers into the database
        3. Returns only papers that need processing (new + previously failed)

        Args:
            papers: List of ArxivPaper objects to deduplicate.

        Returns:
            List of ArxivPaper objects that need processing:
            - New papers (not in database)
            - Papers that exist but haven't been processed (no summary)
        """
        to_process: list[ArxivPaper] = []
        new_count = 0
        skipped_count = 0
        retry_count = 0

        for paper in papers:
            if not paper.arxiv_id:
                logger.warning("Paper without arxiv_id: %s", paper.title[:50])
                to_process.append(paper)
                continue

            if self._repository.is_processed(paper.arxiv_id):
                skipped_count += 1
                logger.debug("Skipping already processed paper: %s", paper.arxiv_id)
                continue

            if self._repository.exists(paper.arxiv_id):
                retry_count += 1
                existing = self._repository.find_by_arxiv_id(paper.arxiv_id)
                if existing:
                    to_process.append(existing)
                    logger.debug("Re-processing paper: %s", paper.arxiv_id)
            else:
                try:
                    paper_id = self._repository.insert(paper)
                    paper.db_id = paper_id
                    to_process.append(paper)
                    new_count += 1
                    logger.debug("Inserted new paper: %s", paper.arxiv_id)
                except sqlite3.IntegrityError:
                    logger.warning(
                        "Race condition inserting paper %s, fetching existing",
                        paper.arxiv_id,
                    )
                    existing = self._repository.find_by_arxiv_id(paper.arxiv_id)
                    if existing and not existing.summary:
                        to_process.append(existing)

        logger.info(
            "Deduplication complete: %d new, %d to retry, %d skipped (already processed)",
            new_count,
            retry_count,
            skipped_count,
        )

        return to_process

    def save_summaries(self, papers: list[ArxivPaper]) -> int:
        """Save LLM-generated summaries back to the database.

        Args:
            papers: List of ArxivPaper objects with summaries.

        Returns:
            Number of papers updated.
        """
        updated = 0
        for paper in papers:
            if paper.arxiv_id and paper.summary:
                self._repository.update_summary(
                    arxiv_id=paper.arxiv_id,
                    summary=paper.summary,
                    research_field=paper.research_field,
                )
                updated += 1

        logger.info("Saved summaries for %d papers", updated)
        return updated

    def get_stats(self) -> dict:
        """Get database statistics.

        Returns:
            Dictionary with statistics about stored papers.
        """
        total = self._repository.count_all()
        processed = self._repository.count_processed()
        earliest, latest = self._repository.get_date_range()

        return {
            "total_papers": total,
            "processed_papers": processed,
            "unprocessed_papers": total - processed,
            "earliest_date": earliest.isoformat() if earliest else None,
            "latest_date": latest.isoformat() if latest else None,
        }
