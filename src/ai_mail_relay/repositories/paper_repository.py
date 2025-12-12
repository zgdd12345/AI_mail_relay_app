"""Repository for paper CRUD operations."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import TYPE_CHECKING

from ..database.connection import get_connection

if TYPE_CHECKING:
    from ..arxiv_parser import ArxivPaper

logger = logging.getLogger(__name__)


class PaperRepository:
    """Repository for managing papers in the database."""

    def insert(self, paper: ArxivPaper) -> int:
        """Insert a new paper into the database.

        Args:
            paper: The ArxivPaper to insert.

        Returns:
            The database ID of the inserted paper.

        Raises:
            sqlite3.IntegrityError: If a paper with the same arxiv_id already exists.
        """
        conn = get_connection()
        cursor = conn.execute(
            """
            INSERT INTO papers (
                arxiv_id, title, authors, categories, abstract,
                links, affiliations, summary, research_field,
                published_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                paper.arxiv_id,
                paper.title,
                paper.authors,
                json.dumps(paper.categories),
                paper.abstract,
                json.dumps(paper.links),
                paper.affiliations,
                paper.summary or None,
                paper.research_field or None,
                paper.published_date.isoformat() if paper.published_date else None,
            ),
        )
        conn.commit()
        paper_id = cursor.lastrowid
        logger.debug("Inserted paper %s with id %d", paper.arxiv_id, paper_id)
        return paper_id

    def find_by_arxiv_id(self, arxiv_id: str) -> ArxivPaper | None:
        """Find a paper by its arXiv ID.

        Args:
            arxiv_id: The arXiv ID to search for.

        Returns:
            The ArxivPaper if found, None otherwise.
        """
        from ..arxiv_parser import ArxivPaper

        conn = get_connection()
        cursor = conn.execute(
            "SELECT * FROM papers WHERE arxiv_id = ?",
            (arxiv_id,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_paper(row)

    def exists(self, arxiv_id: str) -> bool:
        """Check if a paper with the given arXiv ID exists.

        Args:
            arxiv_id: The arXiv ID to check.

        Returns:
            True if the paper exists, False otherwise.
        """
        conn = get_connection()
        cursor = conn.execute(
            "SELECT 1 FROM papers WHERE arxiv_id = ?",
            (arxiv_id,),
        )
        return cursor.fetchone() is not None

    def is_processed(self, arxiv_id: str) -> bool:
        """Check if a paper has been processed (has summary).

        Args:
            arxiv_id: The arXiv ID to check.

        Returns:
            True if the paper exists and has been processed, False otherwise.
        """
        conn = get_connection()
        cursor = conn.execute(
            "SELECT 1 FROM papers WHERE arxiv_id = ? AND processed_at IS NOT NULL",
            (arxiv_id,),
        )
        return cursor.fetchone() is not None

    def find_unprocessed(self) -> list[ArxivPaper]:
        """Find all papers that haven't been processed yet.

        Returns:
            List of ArxivPaper objects without summaries.
        """
        from ..arxiv_parser import ArxivPaper

        conn = get_connection()
        cursor = conn.execute(
            "SELECT * FROM papers WHERE processed_at IS NULL ORDER BY fetched_at"
        )

        return [self._row_to_paper(row) for row in cursor.fetchall()]

    def update_summary(
        self,
        arxiv_id: str,
        summary: str,
        research_field: str,
    ) -> None:
        """Update a paper with its LLM-generated summary.

        Args:
            arxiv_id: The arXiv ID of the paper to update.
            summary: The LLM-generated summary.
            research_field: The extracted research field.
        """
        conn = get_connection()
        conn.execute(
            """
            UPDATE papers
            SET summary = ?, research_field = ?, processed_at = CURRENT_TIMESTAMP
            WHERE arxiv_id = ?
            """,
            (summary, research_field, arxiv_id),
        )
        conn.commit()
        logger.debug("Updated summary for paper %s", arxiv_id)

    def find_by_date_range(
        self,
        start_date: date,
        end_date: date | None = None,
    ) -> list[ArxivPaper]:
        """Find papers within a date range.

        Args:
            start_date: The start date (inclusive).
            end_date: The end date (inclusive). Defaults to start_date.

        Returns:
            List of ArxivPaper objects within the date range.
        """
        from ..arxiv_parser import ArxivPaper

        if end_date is None:
            end_date = start_date

        conn = get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM papers
            WHERE published_date BETWEEN ? AND ?
            ORDER BY published_date DESC, id DESC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        )

        return [self._row_to_paper(row) for row in cursor.fetchall()]

    def find_by_ingested_date_range(
        self,
        start_date: date,
        end_date: date | None = None,
    ) -> list[ArxivPaper]:
        """Find papers whose fetched_at timestamps fall within a date range."""
        from ..arxiv_parser import ArxivPaper

        if end_date is None:
            end_date = start_date

        start_ts = f"{start_date.isoformat()} 00:00:00"
        end_ts = f"{end_date.isoformat()} 23:59:59"

        conn = get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM papers
            WHERE fetched_at BETWEEN ? AND ?
            ORDER BY fetched_at DESC, id DESC
            """,
            (start_ts, end_ts),
        )

        return [self._row_to_paper(row) for row in cursor.fetchall()]

    def find_for_report_date(self, report_date: date) -> list[ArxivPaper]:
        """Load papers for a report date.

        Priority:
        1) published_date within the target day
        2) processed_at within the target day (covers legacy rows without published_date)
        No cross-day fallback: only return papers that match the target date.
        """
        from ..arxiv_parser import ArxivPaper

        # 1) By published_date
        by_pub = self.find_by_date_range(report_date, report_date)
        if by_pub:
            return by_pub

        # 2) By processed_at day window
        start_ts = f"{report_date.isoformat()} 00:00:00"
        end_ts = f"{report_date.isoformat()} 23:59:59"
        conn = get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM papers
            WHERE processed_at BETWEEN ? AND ?
            ORDER BY processed_at DESC, id DESC
            """,
            (start_ts, end_ts),
        )
        by_processed = [self._row_to_paper(row) for row in cursor.fetchall()]
        return by_processed

    def count_all(self) -> int:
        """Count total number of papers in the database."""
        conn = get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM papers")
        return cursor.fetchone()[0]

    def count_processed(self) -> int:
        """Count number of processed papers."""
        conn = get_connection()
        cursor = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE processed_at IS NOT NULL"
        )
        return cursor.fetchone()[0]

    def get_date_range(self) -> tuple[date | None, date | None]:
        """Get the date range of papers in the database.

        Returns:
            Tuple of (earliest_date, latest_date), or (None, None) if empty.
        """
        conn = get_connection()
        cursor = conn.execute(
            "SELECT MIN(published_date), MAX(published_date) FROM papers"
        )
        row = cursor.fetchone()
        if row[0] is None:
            return None, None

        return (
            date.fromisoformat(row[0]),
            date.fromisoformat(row[1]),
        )

    def find_by_arxiv_ids(self, arxiv_ids: list[str]) -> list[ArxivPaper]:
        """Fetch papers by a list of arXiv IDs (order preserved as input where possible)."""
        if not arxiv_ids:
            return []

        from ..arxiv_parser import ArxivPaper

        conn = get_connection()
        placeholders = ",".join("?" for _ in arxiv_ids)
        cursor = conn.execute(
            f"SELECT * FROM papers WHERE arxiv_id IN ({placeholders})",
            arxiv_ids,
        )
        rows = cursor.fetchall()
        found_map = {row["arxiv_id"]: self._row_to_paper(row) for row in rows}
        # Preserve input order; drop missing IDs silently
        return [found_map[arxiv_id] for arxiv_id in arxiv_ids if arxiv_id in found_map]

    def _row_to_paper(self, row) -> ArxivPaper:
        """Convert a database row to an ArxivPaper object."""
        from ..arxiv_parser import ArxivPaper

        published_date = None
        if row["published_date"]:
            published_date = date.fromisoformat(row["published_date"])

        return ArxivPaper(
            title=row["title"],
            authors=row["authors"],
            categories=json.loads(row["categories"]),
            abstract=row["abstract"] or "",
            links=json.loads(row["links"]) if row["links"] else [],
            affiliations=row["affiliations"] or "",
            arxiv_id=row["arxiv_id"],
            summary=row["summary"] or "",
            research_field=row["research_field"] or "",
            db_id=row["id"],
            published_date=published_date,
        )
