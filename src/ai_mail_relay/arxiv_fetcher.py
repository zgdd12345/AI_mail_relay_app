"""Direct arXiv API fetcher as an alternative to email parsing."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import List
from xml.etree import ElementTree as ET

import httpx

from .arxiv_parser import ArxivPaper


LOGGER = logging.getLogger(__name__)
ARXIV_API_BASE = "https://export.arxiv.org/api/query"
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivAPIFetcher:
    """Fetch papers directly from arXiv API."""

    def __init__(self, allowed_categories: List[str], max_days_back: int = 1) -> None:
        """Initialize the arXiv API fetcher.

        Args:
            allowed_categories: List of arXiv categories to fetch (e.g., ['cs.AI', 'cs.LG'])
            max_days_back: Maximum number of days to look back for papers
        """
        self._categories = allowed_categories
        self._max_days_back = max_days_back

    def fetch_papers(
        self, target_date: date | None = None, max_results: int = 200
    ) -> List[ArxivPaper]:
        """Fetch papers from arXiv API for the given date and categories.

        Args:
            target_date: Date to fetch papers for (default: yesterday)
            max_results: Maximum number of papers to fetch per query

        Returns:
            List of ArxivPaper objects
        """
        if target_date is None:
            # Default to yesterday to match arXiv announcement schedule
            target_date = (datetime.utcnow() - timedelta(days=1)).date()

        categories = self._categories
        if not categories:
            LOGGER.warning("No categories configured, using default AI categories")
            categories = ["cs.AI", "cs.LG", "cs.CV", "cs.CL"]

        LOGGER.info(
            "Fetching papers from arXiv API for %s with categories: %s",
            target_date,
            ", ".join(categories),
        )

        # Build query for multiple categories
        category_query = " OR ".join([f"cat:{cat}" for cat in categories])

        # Note: We fetch recent papers and filter by date locally
        # because arXiv's submittedDate filter can be unreliable
        params = {
            "search_query": category_query,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        # Respect arXiv rate limit (1 request per 3 seconds)
        time.sleep(3)

        # Retry logic for network failures
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                response = httpx.get(
                    ARXIV_API_BASE,
                    params=params,
                    timeout=30.0,
                    headers={"User-Agent": "AI-Mail-Relay/1.0 (https://github.com/yourrepo)"},
                    follow_redirects=True,
                )
                response.raise_for_status()
                break  # Success, exit retry loop

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
                if attempt < max_retries - 1:
                    LOGGER.warning(
                        "Network error (attempt %d/%d): %s. Retrying in %d seconds...",
                        attempt + 1,
                        max_retries,
                        exc,
                        retry_delay,
                    )
                    time.sleep(retry_delay)
                    continue
                else:
                    LOGGER.error("Failed to fetch from arXiv API after %d attempts: %s", max_retries, exc)
                    return []

            except httpx.HTTPStatusError as exc:
                LOGGER.error("HTTP error from arXiv API: %s (status: %s)", exc, exc.response.status_code)
                return []

            except httpx.HTTPError as exc:
                LOGGER.error("Failed to fetch from arXiv API: %s", exc)
                return []

        papers = self._parse_arxiv_xml(response.content, target_date)
        LOGGER.info("Fetched %d papers from arXiv API", len(papers))
        return papers

    def _parse_arxiv_xml(self, xml_content: bytes, target_date: date) -> List[ArxivPaper]:
        """Parse arXiv API XML response into ArxivPaper objects.

        Args:
            xml_content: Raw XML response from arXiv API
            target_date: Date to filter papers by

        Returns:
            List of parsed ArxivPaper objects
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            LOGGER.error("Failed to parse arXiv XML response: %s", exc)
            return []

        papers: List[ArxivPaper] = []

        for entry in root.findall("atom:entry", NAMESPACES):
            try:
                paper = self._parse_entry(entry, target_date)
                if paper:
                    papers.append(paper)
            except Exception as exc:
                LOGGER.warning("Failed to parse entry: %s", exc)
                continue

        return papers

    def _parse_entry(self, entry: ET.Element, target_date: date) -> ArxivPaper | None:
        """Parse a single entry from arXiv XML.

        Args:
            entry: XML element representing a single paper
            target_date: Date to filter papers by

        Returns:
            ArxivPaper object or None if paper should be filtered out
        """
        # Extract publication date first for filtering
        published_elem = entry.find("atom:published", NAMESPACES)
        if published_elem is not None and published_elem.text:
            pub_date_str = published_elem.text.split("T")[0]  # YYYY-MM-DD
            try:
                pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d").date()
            except ValueError:
                LOGGER.warning("Invalid publication date format: %s", published_elem.text)
                return None

            # Filter to only papers within max_days_back
            oldest_date = target_date - timedelta(days=self._max_days_back - 1)
            if not (oldest_date <= pub_date <= target_date):
                return None

        # Extract title
        title_elem = entry.find("atom:title", NAMESPACES)
        title = ""
        if title_elem is not None and title_elem.text:
            title = title_elem.text.strip().replace("\n", " ")

        # Extract abstract
        summary_elem = entry.find("atom:summary", NAMESPACES)
        abstract = ""
        if summary_elem is not None and summary_elem.text:
            abstract = summary_elem.text.strip()

        # Extract authors
        authors = []
        for author_elem in entry.findall("atom:author", NAMESPACES):
            name_elem = author_elem.find("atom:name", NAMESPACES)
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text.strip())
        authors_str = ", ".join(authors)

        # Extract categories
        categories = []
        for cat_elem in entry.findall("atom:category", NAMESPACES):
            term = cat_elem.get("term")
            if term:
                categories.append(term)

        # Extract arXiv ID from entry ID
        id_elem = entry.find("atom:id", NAMESPACES)
        arxiv_id = ""
        if id_elem is not None and id_elem.text:
            # Format: http://arxiv.org/abs/2310.12345v1
            parts = id_elem.text.split("/abs/")
            if len(parts) > 1:
                # Remove version suffix (v1, v2, etc.)
                arxiv_id = parts[1].split("v")[0]

        # Extract links
        links = []
        for link_elem in entry.findall("atom:link", NAMESPACES):
            href = link_elem.get("href")
            if href:
                links.append(href)

        return ArxivPaper(
            title=title,
            authors=authors_str,
            categories=categories,
            abstract=abstract,
            links=links,
            arxiv_id=arxiv_id,
        )


__all__ = ["ArxivAPIFetcher"]
