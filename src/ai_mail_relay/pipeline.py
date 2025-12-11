"""Core orchestration logic for the AI mail relay."""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from datetime import UTC, date, datetime, timedelta
from typing import Iterable, List

from .arxiv_parser import ArxivPaper, filter_papers
from .config import Settings
from .llm_client import LLMClient
from .mail_sender import MailSender


LOGGER = logging.getLogger(__name__)


def _init_database_if_enabled(settings: Settings) -> None:
    """Initialize database connection and run migrations if enabled."""
    if not settings.database.enabled:
        return

    from .database import init_database, run_migrations

    init_database(settings.database)
    run_migrations()


def _load_papers_from_db(target_date: date) -> list[ArxivPaper]:
    """Load papers for the target date from the database as a fallback."""
    from .repositories import PaperRepository

    repo = PaperRepository()
    papers = repo.find_for_report_date(target_date)
    if papers:
        LOGGER.info(
            "Loaded %d paper(s) from database for %s (fallback mode).",
            len(papers),
            target_date,
        )
    else:
        LOGGER.info("No papers found in database for %s when attempting fallback.", target_date)
    return papers


def _render_existing_summaries(papers: list[ArxivPaper]) -> str:
    """Render a markdown summary block from stored summaries/research fields."""
    blocks: list[str] = []
    for idx, paper in enumerate(papers, start=1):
        lines = [f"## Paper {idx}: {paper.title}"]
        if paper.research_field:
            lines.append(f"**细分领域**：{paper.research_field}")
        if paper.summary:
            lines.append(f"**工作内容**：{paper.summary}")
        else:
            lines.append("**工作内容**：未存储摘要")
        blocks.append("\n\n".join(lines))
    return "\n\n".join(blocks)


async def run_pipeline(settings: Settings) -> None:
    """Fetch arXiv papers (via email or API), summarize, and forward the digest."""
    # Always prepare yesterday's digest (arXiv 公告对应上一日)
    target_date = (datetime.now(UTC) - timedelta(days=1)).date()
    report_date = target_date.isoformat()
    LOGGER.info("Preparing arXiv digest for %s", report_date)

    # Initialize database if enabled
    _init_database_if_enabled(settings)

    sender = MailSender(settings.outbox)

    LOGGER.info("Using arXiv API mode to fetch papers")
    papers = fetch_from_api(settings, target_date=target_date)

    LOGGER.info("Parsed %d total papers before filtering", len(papers))
    total_fetched = len(papers)
    fetched_from_db = False

    # 如果没有解析出任何论文，尝试从数据库回退加载
    if not papers and settings.database.enabled:
        fallback_papers = _load_papers_from_db(target_date)
        if fallback_papers:
            papers = fallback_papers
            fetched_from_db = True
            total_fetched = len(papers)

    # 回退仍然为空，发送“未获取到论文”提醒
    if not papers:
        LOGGER.info("No papers found for %s, sending no-paper notification", report_date)
        sender.send_no_papers(report_date)
        return

    filtered_papers = filter_papers(
        papers, settings.filtering.allowed_categories, settings.filtering.keyword_filters
    )

    LOGGER.info("Retained %d AI-related papers after filtering", len(filtered_papers))
    total_filtered = len(filtered_papers)

    # 如果过滤后没有论文，发送“未获取到论文”提醒
    if not filtered_papers:
        LOGGER.info(
            "No AI-related papers after filtering for %s, sending no-paper notification",
            report_date,
        )
        sender.send_no_papers(report_date)
        return

    unique_papers = deduplicate_papers(filtered_papers)
    LOGGER.info("Deduplicated papers down to %d unique entries", len(unique_papers))
    for paper in unique_papers:
        if paper.published_date is None:
            paper.published_date = target_date
        if not paper.arxiv_id:
            LOGGER.warning("Paper missing arXiv ID after parsing: '%s'", paper.title[:80])

    # 如果去重后没有论文，发送"未获取到论文"提醒
    if not unique_papers:
        LOGGER.info(
            "No unique papers after deduplication for %s, sending no-paper notification",
            report_date,
        )
        sender.send_no_papers(report_date)
        return

    arxiv_ids = [paper.arxiv_id for paper in unique_papers if paper.arxiv_id]
    paper_service = None
    repo = None
    db_stats = None

    if settings.database.enabled:
        from .services import PaperService
        from .repositories import PaperRepository

        paper_service = PaperService()
        repo = PaperRepository()
        db_stats = paper_service.get_stats()

        # Ensure new papers are inserted and get unprocessed list
        papers_to_process = paper_service.deduplicate_and_store(unique_papers)

        # If everything is already processed, reuse stored data by arXiv ID
        if not papers_to_process:
            LOGGER.info("All fetched papers already processed; reusing stored summaries from DB.")
            stored_papers = repo.find_by_arxiv_ids(arxiv_ids)
            if stored_papers:
                papers_to_process = []
                final_papers = stored_papers
                final_summary_md = _render_existing_summaries(final_papers)
            else:
                LOGGER.info("Current arXiv IDs not found in DB; reprocessing with LLM.")
                papers_to_process = unique_papers

        # If we still have papers needing processing, run LLM and save
        if papers_to_process:
            llm_client = LLMClient(settings.llm)
            summary = await llm_client.summarize_papers(papers_to_process)
            paper_service.save_summaries(papers_to_process)
            # Refresh from DB to include stored summaries (preserves order by arXiv ID)
            final_papers = repo.find_by_arxiv_ids(arxiv_ids) or papers_to_process
            final_summary_md = _render_existing_summaries(final_papers)

        LOGGER.info(
            "Counts — fetched:%d, filtered:%d, unique:%d, in_db:%s, processed:%s, to_llm:%d, ready_to_send:%d",
            total_fetched,
            total_filtered,
            len(unique_papers),
            (db_stats["total_papers"] if db_stats else "N/A"),
            (db_stats["processed_papers"] if db_stats else "N/A"),
            len(papers_to_process),
            len(final_papers),
        )

    else:
        # No database: always process and send from memory
        llm_client = LLMClient(settings.llm)
        summary = await llm_client.summarize_papers(unique_papers)
        final_papers = unique_papers
        final_summary_md = summary

    summary_map = MailSender.build_summary_map(final_summary_md, final_papers)

    # Multi-user delivery path
    if settings.multi_user.enabled:
        if not settings.database.enabled:
            LOGGER.warning(
                "MULTI_USER_MODE requires DATABASE_ENABLED=true; falling back to single-user delivery."
            )
        else:
            from .services import DeliveryService, UserService

            user_service = UserService()
            delivery_service = DeliveryService(skip_delivered=settings.multi_user.skip_delivered)
            users = user_service.get_active_users()

            if not users:
                LOGGER.warning(
                    "Multi-user mode enabled but no active users found. Delivering to default recipient."
                )
            else:
                LOGGER.info("Sending personalized digests to %d active user(s)", len(users))
                for user in users:
                    user_papers = user_service.get_papers_for_user(user, final_papers)
                    if settings.multi_user.skip_delivered:
                        user_papers = delivery_service.filter_undelivered(user.id, user_papers)

                    if not user_papers:
                        LOGGER.info("No papers to deliver for user %s, skipping.", user.email)
                        continue

                    per_user_summary_map = {
                        paper.arxiv_id: summary_map.get(paper.arxiv_id, "")
                        for paper in user_papers
                        if paper.arxiv_id
                    }
                    sender.send_digest(
                        final_summary_md,
                        user_papers,
                        report_date=report_date,
                        to_address=user.email,
                        recipient_name=user.name,
                        summary_map=per_user_summary_map,
                    )
                    delivery_service.record_delivery(
                        user.id, [paper.db_id for paper in user_papers if paper.db_id is not None]
                    )

                LOGGER.info("Completed multi-user delivery.")
                return

    # Fallback to single-recipient delivery
    sender.send_digest(final_summary_md, final_papers, report_date=report_date, summary_map=summary_map)

    LOGGER.info("Successfully sent digest email with %d papers", len(final_papers))


def fetch_from_api(settings: Settings, target_date: date | None = None) -> List[ArxivPaper]:
    """Fetch papers directly from arXiv API."""
    from .arxiv_fetcher import ArxivAPIFetcher

    if target_date is None:
        target_date = (datetime.now(UTC) - timedelta(days=1)).date()

    fetcher = ArxivAPIFetcher(
        allowed_categories=settings.filtering.allowed_categories,
        max_days_back=settings.filtering.max_days_back,
    )
    papers = fetcher.fetch_papers(target_date=target_date, max_results=settings.arxiv.api_max_results)

    LOGGER.info("Fetched %d papers from arXiv API", len(papers))
    return papers


def deduplicate_papers(papers: Iterable[ArxivPaper]) -> List[ArxivPaper]:
    """Deduplicate papers by title while preserving order."""
    unique: "OrderedDict[str, ArxivPaper]" = OrderedDict()
    for paper in papers:
        normalized_title = paper.title.strip().lower()
        if normalized_title not in unique:
            unique[normalized_title] = paper
    return list(unique.values())
__all__ = ["run_pipeline"]
